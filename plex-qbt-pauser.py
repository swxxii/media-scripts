#!/usr/bin/env python3
# plex-qbt-pauser.py — see README.md for more information.
import atexit
import fcntl
import json
import logging
import os
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
PLEX_SESSIONS_URL = "http://192.168.1.3:32400/status/sessions"
QB_HOST = "192.168.1.3"
QB_PORT = 8081
SKIP_CATEGORY = "force"
INTERVAL_SECONDS = 30
SECRETS_FILENAME = "secrets.json"
LOG_MAX_BYTES = 100_000
LOG_LEVEL = logging.INFO

# -------------------------------------------------------------------------
# INITIAL SETUP
# -------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
SCRIPT = Path(__file__).resolve()
LOG_FILE = SCRIPT.with_suffix(".log")
PID_FILE = SCRIPT.with_suffix(".pid")
DETACHED_ENV = "PLEX_QBT_PAUSER_DETACHED"
log = logging.getLogger("plex-qbt-pauser")
log.setLevel(LOG_LEVEL)
_h = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=0)
_h.setFormatter(
    logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
log.addHandler(_h)

_lock_fd = None


# Relaunches the script as a detached background daemon process.
def detach_in_background():
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


# Ensures only a single instance of the script runs using a PID file lock.
def acquire_lock():
    global _lock_fd
    _lock_fd = open(PID_FILE, "w")
    try:
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("Another instance is already running – exiting.", file=sys.stderr)
        sys.exit(0)
    _lock_fd.write(str(os.getpid()))
    _lock_fd.flush()

    def _unlock():
        _lock_fd.close()
        PID_FILE.unlink(missing_ok=True)

    atexit.register(_unlock)


# Loads sensitive credentials from secrets.json and combines them with global config.
def load_config():
    secrets_path = (ROOT / SECRETS_FILENAME).resolve()
    try:
        secrets = json.loads(secrets_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("Invalid secrets file", file=sys.stderr)
        sys.exit(1)
    log.info("Loaded secrets from %s", secrets_path)
    return {
        "plex_sessions_url": PLEX_SESSIONS_URL,
        "plex_token": secrets["plex_token"],
        "qb_host": QB_HOST,
        "qb_port": QB_PORT,
        "qb_user": secrets["qbittorrent_username"],
        "qb_password": secrets["qbittorrent_password"],
        "skip_category": SKIP_CATEGORY,
        "interval_seconds": INTERVAL_SECONDS,
    }


# Main loop: monitors Plex for active streams and pauses qBittorrent accordingly.
def main():
    c = load_config()
    paused = None
    http = requests.Session()
    http.headers["Accept"] = "application/xml"
    qb = qbittorrentapi.Client(
        host=c["qb_host"],
        port=c["qb_port"],
        username=c["qb_user"],
        password=c["qb_password"],
    )
    qb.auth_log_in()
    log.info("Connected to qBittorrent – monitoring Plex sessions...")

    # Toggles the alternative speed limits in qBittorrent.
    def speed(alt, msg=None):
        try:
            if str(qb.transfer_speed_limits_mode()) == ("1" if alt else "0"):
                return
            qb.transfer_set_speed_limits_mode(alt)
            if msg:
                log.info(msg)
        except Exception as e:
            log.warning("qBittorrent speed limits: %s", e)

    while True:
        try:
            r = http.get(
                c["plex_sessions_url"],
                params={"X-Plex-Token": c["plex_token"]},
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

            if n > 0:
                if paused is not True:
                    log.info("%d remote user(s) playing – pausing torrents", n)
                ex = (c["skip_category"] or "").strip()
                if not ex:
                    qb.torrents.pause.all()
                    skipped = 0
                else:
                    skipped, hashes = 0, []
                    for t in qb.torrents_info():
                        if (t.get("category") or "") == ex:
                            skipped += 1
                            log.info("Skipped pausing – %r", t.get("name") or "")
                        else:
                            hashes.append(t.get("hash") or "")
                    if hashes:
                        qb.torrents_pause(torrent_hashes=hashes)
                speed(
                    skipped > 0,
                    (
                        "Speed limits: alternative (%d torrent(s) still active)" % skipped
                        if skipped
                        else "Speed limits: normal (no torrents in skip category)"
                    ),
                )
                paused = True
            elif paused is not False:
                log.info("No remote playback – resuming torrents")
                speed(False, "Speed limits: normal")
                try:
                    qb.torrents.resume.all()
                except Exception as e:
                    log.warning("qBittorrent resume all: %s", e)
                paused = False
        except requests.RequestException as e:
            log.warning("Plex request failed: %s – retrying next cycle", e)
            http.close()
            http = requests.Session()
            http.headers["Accept"] = "application/xml"
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
    if detach_in_background():
        sys.exit(0)
    acquire_lock()
    log.info("Script started (pid=%s)", os.getpid())
    main()
