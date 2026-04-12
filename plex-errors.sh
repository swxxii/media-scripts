#!/bin/bash
grep -rih -A 5 -B 5 "13.transcode\|error" "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Logs/"
