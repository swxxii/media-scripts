# Plex Scripts

Scripts for managing Plex media server, monitoring playback, and automating tasks.

## Dependencies

```bash
pip install requests qbittorrent-api
```

## Scripts

### `plexmeta.py`

Exports Plex library to CSV and JSON metadata via Tautulli API so you have a backup of what was in Plex if you lose everything (e.g. NAS failure).

**Features:**
- Queries Tautulli for all library sections
- Triggers CSV and JSON exports for each section
- Polls until exports complete
- Downloads exports files to a local folder
- Cleans up server-side exports

**Setup:**
1. Edit `../config.yml` and configure:
   - `tautulli_url` - Tautulli server URL
   - `tautulli_api_key` - Your Tautulli API key
   - `plexmeta_output_dir` - Folder to save exported CSVs/JSONs

**Usage:**
```bash
python3 plexmeta.py
```

**Cron:** Daily at 2 AM

---

### `plex-qbt-pauser.py`

Pause torrents when remote users are playing in Plex, then resume when they finish. Skip pausing torrents in certain categories. If any torrents remain active, switches on alternative speed limit.

The first run spawns a background worker and then exits (like `nohup`).

**Setup:**
1. Edit `../config.yml` and configure:
   - `plex_url` - Your Plex server address
   - `plex_token` *(Plex Web → library item → Get Info → View XML → copy `X-Plex-Token` from URL)*
   - `qbittorrent_host` - qBittorrent server IP
   - `qbittorrent_username` / `password` - Your qBittorrent credentials
   - `qbittorrent_port` - qBittorrent WebUI port (optional, default: 8081)
   - `qbittorrent_skip_category` - Category to skip pausing (optional, default: "force")
   - `qbittorrent_polling_interval` - Check interval in seconds (optional, default: 30)

**Usage:**
```bash
# Run directly (spawns background worker)
python3 plex-qbt-pauser.py

# Restart the script
python3 plex-qbt-pauser.py --restart

# Monitor live logs
tail -f plex-qbt-pauser.log
```

**Cron:** Every hour (ensures daemon stays running)

---

### `plex-buffer.sh`

Tautulli notification trigger script for logging buffering events so you can review who buffered, what title, and how many times.

**Config:**
- `LOG` - Log file path (default: script directory)
- `KEEP_LINES` - Maximum number of log lines to keep (default: `500`)

**Tautulli Setup:**
1. Go to **Settings → Notification Agents → Add → Script**
2. Set **Script Folder** to this directory and select `plex-buffer.sh`
3. Under **Triggers**, enable **Buffer Warning**
4. Under **Arguments**, enter: `{username} "{title}" {buffer_count}`
5. Under **Conditions**, set **Stream Location** is **wan** to only log remote users
6. Save and restart Tautulli

**Example log line:**
```
2026-04-12 23:05:14 AEST | alice | Inception | Count: 3
```

---

### `plex-chromecast-fix.sh`

Fix Chromecast casting issues on Plex. Run after each Plex update.

**What it does:**
- Renames `/usr/lib/plexmediaserver/Resources/Profiles/Generic.xml` to `Generic.xml.old`
- Restarts Plex media server

See [plex-chromecast-fix.md](plex-chromecast-fix.md) for more details.

**Usage:**
```bash
sudo ./plex-chromecast-fix.sh
```

---

### `movie-folders.sh`

Organize movie files into individual folders for Plex compatibility.

**Features:**
- Moves video files (mkv, mp4, avi, mpeg4, mpg, divx) into their own folders
- Consolidates companion files (subtitles, nfo, etc.) with each movie
- Cleans up small/empty folders (< 90MB)
- Progress logging

**Setup:**
1. Edit `movie-folders.sh` and set the `src` variable to your target directory

**Usage:**
```bash
./movie-folders.sh
```

⚠️ CAUTION: This script uses destructive cleanup (`rm -rf`) for empty folders.
