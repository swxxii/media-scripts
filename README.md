# media-scripts

Utility scripts for media servers, backup automation, and file management.

## Configuration

Update scripts with your configuration directly within the `.py` or `.sh` files.

Copy `secrets.example.json` to `secrets.json` and enter your sensitive credentials (`plexmeta.py`and `plex-qbt-pauser.py`).

---

## Scripts

### `backuparr.sh`

Automated backup for Arr services and Docker containers.

**Features:**

- Existing backup zips from Sonarr, Radarr, and Prowlarr and Bazarr
- qBittorrent configuration
- Docker container data folders (stops and restarts containers)
- Syncs all backups to cloud-synced directory (Google Drive, etc.)
- Verbose logging to `backuparr.log`

**Setup:**

1. Open `backuparr.sh` and configure the inline variables at the top of the file:
  - `DESTDIR` - Where the backups are saved
  - `ARR_BASE` - The directory containing your Arr apps
  - `ARR_APPS` - The list of Arr apps you have installed
  - `BAZARR_DATA_DIR` - Location of Bazarr's automated backups 
  - `QBITTORRENT_CONF` - Location of `qBittorrent.conf`
  - `CONTAINERS` - The list of Docker containers you want backed up 
  - `DOCKER_BASE_DIR` - Where your Docker container data/compose files live 
  - `SCRIPTS_DIR` - Location of the scripts folder to back up

**Usage:**

Run manually, or add to your crontab to run regularly (e.g., weekly):

```bash
0 3 * * 0 /path/to/backuparr.sh
```

---

### `media-extensions.py`

Restores file extensions for photos and videos by analyzing magic bytes.

**Features:**

- Detects file types from binary headers/magic bytes
- Supports images: JPEG, PNG, GIF, BMP, TIFF, HEIC, HEIF, AVIF
- Supports videos: MP4, M4V, MOV, 3GP, MKV, FLV, MPEG, OGG, AVI, WebM
- Handles equivalent extensions (.jpg/.jpeg, .tiff/.tif, etc.)
- Skips system files (.DS_Store, Thumbs.db, etc.)
- Dry-run mode available for preview

**Usage:**

```bash
# Preview changes without modifying files (Dry Run)
python3 media-extensions.py /path/to/files --dry-run

# Execute and rename
python3 media-extensions.py /path/to/files
```

---

### `movie-folders.sh`

Organizes movie files into individual folders for Plex compatibility.

**Features:**

- Moves video files (mkv, mp4, avi, mpeg4, mpg, divx) into their own folders
- Consolidates companion files (subtitles, nfo, etc.) with each movie
- Cleans up small/empty folders (< 90MB)
- Progress logging

**Setup:**

1. Open `movie-folders.sh`.
2. Edit the `src` variable to point to your target directory.

**Usage:**

CAUTION! This script uses destructive cleanup (`rm -rf`) for empty folders.

```bash
./movie-folders.sh
```

---

### `plex-chromecast-fix.sh`

Post-update Plex helper for a Chromecast playback issue where `Generic.xml` is incorrectly used.

**What it does:**

- Renames `/usr/lib/plexmediaserver/Resources/Profiles/Generic.xml` to `Generic.xml.old`
- Restarts `plexmediaserver`
- If already renamed, prints an "Already disabled" message

**Usage:**

```bash
sudo ./plex-chromecast-fix.sh
```

For full diagnosis details, see [Chromecast.md](Chromecast.md).

---

### `plexmeta.py`

Exports Plex library to CSV and JSON metadata via Tautulli API so you have a backup of what was in Plex if you lose everything (e.g. NAS failure).

**Features:**

- Queries Tautulli for all library sections
- Triggers CSV and JSON exports for each section
- Polls until exports complete
- Downloads exports files to a local folder
- Cleans up server-side exports

**Setup:**

1. Install dependencies: `pip install requests`
2. Edit `plexmeta.py` and configure the inline variables:
  - `TAUTULLI` - Tautulli server URL and port
  - `OUTPUT_DIR` - Folder to save exported CSVs/JSONs
3. Edit `secrets.json` and configure `tautulli_api_key`.

**Usage:**

```bash
python3 plexmeta.py
```

---

### `plex-qbt-pauser.py`

Designed to pause torrents when remote users are playing in Plex then resume when they finish playing. Skip pausing torrents in certain categories. If any torrents remain active switches on alternative speed limit.

The first run spawns a background worker and then exits (like `nohup`). 

**Dependencies:**

1. Run in script folder: `pip install requests qbittorrent-api`

**Setup:**

1. Edit `plex-qbt-pauser.py` and configure the inline variables at the top of the file:
  - `PLEX_SESSIONS_URL` - Change Plex server IP
  - `QB_HOST` - qBittorrent IP address
  - `QB_PORT` - qBittorrent WebUI port
  - `SKIP_CATEGORY` - Don't pause torrents in this caregory (use `""` to pause all)
  - `INTERVAL_SECONDS` - Time between checks in seconds
2. Edit `secrets.json` and configure:
  - `plex_token` *(To find this: Plex Web → library item → Get Info → View XML → copy* `X-Plex-Token` *value from URL)*
  - `qbittorrent_username`
  - `qbittorrent_password`

**Usage:**

Run it directly, or set it up as a cron job hourly to ensure script is always running in case of crash or reboot.

```bash
# Install as Cron job
sudo ln -s /path/to/plex-qbt-pauser.py /etc/cron.hourly/plex-qbt-pauser

# Restart the script
pkill -f plex-qbt-pauser.py && /path/to/plex-qbt-pauser.py

# Monitor live logs
tail -f /path/to/plex-qbt-pauser.log  
```

---

### `test-trackers.py`

Tests BitTorrent tracker URLs for validity and performance.

**Features:**

- Fetches tracker lists from multiple public sources
- Tests UDP and HTTP trackers concurrently
- Measures tracker response latency
- Filters out dead/slow trackers
- Saves valid trackers to `valid_trackers.txt`
- Progress bar and logging

**Setup:**

1. Open `test-trackers.py` and optionally configure:
  - `TRACKER_LISTS` - Source URLs to pull potential trackers from.
  - `OUTPUT_FILE` / `LOG_FILE` - Filepaths for output.

**Usage:**

```bash
python3 test-trackers.py
```

---

### [Chromecast.md](Chromecast.md)

When casting from the Plex iOS app to a Chromecast, some movies fail to play while others work fine. This document describes the cause, how to diagnose it from server logs, and how to fix it.