#!/bin/bash
# =============================================================================
# backuparr.sh
# =============================================================================
# Description  : Syncs backup zips from Sonarr, Radarr, Prowlarr, Bazarr,
#                qBittorrent config and scripts folder into a cloud-synced
#                directory. Logs are written to backuparr.log next to the
#                script (truncated each run). Docker container data folders
#                are also backed up; containers are stopped before and
#                restarted after each run.
#
# Usage        : Edit configuration variables at the top of this file.
#                Run this script daily or weekly via scheduled cron job.
#
# =============================================================================
# CONFIG - customize as needed
# =============================================================================

# Backup destination - should be synced to google drive or similar
DESTDIR="/mnt/sync/Google/Backups"

# Base folder where each ARR app stores its data
# Appends /[app]/data/Backups/scheduled/ for each app
ARR_BASE="/var/lib"

# ARR-related apps - list of arr apps to back up
ARR_APPS=(sonarr radarr prowlarr)

# Bazarr backup directory
BAZARR_DATA_DIR="/opt/bazarr/data/backup"

# qBittorrent config file
QBITTORRENT_CONF="/home/qbittorrent/.config/qBittorrent/qBittorrent.conf"

# List of containers to stop/start and back up
CONTAINERS=(cleanuparr filebrowser gitea monitor tautulli uptime-kuma wtwp)

# Where compose projects live
DOCKER_BASE_DIR="/home/simon/docker"

# Scripts directory
SCRIPTS_DIR="/home/simon/scripts"

# Log everything to backuparr.log next to this script (overwrite)
set -euo pipefail
LOGFILE="$(dirname "${BASH_SOURCE[0]}")/backuparr.log"
: >"$LOGFILE"

# Log output to logfile only
exec >>"$LOGFILE" 2>&1

# =============================================================================
section() {
    echo
    echo '------------------------------------------------------------'
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo '------------------------------------------------------------'
}

# Perform rsync with optional extra arguments
rsync_job() {
    local src="$1" dest="$2"
    shift 2
    local extra=("$@")
    local flags=("-a" "--delete")
    echo "Backing up $(basename "$dest")..."
    mkdir -p "$dest"
    rsync "${flags[@]}" "${extra[@]}" "$src" "$dest"
}

# =============================================================================
# FOLDER BACKUPS - rsync ARR backups, Bazarr, qBittorrent, and scripts
# =============================================================================
section "Performing folder backups"

# Create destination directories
for app in "${ARR_APPS[@]}"; do
    mkdir -p "$DESTDIR/$app"
done
mkdir -p "$DESTDIR/bazarr"
mkdir -p "$DESTDIR/qbittorrent"
mkdir -p "$DESTDIR/scripts"

# Sync each ARR backup folder
for app in "${ARR_APPS[@]}"; do
    rsync_job "$ARR_BASE/$app/Backups/scheduled/" "$DESTDIR/$app/"
done

# Sync other folders
rsync_job "$BAZARR_DATA_DIR/" "$DESTDIR/bazarr/"
rsync_job "$QBITTORRENT_CONF" "$DESTDIR/qbittorrent/"
rsync_job "$SCRIPTS_DIR/" "$DESTDIR/scripts/" --exclude=pyenv/ --exclude=.git/ --no-links

# =============================================================================
# DOCKER BACKUPS - stop containers, copy data files, start containers
# =============================================================================
manage_containers() {
    local cmd="$1"
    for c in "${CONTAINERS[@]}"; do
        echo "$cmd $c..."
        docker compose -f "$DOCKER_BASE_DIR/$c/docker-compose.yml" "$cmd"
    done
}

if [ ${#CONTAINERS[@]} -gt 0 ]; then
    section "Stopping Docker containers"
    manage_containers stop

    section "Backing up Docker containers"

    # Create container backup directories
    for c in "${CONTAINERS[@]}"; do
        mkdir -p "$DESTDIR/$c"
    done
    for c in "${CONTAINERS[@]}"; do
        rsync_job "$DOCKER_BASE_DIR/$c/" "$DESTDIR/$c/"
    done

    section "Starting Docker containers"
    manage_containers start
fi

# =============================================================================
# FINALIZE and print backup size
# =============================================================================

size=$(du -sh "$DESTDIR" | cut -f1)
section "Backup complete: $size"
