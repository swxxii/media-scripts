#!/bin/bash

# Simple post-update Plex fix: disable Generic.xml and restart Plex.

set -e

if [ "$EUID" -ne 0 ]; then
  echo "Run as root: sudo ./plex-chromecast-fix.sh"
  exit 1
fi

generic_file="/usr/lib/plexmediaserver/Resources/Profiles/Generic.xml"
generic_old="${generic_file}.old"

if [ -f "$generic_file" ]; then
  mv "$generic_file" "$generic_old"
  echo "Renamed: $generic_file -> $generic_old"
elif [ -f "$generic_old" ]; then
  echo "Already disabled: $generic_old"
  exit 0
else
  echo "Not found: $generic_file"
  exit 1
fi

systemctl restart plexmediaserver
echo "Plex restarted."
