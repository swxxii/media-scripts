#!/bin/bash
# =============================================================================
# backuparr.sh
# =============================================================================
# Description  : Backs up Docker container data folders, qBittorrent config,
#                and scripts folder as compressed .tgz archives in a
#                cloud-synced directory. Containers are stopped before backup
#                and restarted after. Logs are written to backuparr.log next to
#                the script (truncated each run).
#
# Usage        : Edit configuration variables at the top of this file.
#                Run this script daily or weekly via scheduled cron job.
#
# =============================================================================
# CONFIG - customize as needed
# =============================================================================

# Backup destination - should be synced to google drive or similar
DESTDIR="/mnt/sync/Google/Backups"

# qBittorrent config file
QBITTORRENT_CONF="/home/qbittorrent/.config/qBittorrent/qBittorrent.conf"

# List of containers to stop/start and back up
CONTAINERS=(sonarr radarr prowlarr cleanuparr filebrowser gitea tautulli uptime-kuma signal-api monitor bazarr)

# Per-container archive excludes (relative to the container's data folder)
declare -A EXCLUDES=(
    ["radarr"]="config/MediaCover"
    ["sonarr"]="config/MediaCover"
    ["tautulli"]="cache"
)

# Read personal paths from config.yml
_CONFIG="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../config.yml"
DOCKER_BASE_DIR="$(python3 -c "import yaml; c=yaml.safe_load(open('$_CONFIG')); print(c['docker_base_dir'])")"
SCRIPTS_DIR="$(python3 -c "import yaml; c=yaml.safe_load(open('$_CONFIG')); print(c['scripts_dir'])")"

# Log everything to backuparr.log next to this script (overwrite)
set -euo pipefail
LOGFILE="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/backuparr.log"
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

# Create a .tgz archive of a source folder/file with optional extra tar args
tar_job() {
    local src="$1" dest_tgz="$2"
    shift 2
    local extra=("$@")
    echo "Backing up $(basename "$dest_tgz")..."
    mkdir -p "$(dirname "$dest_tgz")"
    tar -czf "$dest_tgz" "${extra[@]}" \
        -C "$(dirname "${src%/}")" "$(basename "${src%/}")"
}

# =============================================================================
# FOLDER BACKUPS - archive qBittorrent and scripts
# =============================================================================
section "Performing folder backups"

mkdir -p "$DESTDIR"

tar_job "$QBITTORRENT_CONF" "$DESTDIR/qbittorrent.tgz"
tar_job "$SCRIPTS_DIR/" "$DESTDIR/scripts.tgz" --exclude='pyenv' --exclude='.git'

# =============================================================================
# DOCKER BACKUPS - stop containers, archive data folders, start containers
# =============================================================================
if [ ${#CONTAINERS[@]} -gt 0 ]; then
    section "Stopping Docker containers"
    for c in "${CONTAINERS[@]}"; do
        echo "Stopping $c..."
        docker compose -f "$DOCKER_BASE_DIR/$c/docker-compose.yml" stop
    done

    # Wait for all containers to stop
    echo "Waiting for containers to stop..."
    for c in "${CONTAINERS[@]}"; do
        timeout 30 bash -c "while docker compose -f \"$DOCKER_BASE_DIR/$c/docker-compose.yml\" ps --services --filter status=running | grep -q .; do sleep 0.5; done"
    done

    section "Backing up Docker containers"

    # Archive each container's data folder into a .tgz
    for c in "${CONTAINERS[@]}"; do
        if [ -n "${EXCLUDES[$c]:-}" ]; then
            tar_job "$DOCKER_BASE_DIR/$c/" "$DESTDIR/$c.tgz" --exclude="${EXCLUDES[$c]}"
        else
            tar_job "$DOCKER_BASE_DIR/$c/" "$DESTDIR/$c.tgz"
        fi
    done

    section "Starting Docker containers"
    for c in "${CONTAINERS[@]}"; do
        echo "Starting $c..."
        docker compose -f "$DOCKER_BASE_DIR/$c/docker-compose.yml" start
    done

    # Wait for all containers to start
    echo "Waiting for containers to start..."
    for c in "${CONTAINERS[@]}"; do
        timeout 30 bash -c "while ! docker compose -f \"$DOCKER_BASE_DIR/$c/docker-compose.yml\" ps --services --filter status=running | grep -q .; do sleep 0.5; done"
    done
fi

# =============================================================================
# FINALIZE and print backup size
# =============================================================================

size=$(du -sh "$DESTDIR" | cut -f1)
section "Backup complete: $size"
