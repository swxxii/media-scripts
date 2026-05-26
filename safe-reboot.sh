#!/usr/bin/env bash
set -euo pipefail

containers=$(docker ps -q || true)
if [[ -n "${containers// }" ]]; then
    docker stop --time 30 $containers >/dev/null 2>&1 || true
    waited=0
    while [[ -n "$(docker ps -q || true)" && $waited -lt 60 ]]; do
        sleep 1
        ((waited++))
    done
fi

umount -l /mnt/media /mnt/sync 2>/dev/null || true

sync >/dev/null 2>&1
exec systemctl reboot >/dev/null 2>&1
