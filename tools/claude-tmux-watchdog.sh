#!/bin/bash
# Keep a single interactive, Remote-Control-enabled `claude` alive in a detached
# tmux session so it can be driven from the Claude iPhone / web app.
#
# Two cron jobs drive this (see tools/README.md):
#   every 15 min            -> recreate the session if it has crashed/exited
#   daily, --restart        -> recycle the session (kill + recreate)
# Safe to run again either way; flock serialises overlapping runs.

# Cron has a minimal environment; load the paths that hold tmux and the claude binary.
export PATH="/usr/local/bin:/usr/bin:/bin:$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"

SESSION="claude"          # tmux session name  ->  tmux attach -t claude
WORKDIR="$HOME/homelab"   # cwd of the claude session
RC_NAME="Beelink"         # title shown in the Claude app / claude.ai/code session list
LOCK="/tmp/claude-tmux-watchdog.lock"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S %Z') $*"; }

# Serialise overlapping cron runs so two ticks can't race to create the session.
exec 9>"$LOCK"
flock -n 9 || exit 0

# Tools must be present (guards against a broken PATH or an uninstalled binary).
CLAUDE="$(command -v claude)"
if [ -z "$CLAUDE" ] || ! command -v tmux >/dev/null 2>&1; then
    log "ERROR: claude or tmux not found on PATH; not starting"
    exit 1
fi

# Start the detached session. `claude` is the pane's own process (via exec), so when
# it exits the tmux session ends and the next 15-min run recreates it.
#
# --remote-control connects it to the Claude app and gives it a stable, findable name.
# (remoteControlAtStartup=true in ~/.claude/settings.json already auto-connects, but
# passing the flag makes it robust to that setting changing, and names the session.)
# Interactive (not server) mode is used because server mode exits after ~10 min offline.
#
# `9>&-` closes the lock fd for the tmux command: the detached tmux SERVER would
# otherwise inherit fd 9 and hold the flock for the whole life of the session, so every
# later run (and every --restart) would find the lock held and exit without doing
# anything. The lock must outlive only this script run, not the session it starts.
start_session() {
    tmux new-session -d -s "$SESSION" -x 220 -y 50 -c "$WORKDIR" \
        "exec $CLAUDE --remote-control $RC_NAME" 9>&-
    log "started tmux session '$SESSION' in $WORKDIR (Remote Control name: $RC_NAME)"
}

# --restart: recycle the session (kill + recreate). The daily cron uses this because an
# interactive RC session does NOT reliably reconnect after a network drop -- it can sit
# alive at a prompt with every connection gone, unreachable from the app, and the plain
# `has-session` check below can't tell that from healthy. Recycling also picks up the
# binary auto-update (the long-lived process otherwise runs a stale version).
if [ "$1" = "--restart" ]; then
    tmux kill-session -t "$SESSION" 2>/dev/null && log "killed stale tmux session '$SESSION' for --restart"
    start_session
    exit 0
fi

# Default (15-min) run: only recreate a session that is fully gone (crashed/exited).
if tmux has-session -t "$SESSION" 2>/dev/null; then
    exit 0
fi
start_session
