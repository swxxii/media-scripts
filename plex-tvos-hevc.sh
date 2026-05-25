#!/bin/bash
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Run as root: sudo ./plex-tvos-hevc.sh"
  exit 1
fi

PROFILE_DIR="/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Profiles"
PROFILE_URL="https://raw.githubusercontent.com/BTerell/plex-appletv-hevc-fix/main/tvOS.xml"
PROFILE_FILE="$PROFILE_DIR/tvOS.xml"

BASE_DIR="/var/lib/plexmediaserver/Library/Application Support/Plex Media Server"
if [ ! -d "$BASE_DIR" ]; then
  echo "Plex data directory not found: $BASE_DIR"
  exit 1
fi

mkdir -p "$PROFILE_DIR"
curl -L "$PROFILE_URL" -o "$PROFILE_FILE"
chown plex:plex "$PROFILE_FILE"
systemctl restart plexmediaserver

echo "Done. Force-quit Plex on Apple TV to reload profile."
