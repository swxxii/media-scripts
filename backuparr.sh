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
CONTAINERS=(cleanuparr filebrowser tautulli uptime-kuma gitea)
# where compose projects live
DOCKER_BASE_DIR="/home/simon/docker"

# scripts directory
SCRIPTS_DIR="/home/simon/scripts"

# log everything to backuparr.log next to this script (overwrite)
LOGFILE="$(dirname "${BASH_SOURCE[0]}")/backuparr.log"
: >"$LOGFILE"
# log output to logfile only
exec >>"$LOGFILE" 2>&1
# -----------------------------------------------------------------------------

# helper: perform rsync with optional extra args
rsync_job() {
    local src="$1" dest="$2" extra="$3" flags="-a --delete"
    if [ "$VERBOSE" = true ]; then
        # only add verbose flag (avoid progress which can produce control chars)
        flags="$flags -v"
    fi
    echo "[>] Backing up $(basename "$dest")..."
    mkdir -p "$dest"
    rsync $flags $extra "$src" "$dest"
}

# -----------------------------------------------------------------------------
# FOLDER BACKUPS - rsync ARR backups, Bazarr, qBittorrent, and scripts
# -----------------------------------------------------------------------------
mkdir -p "$DESTDIR"
echo "[*] Performing folder backups"
# sync each arr backup folder
for app in "${ARR_APPS[@]}"; do
    rsync_job "$ARR_BASE/$app/Backups/scheduled/" "$DESTDIR/$app/"
done
# sync other folders
rsync_job "$BAZARR_DATA_DIR/" "$DESTDIR/bazarr/"
rsync_job "$QBITTORRENT_CONF" "$DESTDIR/qbittorrent/"
rsync_job "$SCRIPTS_DIR/" "$DESTDIR/scripts/" "--exclude=pyenv/ --no-links"

# -----------------------------------------------------------------------------
# DOCKER BACKUPS - stop containers, copy data files, start containers
# -----------------------------------------------------------------------------
manage_containers() {
    local cmd="$1"
    for c in "${CONTAINERS[@]}"; do
        echo "[>] $cmd $c..."
        docker compose -f "$DOCKER_BASE_DIR/$c/docker-compose.yml" $cmd
    done
}

if [ ${#CONTAINERS[@]} -gt 0 ]; then
    echo
    echo "[*] Stopping Docker containers"
    manage_containers stop

    echo
    echo "[*] Backing up Docker containers"
    for c in "${CONTAINERS[@]}"; do
        rsync_job "$DOCKER_BASE_DIR/$c/" "$DESTDIR/$c/"
    done

    echo
    echo "[*] Starting Docker containers"
    manage_containers start
fi

# -----------------------------------------------------------------------------
# FINALIZE and print backup size
# -----------------------------------------------------------------------------

echo

size=$(du -sh "$DESTDIR" | cut -f1)
echo "[+] Backup complete: $size"
