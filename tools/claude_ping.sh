#!/bin/bash
# Cron has a heavily restricted environment, so we load common paths to ensure it finds the 'claude' binary
export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"

LOG="$HOME/claude_cron.log"

# -p runs Claude as a single-shot headless command
# < /dev/null prevents the CLI from hanging and waiting for stdin piped input
echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') =====" >> "$LOG"
# Use Haiku, not the default (Opus): a heartbeat ping needs the cheapest model.
# Opus weighs many times a Haiku token against the 5-hour quota. Auth stays on
# the subscription (OAuth); --bare would drop the ~35k system prompt but forces
# API-key auth, so it's not usable here.
claude -p "Hi" --model claude-haiku-4-5-20251001 < /dev/null >> "$LOG" 2>&1

# Cap log at last 100 lines (atomic temp + rename)
tail -n 100 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
