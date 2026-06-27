# media-scripts

Utility scripts for media servers, backup automation, and file management.

## Documentation

- **[plex/README.md](plex/README.md)** — Plex-specific scripts and configuration
- **[system/README.md](system/README.md)** — System maintenance and backup automation
- **[tools/README.md](tools/README.md)** — Utility tools for file management and testing

## Folder Structure

```
scripts/
├── plex/              # Plex-related scripts
├── system/            # System maintenance scripts
├── tools/             # Utility tools
├── config.yml         # Configuration (gitignored, not in repo)
└── config.example.yml # Template configuration file
```

## Dependencies

Before running the scripts, make sure to install the required system utilities and Python dependencies.

### 1. Python Packages

Install all required Python dependencies via `pip`:

```bash
pip install requests pyyaml qbittorrent-api tqdm python-whois dnspython english-words rich
```

### 2. System Utilities

Some tools (like subtitle stripping) require external command line utilities:

```bash
# Debian/Ubuntu systems
sudo apt install ffmpeg mediainfo
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
- `qbittorrent_port` — Your qBittorrent WebUI port (optional, default: `8081`)
- `qbittorrent_skip_category` — Category to skip pausing (optional, default: `"force"`)
- `qbittorrent_polling_interval` — Interval in seconds to check Plex sessions (optional, default: `30`)

**Paths:**
- `plexmeta_output_dir` — Where plexmeta exports library metadata
- `docker_base_dir` — Where your Docker compose projects/container data live
- `scripts_dir` — The path to this scripts directory (`/path/to/scripts`)
- `backup_dest_dir` — Where `backuparr.sh` saves the compressed `.tgz` archives
- `qbittorrent_conf` — Path to your `qBittorrent.conf` configuration file


## Scheduling Scripts

Most scripts run automatically via cron.

### 1. User Crontab (for Plex/user scripts)

Edit your user crontab:
```bash
crontab -e
```

Copy and paste these lines (replace `/path/to/scripts` with your installation path):
```bash
# Export Plex metadata via Tautulli - daily 2 AM
0 2 * * * /usr/bin/python3 /path/to/scripts/plex/plexmeta.py >> /path/to/scripts/plex/plexmeta.log 2>&1

# Ensure plex-playback-monitor daemon is running - every hour
0 * * * * /usr/bin/python3 /path/to/scripts/plex/plex-playback-monitor.py >> /path/to/scripts/plex/plex-playback-monitor.log 2>&1
```

**View your user crontab:**
```bash
crontab -l
```

### 2. Root Crontab (for system scripts requiring root privileges)

Edit the root crontab:
```bash
sudo crontab -e
```

Copy and paste these lines (replace `/path/to/scripts` with your installation path):
```bash
# Backup Arr services and Docker containers - weekly Sunday 3 AM
# (writes its own backuparr.log next to the script)
0 3 * * 0 /path/to/scripts/system/backuparr.sh

# Check network mounts - every 5 minutes
*/5 * * * * /path/to/scripts/system/check-mounts.sh
```

**View your root crontab:**
```bash
sudo crontab -l
```

## License

MIT License. See [LICENSE](LICENSE) for details.
