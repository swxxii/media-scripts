# media-scripts

Utility scripts for media servers, backup automation, and file management.

## Folder Structure

```
scripts/
├── plex/              # Plex-related scripts
├── system/            # System maintenance scripts
├── tools/             # Utility tools
└── config.yml         # Configuration (gitignored, not in repo)
```

## Setup

### 1. Clone the repository

```bash
git clone <repo-url> ~/scripts
cd ~/scripts
```

### 2. Create config.yml

```bash
cp config.example.yml config.yml
```

Open `config.yml` and fill in your values:

**Plex:**
- `plex_token` — From Plex Web: library → item → Get Info → View XML → copy `X-Plex-Token` from URL
- `plex_url` — Your Plex server address (e.g., `http://YOUR_SERVER_IP:32400`)

**Tautulli:**
- `tautulli_api_key` — From Tautulli: Settings → API
- `tautulli_url` — Your Tautulli server address

**qBittorrent:**
- `qbittorrent_username` — Your qBittorrent WebUI username
- `qbittorrent_password` — Your qBittorrent WebUI password
- `qbittorrent_host` — Your qBittorrent server IP

**Paths:**
- `plexmeta_output_dir` — Where plexmeta exports metadata
- `docker_base_dir` — Where your Docker compose projects live
- `scripts_dir` — This directory (`/path/to/scripts`)

### 3. Install dependencies

**Python packages:**
```bash
pip install requests qbittorrent-api rich tqdm
```

**System packages** (if using strip-subtitles.py):
```bash
sudo apt install ffmpeg mediainfo
```

### 4. Review folder READMEs

Each folder has additional setup instructions:
- [plex/README.md](plex/README.md) — Plex-specific configuration
- [system/README.md](system/README.md) — System script setup
- [tools/README.md](tools/README.md) — Utility tool usage

## Scheduling Scripts

Most scripts run automatically via cron. Before setting up cron, ensure:
1. `config.yml` is configured (Step 2 above)
2. Dependencies are installed (Step 3 above)

### Add to Crontab

Edit your crontab:
```bash
crontab -e
```

Copy and paste these lines (replace `/path/to/scripts` with your installation path):
```bash
# Backup Arr services and Docker containers - weekly Sunday 3 AM
0 3 * * 0 /path/to/scripts/system/backuparr.sh >> /path/to/scripts/system/backuparr.log 2>&1

# Export Plex metadata via Tautulli - daily 2 AM
0 2 * * * /usr/bin/python3 /path/to/scripts/plex/plexmeta.py >> /path/to/scripts/plex/plexmeta.log 2>&1

# Check network mounts - every 5 minutes
*/5 * * * * /path/to/scripts/system/check-mounts.sh

# Ensure plex-qbt-pauser daemon is running - every hour
0 * * * * /usr/bin/python3 /path/to/scripts/plex/plex-qbt-pauser.py >> /path/to/scripts/plex/plex-qbt-pauser.log 2>&1
```

**View your crontab:**
```bash
crontab -l
```

## License

MIT License. See [LICENSE](LICENSE) for details.
