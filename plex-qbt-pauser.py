#!/usr/bin/env python3
# plex-qbt-pauser.py — see README.md for more information.
# Imports for system operations, logging, file handling, and API clients
import atexit
import fcntl
import json
import logging
import os
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from logging.handlers import RotatingFileHandler
from pathlib import Path
import qbittorrentapi
import requests

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------

# Plex server endpoint for checking active streaming sessions
PLEX_URL: str = "http://192.168.1.3:32400/status/sessions"
QB_HOST: str = "192.168.1.3"               # qBittorrent host
QB_PORT: int = 8081                        # qBittorrent port
SKIP_CAT: str = "force"                    # Don't pause torrents in this category ("" to pause all)
INTERVAL: int = 30                         # Polling interval in seconds
SECRETS_FILE: str = "secrets.json"         # File with API credentials
MAX_BYTES: int = 100_000                   # Max log file size before rotation
LOG_LEVEL: int = logging.INFO              # Logging verbosity level
MAX_NORMAL: int = 99                       # Max concurrent torrents when no playback
MAX_LIMITED: int = 1                       # Max concurrent torrents during playback

# -------------------------------------------------------------------------
# INITIAL SETUP
# -------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent     # Script directory
SCRIPT = Path(__file__).resolve()          # Script file path
LOG_FILE = SCRIPT.with_suffix(".log")      # Log file path
PID_FILE = SCRIPT.with_suffix(".pid")      # Lock file path
DETACHED_ENV = "PLEX_QBT_PAUSER_DETACHED"  # Detached process indicator

# Create rotating file logger with timestamp and level formatting
def setup_logger(log_file: Path, level: int, max_bytes: int) -> logging.Logger:
    logger = logging.getLogger("plex-qbt-pauser")
    logger.setLevel(level)
    # Create rotating handler that overwrites when max size is reached
    handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=0)
    handler.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    # Avoid duplicate handlers if logger already exists
    if not logger.hasHandlers():
        logger.addHandler(handler)
    return logger

log = setup_logger(LOG_FILE, LOG_LEVEL, MAX_BYTES)


