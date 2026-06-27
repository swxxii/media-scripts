# System Scripts

Scripts for system maintenance, backup automation, and file management.

See [main README](../README.md) for general setup and configuration.

## Scripts

### `backuparr.sh`

Automated backup for Docker containers including Arr services (Sonarr, Radarr, Prowlarr), Bazarr, and other services, plus qBittorrent configuration and scripts folder.

**Features:**
- Writes each backup as a compressed `.tgz` archive into a cloud-synced directory (Google Drive, etc.)
- Docker container data folders (stops and restarts containers around the backup)
- qBittorrent configuration
- Scripts directory (excludes `pyenv` and `.git`)
- Per-container archive excludes (e.g. `MediaCover`, `cache`) to keep archives small
- Verbose logging to `backuparr.log` (truncated each run)

**Setup:**

Edit `../config.yml` and configure:
- `docker_base_dir` - Where your Docker container data/compose files live
- `scripts_dir` - Location of the scripts folder to back up
- `backup_dest_dir` - Where the `.tgz` archives are saved (should be a cloud-synced folder)
- `qbittorrent_conf` - Location of `qBittorrent.conf`

Edit `backuparr.sh` and configure the lists at the top if needed:
- `CONTAINERS` - The list of Docker containers to stop and back up
- `EXCLUDES` - Optional per-container paths to leave out of the archive

**Usage:**
```bash
./backuparr.sh
```

**Cron:** Weekly Sunday at 3 AM

---

### `check-mounts.sh`

Checks that configured mount points are healthy and remounts them if they are stale or unresponsive.

**Features:**
- Tests each mount point with a short `touch` probe (5 second timeout)
- Lazily unmounts and remounts stale/dead mounts automatically
- Cleans up test files on success

**Setup:**

Edit `check-mounts.sh` and set the `MOUNTS` array to list your mount points:
```bash
MOUNTS=("/mnt/media" "/mnt/sync")
```

**Usage:**
```bash
./check-mounts.sh
```

**Cron:** Every 5 minutes

---


### `safe-reboot.sh`

Gracefully stops all running Docker containers (waiting up to 60s for them to stop), lazily unmounts the network mounts (`/mnt/media`, `/mnt/sync`), syncs disk buffers, then reboots the system via `systemctl`.

**Usage:**
```bash
sudo ./safe-reboot.sh
```

---

## Scheduling

All scripts are configured to run automatically via cron:

```bash
# Weekly backup (Sunday 3 AM)
0 3 * * 0 /path/to/scripts/system/backuparr.sh

# Mount checks (every 5 minutes)
*/5 * * * * /path/to/scripts/system/check-mounts.sh
```

