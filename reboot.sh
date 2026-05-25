#!/usr/bin/env bash
# =============================================================================
# reboot.sh
# =============================================================================
# Description : Gracefully stops running Docker containers, then reboots the
#               system.
#
# Cron: as root run `sudo crontab -e` and add this line to run daily at 05:00:
# 0 5 * * * /usr/local/bin/reboot-media >/dev/null 2>&1
# =============================================================================
set -euo pipefail

containers=$(docker ps -q || true)
if [[ -n "${containers// }" ]]; then
    docker stop $containers >/dev/null 2>&1 || true
    # wait until all containers are gone
    while [[ -n "$(docker ps -q || true)" ]]; do
        sleep 1
    done
fi

sync >/dev/null 2>&1
exec systemctl reboot >/dev/null 2>&1