# Spawn a detached background process if not already running as detached
def detach_in_background() -> bool:
    # If already detached, don't spawn another process
    if os.environ.get(DETACHED_ENV):
        return False
    # Prepare new process with detached environment variable
    argv = [sys.executable, "-u", str(SCRIPT)]
    env = {**os.environ, DETACHED_ENV: "1"}
    with open(LOG_FILE, "a", encoding="utf-8") as bootlog:
        bootlog.write("\n--- detach: spawning worker ---\n")
        bootlog.flush()
        # Start process in new session to detach from parent
        proc = subprocess.Popen(
            argv,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=bootlog,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    time.sleep(0.25)
    # Check if child process exited immediately (error condition)
    code = proc.poll()
    if code is not None:
        why = "already running / lock" if code == 0 else f"code {code}"
        print(f"Worker exited ({why}). See {LOG_FILE}", file=sys.stderr)
        sys.exit(code)
    print(f"Worker running in background (log {LOG_FILE})", file=sys.stderr)
    return True



from contextlib import contextmanager

# File-based lock to prevent multiple instances from running simultaneously
@contextmanager
def acquire_lock():
    if not PID_FILE.exists():
        PID_FILE.touch()
    lock_fd = open(PID_FILE, "r+")
    try:
        # Try to acquire exclusive non-blocking lock (fails if already locked)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("Another instance is already running – exiting.", file=sys.stderr)
        sys.exit(0)
    # Write current process ID to lock file
    lock_fd.seek(0)
    lock_fd.truncate()
    lock_fd.write(str(os.getpid()))
    lock_fd.flush()
    try:
        yield
    finally:
        lock_fd.close()
        PID_FILE.unlink(missing_ok=True)



# Load API credentials and configuration from secrets.json
def load_config() -> dict:
    # Construct path to secrets file in script directory
    secrets_path = (ROOT / SECRETS_FILE).resolve()
    try:
        # Parse JSON from file
        secrets = json.loads(secrets_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("Invalid secrets file", file=sys.stderr)
        sys.exit(1)
    log.info("Loaded secrets from %s", secrets_path)
    # Combine secrets with hardcoded config values
    return {
        "plex_sessions_url": PLEX_URL,
        "plex_token": secrets["plex_token"],
        "qb_host": QB_HOST,
        "qb_port": QB_PORT,
        "qb_user": secrets["qbittorrent_username"],
        "qb_password": secrets["qbittorrent_password"],
        "skip_category": SKIP_CAT,
        "interval_seconds": INTERVAL,
    }


# Manages qBittorrent operations (pausing, resuming, changing limits)
class QbitManager:
    def __init__(self, qb: qbittorrentapi.Client, log: logging.Logger):
        self.qb = qb
        self.log = log

    # Toggle between normal and alternative (reduced) speed limits
    def set_speed_limits(self, alt: bool, msg: str = None):
        try:
            if str(self.qb.transfer_speed_limits_mode()) == ("1" if alt else "0"):
                return
            self.qb.transfer_set_speed_limits_mode(alt)
            if msg:
                self.log.info(msg)
        except Exception as e:
            self.log.warning("qBittorrent speed limits: %s", e)

    # Limit concurrent active torrents during remote playback
    def set_max_torrents(self, limit: int):
        try:
            prefs = self.qb.app_preferences()
            if prefs.get("max_active_torrents") == limit:
                return
            self.qb.app_set_preferences({"max_active_torrents": limit})
            self.log.info(f"Max active torrents: {limit}")
        except Exception as e:
            self.log.warning("qBittorrent max active torrents: %s", e)

    # Pause non-skip torrents and resume skip-category torrents
    def pause_resume_by_category(self, skip_category: str):
        skipped, to_pause, to_resume = 0, [], []
        # Iterate through all torrents and categorize for pause/resume
        for t in self.qb.torrents_info():
            state = (t.get("state") or "").lower()
            name = t.get("name") or ""
            thash = t.get("hash") or ""
            if (t.get("category") or "") == skip_category:
                skipped += 1
                # Resume if skip-category torrent is paused
                if "pause" in state:
                    to_resume.append(thash)
                    self.log.info("Resuming skip-category torrent – %r", name)
            else:
                # Pause if non-skip torrent is actively running
                # Skip errored and checking-in-progress states
                if "pause" not in state and state not in ["error", "unknown", "missingfiles", "checkingresume"]:
                    to_pause.append(thash)
                    self.log.info("Pausing non-skip torrent – %r", name)
        # Batch pause and resume operations
        if to_pause:
            self.qb.torrents_pause(torrent_hashes=to_pause)
        if to_resume:
            self.qb.torrents_resume(torrent_hashes=to_resume)
        return skipped

    # Resume all paused torrents
    def resume_all(self):
        try:
            self.qb.torrents.resume.all()
        except Exception as e:
            self.log.warning("qBittorrent resume all: %s", e)


# Monitors active Plex streaming sessions
class PlexMonitor:
    def __init__(self, config: dict, log: logging.Logger):
        self.c = config
        self.log = log
        # Session for HTTP requests to Plex server
        self.http = requests.Session()
        self.http.headers["Accept"] = "application/xml"

    # Count active remote Plex playback sessions (non-local, playing state)
    def get_remote_play_count(self) -> int:
        r = self.http.get(
            self.c["plex_sessions_url"],
            params={"X-Plex-Token": self.c["plex_token"]},
            timeout=15,
        )
        r.raise_for_status()
        # Parse XML response and count remote players in playing state
        root = ET.fromstring(r.text)
        # Sum up sessions where player is remote (local=0) and actively playing
        n = sum(
            1
            for v in root
            if (pl := v.find("Player")) is not None
            and pl.get("local") == "0"
            and pl.get("state") == "playing"
        )
        return n

    # Reset HTTP session to recover from connection errors
    def reset_http(self):
        self.http.close()
        self.http = requests.Session()
        self.http.headers["Accept"] = "application/xml"


# Main monitoring loop: check Plex, pause/resume torrents based on activity
def main():
    # Load API credentials from secrets.json
    c = load_config()
    # Track state to avoid logging redundant state transitions
    paused = None
    # Connect to qBittorrent
    qb = qbittorrentapi.Client(
        host=c["qb_host"],
        port=c["qb_port"],
        username=c["qb_user"],
        password=c["qb_password"],
    )
    qb.auth_log_in()
    log.info("Connected to qBittorrent – monitoring Plex sessions...")
    # Initialize manager instances for qBittorrent and Plex operations
    qbm = QbitManager(qb, log)
    plex = PlexMonitor(c, log)

    # Infinite monitoring loop
    while True:
        try:
            # Check for active remote Plex streams
            n = plex.get_remote_play_count()
            # If any remote playback is active, pause torrents
            if n > 0:
                # Remote playback detected - pause torrents
                # Log state change only on transition from unpaused to paused
                if paused is not True:
                    log.info("%d remote user(s) playing – pausing torrents", n)
                ex = (c["skip_category"] or "").strip()
                # If no skip category configured, pause all torrents
                if not ex:
                    # No skip category - pause all torrents
                    qb.torrents.pause.all()
                    skipped = 0
                else:
                    # Pause non-skip torrents, resume skip-category torrents
                    skipped = qbm.pause_resume_by_category(ex)
                # Reduce speed limits when torrents still active
                qbm.set_speed_limits(
                    skipped > 0,
                    (
                        "Speed limits: alternative - %d torrents active" % skipped
                        if skipped
                        else "Speed limits: normal - no torrents active"
                    ),
                )
                qbm.set_max_torrents(
                    MAX_LIMITED if skipped > 0 else MAX_NORMAL,
                )
                paused = True
            elif paused is not False:
                # No remote playback - resume torrents
                # Log state change only on transition from paused to unpaused
                log.info("No remote playback – resuming torrents")
                qbm.set_speed_limits(False, "Speed limits: normal")
                qbm.set_max_torrents(MAX_NORMAL)
                qbm.resume_all()
                paused = False
        except requests.RequestException as e:
            # Network error connecting to Plex - reset connection
            log.warning("Plex request failed: %s – retrying next cycle", e)
            plex.reset_http()
        except qbittorrentapi.exceptions.APIConnectionError as e:
            # Lost connection to qBittorrent - attempt to re-authenticate
            log.warning("qBittorrent connection lost: %s", e)
            try:
                qb.auth_log_in()
            except Exception as ae:
                log.error("qBittorrent re-auth failed: %s", ae)
        except Exception:
            log.exception("Unexpected error")
        # Wait before next check
        time.sleep(c["interval_seconds"])



if __name__ == "__main__":
    if "--quit" in sys.argv:
        sys.argv.remove("--quit")
        if PID_FILE.exists():
            try:
                old_pid = int(PID_FILE.read_text().strip())
                os.kill(old_pid, signal.SIGKILL)
                print(f"Killed existing worker (pid {old_pid})...", file=sys.stderr)
            except (OSError, ValueError):
                pass
        sys.exit(0)

    if "--restart" in sys.argv:
        sys.argv.remove("--restart")
        if PID_FILE.exists():
            try:
                old_pid = int(PID_FILE.read_text().strip())
                os.kill(old_pid, signal.SIGKILL)
                print(f"Killed existing worker (pid {old_pid})...", file=sys.stderr)
                time.sleep(0.5)
            except (OSError, ValueError):
                pass

    if detach_in_background():
        sys.exit(0)
    with acquire_lock():
        log.info("Script started (pid=%s)", os.getpid())
        main()
