# System Scripts

Scripts for system maintenance, backup automation, and file management.

## Dependencies

Bash and standard Linux utilities (no extra packages required).

## Scripts

### `backuparr.sh`

Automated backup for Arr services (Docker & native), Bazarr, qBittorrent, and other Docker containers.

**Features:**
- Arr services: Sonarr, Radarr, Prowlarr (running as Docker containers)
- Bazarr backups
- qBittorrent configuration
- Docker container data folders (stops and restarts containers during backup)
- Syncs all backups to cloud-synced directory (Google Drive, etc.)
- Verbose logging to `backuparr.log`

**Setup:**

Edit `backuparr.sh` and configure the inline variables at the top:
- `DESTDIR` - Where the backups are saved
- `ARR_BASE` - The directory containing native Arr apps (if any)
- `ARR_APPS` - The list of native Arr apps you have installed
- `BAZARR_DATA_DIR` - Location of Bazarr's automated backups
- `QBITTORRENT_CONF` - Location of `qBittorrent.conf`
- `CONTAINERS` - The list of Docker containers you want backed up
- `DOCKER_BASE_DIR` - Where your Docker container data/compose files live
- `SCRIPTS_DIR` - Location of the scripts folder to back up

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
MOUNTS=(
  "/mnt/nfs"
  "/mnt/smb"
  "/mnt/backup"
)
```

**Usage:**
```bash
./check-mounts.sh
```

**Cron:** Every 5 minutes

---

### `permissions.sh`

Sets correct ownership and permissions for media directories and Docker container data folders.

**What it fixes:**
- qBittorrent downloads: `qbittorrent:media`, `777`
- Plex media library: `plex:media`, `777`
- Plex logs: `plex:media`, `775` (allows Tautulli read access)
- Docker container data folders (sonarr, radarr, prowlarr, cleanuparr, filebrowser, tautulli, wordpress, uptime-kuma, gitea)

**Usage:**
```bash
sudo ./permissions.sh
```

Run this occasionally to ensure correct permissions on all media directories.

---

### `safe-reboot.sh`

Gracefully stops all running Docker containers, syncs disk buffers, then reboots the system via `systemctl`. Waits for all containers to fully stop before proceeding.

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

Run permissions and safe-reboot manually as needed.
