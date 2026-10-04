#!/usr/bin/env bash
#
# recreate-docker.sh — recreate Docker Compose services in bulk.
#
# Discovers every service from a directory of per-service Compose projects
# (one subdirectory per service, each containing a compose file) and takes each
# one `down` then `up -d`. Unlike `docker compose restart`, recreating the
# containers picks up compose changes and current daemon defaults (e.g. logging
# options that only apply at container creation time).
#
# Usage:
#   recreate-docker.sh                 # recreate all discovered services (minus skip list)
#   recreate-docker.sh NAME [NAME...]  # recreate only the named services
#
# Requires Docker Compose v2 (`docker compose`).
set -uo pipefail

# ============================ USER CONFIG ============================
# Directory that holds one subdirectory per Compose service, each with a
# compose file (e.g. ~/docker/radarr/docker-compose.yml). Set this to wherever
# your stacks live.
DOCKER_DIR="$HOME/docker"

# Service names to leave alone during a recreate-all run — e.g. a backup
# website that is normally kept offline. Add names between the parentheses,
# space-separated. Services named explicitly on the command line are always
# recreated, even if listed here. Leave empty to recreate everything.
SKIP=("wordpress")
# ====================================================================

# Recognised compose filenames, in precedence order.
COMPOSE_NAMES=(docker-compose.yml docker-compose.yaml compose.yml compose.yaml)

compose_file() {        # echo the compose file in dir "$1", or nothing
  local d=$1 n
  for n in "${COMPOSE_NAMES[@]}"; do
    [ -f "$d/$n" ] && { echo "$d/$n"; return 0; }
  done
  return 1
}

in_skip() {             # return 0 if service "$1" is in SKIP
  local s=$1 x
  for x in "${SKIP[@]}"; do [ "$s" = "$x" ] && return 0; done
  return 1
}

if [ ! -d "$DOCKER_DIR" ]; then
  echo "error: DOCKER_DIR not found: $DOCKER_DIR" >&2
  exit 1
fi

# Build the work list: named args, or every discovered service when none given.
if [ "$#" -gt 0 ]; then
  all_mode=0
  services=("$@")
else
  all_mode=1
  services=()
  for d in "$DOCKER_DIR"/*/; do
    [ -d "$d" ] || continue
    compose_file "$d" >/dev/null && services+=("$(basename "$d")")
  done
fi

if [ "${#services[@]}" -eq 0 ]; then
  echo "no Compose services found in $DOCKER_DIR" >&2
  exit 1
fi

fail=0
for svc in "${services[@]}"; do
  dir="$DOCKER_DIR/$svc"
  f=$(compose_file "$dir") || { echo "skip: no compose file in $dir" >&2; continue; }

  if [ "$all_mode" -eq 1 ] && in_skip "$svc"; then
    echo "skip: $svc (in skip list)"
    continue
  fi

  printf '== recreating %s ==\n' "$svc"
  if ! docker compose -f "$f" --project-directory "$dir" down || \
     ! docker compose -f "$f" --project-directory "$dir" up -d; then
    echo "  FAILED: $svc" >&2
    fail=1
  fi
done

[ "$fail" -eq 0 ] && echo "done." || echo "done with errors." >&2
exit "$fail"
