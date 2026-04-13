#!/bin/bash
# -----------------------------------------------------------------------------
# backuparr.sh
# ----------------------------------------------------------------------------
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
# -----------------------------------------------------------------------------
# CONFIG - customize as needed
# -----------------------------------------------------------------------------
# verbose mode adds `-v` to rsync and shows live output to the console
VERBOSE=true

# backup destination - should be synced to google drive or similar
DESTDIR="/mnt/sync/Google/Backups"

# base folder where each ARR app stores its data
ARR_BASE="/var/lib" #/[app]/data/Backups/scheduled/ will be appended
# ARR-related apps - list of arr apps to back up
ARR_APPS=(sonarr radarr prowlarr)
# bazarr backup dir (different to others for some reason)
BAZARR_DATA_DIR="/opt/bazarr/data/backup"
# qBittorrent config file
QBITTORRENT_CONF="/home/qbittorrent/.config/qBittorrent/qBittorrent.conf"

# list of containers to stop/start and back up
CONTAINERS=(cleanuparr filebrowser gitea monitor tautulli uptime-kuma wtwp)
# where compose projects live
DOCKER_BASE_DIR="/home/simon/docker"

# scripts directory
SCRIPTS_DIR="/home/simon/scripts"

# log everything to backuparr.log next to this script (overwrite)
set -euo pipefail
IFS=$'\n\t'
LOGFILE="$(dirname "${BASH_SOURCE[0]}")/backuparr.log"
: >"$LOGFILE"
# log output to logfile only
exec >>"$LOGFILE" 2>&1
# -----------------------------------------------------------------------------

log() {
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    printf '[%s] %s\n' "$timestamp" "$*"
}

# helper: perform rsync with optional extra args
rsync_job() {
    local src="$1" dest="$2"
    shift 2
    local extra=("$@")
    local flags=("-a" "--delete")
    if [ "$VERBOSE" = true ]; then
        flags+=("-v")
    fi
    log "[>] Backing up $(basename "$dest")..."
    mkdir -p "$dest"
    rsync "${flags[@]}" "${extra[@]}" "$src" "$dest"
}

# -----------------------------------------------------------------------------
# FOLDER BACKUPS - rsync ARR backups, Bazarr, qBittorrent, and scripts
# -----------------------------------------------------------------------------
log "[*] Performing folder backups"
for app in "${ARR_APPS[@]}"; do
    mkdir -p "$DESTDIR/$app"
done
mkdir -p "$DESTDIR/bazarr"
mkdir -p "$DESTDIR/qbittorrent"
mkdir -p "$DESTDIR/scripts"

# sync each arr backup folder
for app in "${ARR_APPS[@]}"; do
    rsync_job "$ARR_BASE/$app/Backups/scheduled/" "$DESTDIR/$app/"
done
# sync other folders
rsync_job "$BAZARR_DATA_DIR/" "$DESTDIR/bazarr/"
rsync_job "$QBITTORRENT_CONF" "$DESTDIR/qbittorrent/"
rsync_job "$SCRIPTS_DIR/" "$DESTDIR/scripts/" --exclude=pyenv/ --exclude=.git/ --no-links

# -----------------------------------------------------------------------------
# DOCKER BACKUPS - stop containers, copy data files, start containers
# -----------------------------------------------------------------------------
manage_containers() {
    local cmd="$1"
    for c in "${CONTAINERS[@]}"; do
        log "[>] $cmd $c..."
        docker compose -f "$DOCKER_BASE_DIR/$c/docker-compose.yml" "$cmd"
    done
}

if [ ${#CONTAINERS[@]} -gt 0 ]; then
    echo
    log "[*] Stopping Docker containers"
    manage_containers stop

    echo
    log "[*] Backing up Docker containers"
    # ensure container backup directories exist
    for c in "${CONTAINERS[@]}"; do
        mkdir -p "$DESTDIR/$c"
    done
    for c in "${CONTAINERS[@]}"; do
        rsync_job "$DOCKER_BASE_DIR/$c/" "$DESTDIR/$c/"
    done

    echo
    log "[*] Starting Docker containers"
    manage_containers start
fi

# -----------------------------------------------------------------------------
# FINALIZE and print backup size
# -----------------------------------------------------------------------------

echo

size=$(du -sh "$DESTDIR" | cut -f1)
log "[+] Backup complete: $size"
