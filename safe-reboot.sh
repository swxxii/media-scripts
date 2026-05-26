#!/usr/bin/env bash
set -euo pipefail

containers=$(docker ps -q || true)
if [[ -n "${containers// }" ]]; then
    docker stop $containers >/dev/null 2>&1 || true
    while [[ -n "$(docker ps -q || true)" ]]; do
        sleep 1
    done
fi

sync >/dev/null 2>&1
exec systemctl reboot >/dev/null 2>&1
