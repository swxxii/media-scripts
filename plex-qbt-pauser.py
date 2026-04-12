#!/usr/bin/env python3
# plex-qbt-pauser.py — see README.md for more information.
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


PLEX_URL: str = "http://192.168.1.3:32400/status/sessions"
QB_HOST: str = "192.168.1.3"
QB_PORT: int = 8081
SKIP_CAT: str = "force"
INTERVAL: int = 30
SECRETS_FILE: str = "secrets.json"
MAX_BYTES: int = 100_000
LOG_LEVEL: int = logging.INFO
MAX_NORMAL: int = 99
MAX_LIMITED: int = 1

# -------------------------------------------------------------------------
# INITIAL SETUP
# -------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
SCRIPT = Path(__file__).resolve()
LOG_FILE = SCRIPT.with_suffix(".log")
PID_FILE = SCRIPT.with_suffix(".pid")
DETACHED_ENV = "PLEX_QBT_PAUSER_DETACHED"

def setup_logger(log_file: Path, level: int, max_bytes: int) -> logging.Logger:
    logger = logging.getLogger("plex-qbt-pauser")
    logger.setLevel(level)
    handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=0)
    handler.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    if not logger.hasHandlers():
        logger.addHandler(handler)
    return logger

log = setup_logger(LOG_FILE, LOG_LEVEL, MAX_BYTES)



def detach_in_background() -> bool:
    if os.environ.get(DETACHED_ENV):
        return False
    argv = [sys.executable, "-u", str(SCRIPT)]
    env = {**os.environ, DETACHED_ENV: "1"}
    with open(LOG_FILE, "a", encoding="utf-8") as bootlog:
        bootlog.write("\n--- detach: spawning worker ---\n")
        bootlog.flush()
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
    code = proc.poll()
    if code is not None:
        why = "already running / lock" if code == 0 else f"code {code}"
        print(f"Worker exited ({why}). See {LOG_FILE}", file=sys.stderr)
        sys.exit(code)
    print(f"Worker running in background (log {LOG_FILE})", file=sys.stderr)
    return True



from contextlib import contextmanager

@contextmanager
def acquire_lock():
    if not PID_FILE.exists():
        PID_FILE.touch()
    lock_fd = open(PID_FILE, "r+")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("Another instance is already running – exiting.", file=sys.stderr)
        sys.exit(0)
    lock_fd.seek(0)
    lock_fd.truncate()
    lock_fd.write(str(os.getpid()))
    lock_fd.flush()
    try:
        yield
    finally:
        lock_fd.close()
        PID_FILE.unlink(missing_ok=True)



def load_config() -> dict:
    secrets_path = (ROOT / SECRETS_FILE).resolve()
    try:
        secrets = json.loads(secrets_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("Invalid secrets file", file=sys.stderr)
        sys.exit(1)
    log.info("Loaded secrets from %s", secrets_path)
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



class QbitManager:
    def __init__(self, qb: qbittorrentapi.Client, log: logging.Logger):
        self.qb = qb
        self.log = log

    def set_speed_limits(self, alt: bool, msg: str = None):
        try:
            if str(self.qb.transfer_speed_limits_mode()) == ("1" if alt else "0"):
                return
            self.qb.transfer_set_speed_limits_mode(alt)
            if msg:
                self.log.info(msg)
        except Exception as e:
            self.log.warning("qBittorrent speed limits: %s", e)

    def set_max_torrents(self, limit: int, msg: str = None):
        try:
            prefs = self.qb.app_preferences()
            if prefs.get("max_active_torrents") == limit:
                return
            self.qb.app_set_preferences({"max_active_torrents": limit})
            if msg:
                self.log.info(msg)
        except Exception as e:
            self.log.warning("qBittorrent max active torrents: %s", e)

    def pause_resume_by_category(self, skip_category: str):
        skipped, to_pause, to_resume = 0, [], []
        for t in self.qb.torrents_info():
            state = (t.get("state") or "").lower()
            name = t.get("name") or ""
            thash = t.get("hash") or ""
            if (t.get("category") or "") == skip_category:
                skipped += 1
                to_resume.append(thash)
                if "pause" in state:
                    self.log.info("Resuming skip-category torrent – %r", name)
            else:
                to_pause.append(thash)
                if "pause" not in state and state not in ["error", "unknown", "missingfiles", "checkingresume"]:
                    self.log.info("Pausing non-skip torrent – %r", name)
        if to_pause:
            self.qb.torrents_pause(torrent_hashes=to_pause)
        if to_resume:
            self.qb.torrents_resume(torrent_hashes=to_resume)
        return skipped

    def resume_all(self):
        try:
            self.qb.torrents.resume.all()
        except Exception as e:
            self.log.warning("qBittorrent resume all: %s", e)


class PlexMonitor:
    def __init__(self, config: dict, log: logging.Logger):
        self.c = config
        self.log = log
        self.http = requests.Session()
        self.http.headers["Accept"] = "application/xml"

    def get_remote_play_count(self) -> int:
        r = self.http.get(
            self.c["plex_sessions_url"],
            params={"X-Plex-Token": self.c["plex_token"]},
            timeout=15,
        )
        r.raise_for_status()
        root = ET.fromstring(r.text)
        n = sum(
            1
            for v in root
            if (pl := v.find("Player")) is not None
            and pl.get("local") == "0"
            and pl.get("state") == "playing"
        )
        return n

    def reset_http(self):
        self.http.close()
        self.http = requests.Session()
        self.http.headers["Accept"] = "application/xml"


def main():
    c = load_config()
    paused = None
    qb = qbittorrentapi.Client(
        host=c["qb_host"],
        port=c["qb_port"],
        username=c["qb_user"],
        password=c["qb_password"],
    )
    qb.auth_log_in()
    log.info("Connected to qBittorrent – monitoring Plex sessions...")
    qbm = QbitManager(qb, log)
    plex = PlexMonitor(c, log)

    while True:
        try:
            n = plex.get_remote_play_count()
            if n > 0:
                if paused is not True:
                    log.info("%d remote user(s) playing – pausing torrents", n)
                ex = (c["skip_category"] or "").strip()
                if not ex:
                    qb.torrents.pause.all()
                    skipped = 0
                else:
                    skipped = qbm.pause_resume_by_category(ex)
                qbm.set_speed_limits(
                    skipped > 0,
                    (
                        "Speed limits: alternative (%d torrent(s) still active)" % skipped
                        if skipped
                        else "Speed limits: normal (no torrents in skip category)"
                    ),
                )
                qbm.set_max_torrents(
                    MAX_LIMITED if skipped > 0 else MAX_NORMAL,
                    (
                        f"Max active torrents: {MAX_LIMITED} (%d torrent(s) still active)" % skipped
                        if skipped
                        else f"Max active torrents: {MAX_NORMAL} (no torrents in skip category)"
                    ),
                )
                paused = True
            elif paused is not False:
                log.info("No remote playback – resuming torrents")
                qbm.set_speed_limits(False, "Speed limits: normal")
                qbm.set_max_torrents(MAX_NORMAL, "Max active torrents: 99")
                qbm.resume_all()
                paused = False
        except requests.RequestException as e:
            log.warning("Plex request failed: %s – retrying next cycle", e)
            plex.reset_http()
        except qbittorrentapi.exceptions.APIConnectionError as e:
            log.warning("qBittorrent connection lost: %s", e)
            try:
                qb.auth_log_in()
            except Exception as ae:
                log.error("qBittorrent re-auth failed: %s", ae)
        except Exception:
            log.exception("Unexpected error")
        time.sleep(c["interval_seconds"])



if __name__ == "__main__":
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
