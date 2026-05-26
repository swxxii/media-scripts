#!/bin/bash

MOUNTS=("/mnt/media" "/mnt/sync")

for mount in "${MOUNTS[@]}"; do
    if ! mountpoint -q "$mount" || ! timeout 5 touch "$mount/.mount_test" 2>/dev/null; then
        umount -l "$mount" 2>/dev/null
        mount "$mount"
    else
        rm -f "$mount/.mount_test"
    fi
done
