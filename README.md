# media-scripts

Utility scripts for media servers, backup automation, and file management.

## Folder Structure

```
scripts/
├── plex/              # Plex-related scripts
├── system/            # System maintenance scripts
├── tools/             # Utility tools
└── secrets.yml        # Credentials (create from secrets.example.yml)
```

## Setup

1. **Clone the repository:**
   ```bash
   git clone <repo-url> ~/scripts
   cd ~/scripts
   ```

2. **Configure secrets:**
   ```bash
   cp secrets.example.yml secrets.yml
   # Edit secrets.yml and add your credentials
   ```

3. **Review each folder's README** for script-specific setup:
   - [plex/README.md](plex/README.md) - Plex server scripts
   - [system/README.md](system/README.md) - System maintenance
   - [tools/README.md](tools/README.md) - Utility tools

## Automation

Scripts are configured to run automatically via cron.

### Add to Crontab

Edit your crontab:
```bash
crontab -e
```

Add these lines (replace `~/scripts` with your installation path):
```bash
# Backup Arr services and Docker containers - weekly Sunday 3 AM
0 3 * * 0 ~/scripts/system/backuparr.sh >> ~/scripts/system/backuparr.log 2>&1

# Export Plex metadata via Tautulli - daily 2 AM
0 2 * * * /usr/bin/python3 ~/scripts/plex/plexmeta.py >> ~/scripts/plex/plexmeta.log 2>&1

# Check network mounts - every 5 minutes
*/5 * * * * ~/scripts/system/check-mounts.sh

# Ensure plex-qbt-pauser daemon is running - every hour
0 * * * * /usr/bin/python3 ~/scripts/plex/plex-qbt-pauser.py >> ~/scripts/plex/plex-qbt-pauser.log 2>&1
```

Save and exit (in nano: `Ctrl+O`, `Enter`, `Ctrl+X`).

### View Crontab

Check your configured cron jobs:
```bash
crontab -l
```

## Quick Reference

### Plex Scripts
- **plexmeta.py** - Export Plex library metadata
- **plex-qbt-pauser.py** - Pause torrents during Plex playback
- **plex-buffer.sh** - Log Plex buffer events (Tautulli integration)
- **plex-chromecast-fix.sh** - Fix Chromecast casting issues
- **movie-folders.sh** - Organize movies into folders

### System Scripts
- **backuparr.sh** - Backup Arr services and containers
- **check-mounts.sh** - Check and remount network shares
- **permissions.sh** - Fix media directory permissions
- **safe-reboot.sh** - Gracefully reboot with container shutdown

### Tools
- **media-extensions.py** - Restore file extensions from magic bytes
- **strip-subtitles.py** - Remove subtitle tracks from 4K files
- **test-trackers.py** - Test BitTorrent tracker availability

## License

MIT License. See [LICENSE](LICENSE) for details.
