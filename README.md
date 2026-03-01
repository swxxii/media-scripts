# media-scripts

Utility scripts for media servers, backup automation, and file management.

## Scripts

### `backuparr.sh`

Automated backup utility for \*Arr services and Docker containers.

**Features:**

- Existing backup zips from Sonarr, Radarr, and Prowlarr and Bazarr
- qBittorrent configuration
- Docker container data folders (stops and restarts containers)
- Syncs all backups to cloud-synced directory (Google Drive, etc.)
- Verbose logging to `backuparr.log`

**Setup:**
Edit configuration variables at the top of the script:

- `DESTDIR` - backup destination (recommend to cloud sync)
- `ARR_BASE` - Base directory for \*Arr applications
- `ARR_APPS` - List of apps to backup, will be appended to base
- `CONTAINERS` - Docker containers to backup
- `DOCKER_BASE_DIR` - Folder that docker data folders are inside
- `SCRIPTS_DIR` - Scripts directory to backup

**Usage:** Run daily or weekly via cron

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
# Preview changes
python3 media-extensions.py /path/to/files --dry-run

# Restore extensions
python3 media-extensions.py /path/to/files
```

---

### `movie-folders.sh`

Organizes movie files into individual folders for Plex compatibility.

**Features:**

- Moves video files (mkv, mp4, avi, mpeg4, mpg, divx) into their own folders
- Consolidates companion files (subtitles, nfo, etc.) with each movie
- Cleans up small/empty folders (&lt; 90MB)
- Progress logging

**Setup:**
Edit the `src` variable to point to your movies directory:

```bash
src=/volume1/Media/movies
```

**Usage:** Run once to organize existing folder

```bash
./movie-folders.sh
```

**⚠️ Warning:** Uses `rm -rf` for folder cleanup—use with caution!

---

### `plexmeta.py`

Exports Plex library metadata via Tautulli API.

**Features:**

- Queries Tautulli for all library sections
- Triggers CSV and JSON exports for each section
- Polls until exports complete
- Downloads exports files to a local folder
- Cleans up server-side exports

**Setup:**
Edit configuration at the top of the script:

- `TAUTULLI` - Tautulli server URL and port
- `API_KEY` - Tautulli API key (from Tautulli settings)
- `OUTPUT_DIR` - Local directory for exports

**Usage:**

```bash
python3 plexmeta.py
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

**Configuration:**
Edit variables at the top of the script:

- `TRACKER_LISTS` - URLs of tracker lists to fetch
- `OUTPUT_FILE` - Output filename for valid trackers
- `LOG_FILE` - Log file for detailed results

**Usage:**

```bash
python3 test-trackers.py
```

Output: `valid_trackers.txt` - List of working trackers ready for use

---

## Notes

- All scripts include configuration sections at the top—edit before running
- Update scripts to match your configuration