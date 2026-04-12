#!/bin/bash

LOG=${LOG:-/scripts/plex-buffer.log}
KEEP_LINES=${KEEP_LINES:-500}
LOCK_DIR="${LOG}.lockdir"
tmp_file=""

mkdir -p "$(dirname "$LOG")"

# Serialize runs: Buffer Warning can fire in bursts and overlap.
while ! mkdir "$LOCK_DIR" 2>/dev/null; do sleep 0.1; done
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true; [ -n "$tmp_file" ] && rm -f "$tmp_file"' EXIT

printf "%s | %s | %s | Count: %s\n" \
    "$(date '+%Y-%m-%d %H:%M:%S %Z')" \
    "${1:-unknown}" \
    "${2:-unknown}" \
    "${3:-0}" >> "$LOG"

# Trim via temp file to avoid reading and writing the same file at once.
tmp_file=$(mktemp "${LOG}.tmp.XXXXXX")
if tail -n "$KEEP_LINES" "$LOG" > "$tmp_file"; then
    # Prefer atomic replace; fall back to overwrite if rename is not supported.
    mv "$tmp_file" "$LOG" 2>/dev/null || {
        cat "$tmp_file" > "$LOG"
        rm -f "$tmp_file"
        tmp_file=""
    }
fi
