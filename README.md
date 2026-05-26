# media-scripts

Utility scripts for media servers, backup automation, and file management.

## Configuration

Update scripts with your configuration directly within the `.py` or `.sh` files.

Copy `secrets.example.json` to `secrets.json` and enter your sensitive credentials (`plexmeta.py` and `plex-qbt-pauser.py`).

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

### `check-mounts.sh`

Checks that configured mount points are healthy and remounts them if they are stale or unresponsive.

**Features:**

- Tests each mount point with a short `touch` probe (5 second timeout)
- Lazily unmounts and remounts stale/dead mounts automatically
- Cleans up test files on success

**Setup:**

1. Open `check-mounts.sh` and edit the `MOUNTS` array to list your mount points.

**Usage:**

Run manually, or add to cron to run periodically (e.g., every 5 minutes):

```bash
*/5 * * * * /path/to/check-mounts.sh
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
# Preview changes without modifying files
python3 media-extensions.py /path/to/files --dry-run

# Execute and rename files (default mode)
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

### `permissions.sh`

Sets correct ownership and permissions for media directories and Docker container data folders.

**What it fixes:**

- qBittorrent downloads: `qbittorrent:media`, `777`
- Plex media library: `plex:media`, `777`
- Plex logs: `plex:media`, `775` (allows Tautulli read access)
- Docker container data folders (cleanuparr, filebrowser, tautulli, wordpress, uptime-kuma, gitea)

**Usage:**

```bash
sudo ./permissions.sh
```

---

### `plex-buffer.sh`

Tautulli notification trigger script for logging buffering events to a log file so you can review who buffered, what title, and how many times.

**Config:**

- `LOG` - Log file path (default: `/scripts/plex-buffer.log`) - should be writable by docker container
- `KEEP_LINES` - Maximum number of log lines to keep (default: `500`)

The script appends each event, then trims the file to the last `KEEP_LINES` entries.
It also uses a lock directory so overlapping Buffer Warning events do not corrupt the log.

**Tautulli Setup:**

1. Go to **Settings -> Notification Agents -> Add -> Script**.
2. Set **Script Folder** to `/scripts` and select `plex-buffer.sh`.
3. Under **Triggers**, enable **Buffer Warning**.
4. Under **Arguments** for **Buffer Warning**, enter:

```text
{username} "{title}" {buffer_count}
```

5. Under **Conditions**, set **Stream Location** is **wan** to only log remote users.
6. Save and restart Tautulli.

**Example log line:**

```text
2026-04-12 23:05:14 AEST | alice | Inception | Count: 3
```

---

### `plex-chromecast-fix.sh`

Run this a Plex update to fix the issue where casting from iOS to a Chromecast fails for some titles but not all. Plex update restores `Generic.xml` profile which causes this issue. More info in [plex-chromecast-fix.md](plex-chromecast-fix.md).

**What it does:**

- Renames `/usr/lib/plexmediaserver/Resources/Profiles/Generic.xml` to `Generic.xml.old`
- Restarts Plex media server
- If already renamed, prints an "Already disabled" message

**Usage:**

```bash
sudo ./plex-chromecast-fix.sh
```

---

### `plex-qbt-pauser.py`

Designed to pause torrents when remote users are playing in Plex then resume when they finish playing. Skip pausing torrents in certain categories. If any torrents remain active switches on alternative speed limit.

The first run spawns a background worker and then exits (like `nohup`). 

**Dependencies:**

1. Run in script folder: `pip install requests qbittorrent-api`

**Setup:**

1. Edit `plex-qbt-pauser.py` and configure the inline variables at the top of the file:
  - `PLEX_URL` - Plex sessions endpoint URL
  - `QB_HOST` - qBittorrent IP address
  - `QB_PORT` - qBittorrent WebUI port
  - `SKIP_CAT` - Don't pause torrents in this category (use `""` to pause all)
  - `INTERVAL` - Time between checks in seconds
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
/path/to/plex-qbt-pauser.py --restart

# Monitor live logs
tail -f /path/to/plex-qbt-pauser.log  
```

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

### `reboot.sh`

Gracefully stops all running Docker containers, syncs disk buffers, then reboots the system via `systemctl`. Waits for all containers to fully stop before proceeding.

**Usage:**

Run manually or schedule as a daily cron job (e.g., 5:00 AM):

```bash
# Add to root crontab
sudo crontab -e

# Run daily at 05:00
0 5 * * * /path/to/reboot.sh >/dev/null 2>&1
```

---

### `safe-reboot.sh`

Minimal one-liner equivalent of `reboot.sh` — stops all Docker containers then reboots immediately.

**Usage:**

```bash
sudo ./safe-reboot.sh
```

---

### `strip-subtitles.py`

Strips embedded subtitle tracks from video files with `[4K]` in their filename using ffmpeg. Useful for removing unwanted forced subtitle tracks from 4K remuxes.

**Features:**

- Scans a directory recursively or processes a single file
- Only processes files containing `[4K]` in the filename
- Copies video and audio streams unchanged (no re-encode)
- Progress bar per file with tqdm
- Verifies subtitle removal after processing
- Logs to `strip-subtitles.log`

**Dependencies:**

```bash
sudo apt install ffmpeg mediainfo
pip install tqdm
```

**Usage:**

```bash
# Scan a directory
python3 strip-subtitles.py /path/to/media

# Process a single file
python3 strip-subtitles.py /path/to/file.mkv
```

---

### `transcode.py`

Scans a folder (recursively) for video files that will stutter when played via Plex on Apple TV, and transcodes them to a compatible format.

**Detects and fixes:**

- Video: H.264 10-bit (Hi10P), HEVC 10-bit, AV1, VP9 — re-encoded to H.264 8-bit
- Audio: TrueHD, DTS, DTS-HD MA, Dolby Atmos — re-encoded to AC3 640k

Transcoded files are saved alongside originals with a `[transcoded]` suffix. Logs to `transcode.log` in the script directory.

**Dependencies:**

```bash
# Install mediainfo and ffmpeg
sudo apt install mediainfo ffmpeg
```

**Usage:**

```bash
# Scan a folder
python3 transcode.py /path/to/media

# Scan a single file
python3 transcode.py /path/to/file.mkv

# Test mode — transcode first 10 minutes only
python3 transcode.py /path/to/media --test

# Monitor active transcodes
python3 transcode.py --watch
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

1. Install dependencies: `pip install requests rich`
2. Open `test-trackers.py` and optionally configure:
  - `TRACKER_LISTS` - Source URLs to pull potential trackers from.
  - `OUTPUT_FILE` / `LOG_FILE` - Filepaths for output.

**Usage:**

```bash
python3 test-trackers.py
```


---

## License

MIT License. See [LICENSE](LICENSE) for details.
