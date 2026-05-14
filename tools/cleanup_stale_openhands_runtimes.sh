#!/usr/bin/env bash
#
# Prune stale OpenHands agent-server containers.
#
# OpenHands spawns one `oh-agent-server-*` container per app-conversation.
# When a conversation ends, the container is left in a "Paused" state and
# still holds memory/cpu. After ~25 paused runtimes the openhands-app
# orchestrator becomes unresponsive (took 60s+ to answer a simple search;
# eventually OOM'd during the ProbePilot Sprint 4 work).
#
# This script removes:
#   - all `oh-agent-server-*` containers in "Paused" state, regardless of age
#   - additionally, any `oh-agent-server-*` whose status string contains
#     "hours" (i.e. older than 1 hour) — except the most recent N, which
#     might be the one OpenHands is about to attach to
#
# `openhands-app` itself is never touched.
#
# Usage:
#   tools/cleanup_stale_openhands_runtimes.sh         # default: keep 4 newest
#   tools/cleanup_stale_openhands_runtimes.sh --all   # remove every paused/old runtime
#   tools/cleanup_stale_openhands_runtimes.sh --keep 8
#   tools/cleanup_stale_openhands_runtimes.sh --dry-run
#
# Safe to run while ForgeLoop is idle. Avoid running it while a ForgeLoop
# `openhands/execute` call is in flight — it may remove the runtime the
# orchestrator just spawned.

set -e -o pipefail

KEEP=4
DRY_RUN=0
ALL=0

while [ $# -gt 0 ]; do
  case "$1" in
    --keep)    KEEP="$2"; shift 2 ;;
    --all)     ALL=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '1,/^set -e/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not on PATH" >&2
  exit 2
fi

# Compute removal list via python for portability — macOS ships bash 3.2,
# which lacks `mapfile`. Python is on $PATH everywhere ForgeLoop runs.
INVENTORY=$(docker ps -a --filter "name=oh-agent-server-" \
  --format '{{.Names}}|{{.Status}}|{{.CreatedAt}}')

TOTAL_FOUND=$(printf '%s\n' "$INVENTORY" | grep -c . || true)
echo "found $TOTAL_FOUND oh-agent-server containers"

if [ "$TOTAL_FOUND" -eq 0 ]; then
  exit 0
fi

# Write python script to a temp file so heredoc and stdin don't fight on
# macOS bash 3.2 (where python3 - <<EOF and piped stdin both want stdin).
PY_SCRIPT="$(mktemp -t fl_cleanup_oh.XXXXXX.py)"
trap 'rm -f "$PY_SCRIPT"' EXIT
cat >"$PY_SCRIPT" <<'PY'
import sys
keep = int(sys.argv[1])
all_mode = sys.argv[2] == "1"
rows = []
for line in sys.stdin:
    line = line.rstrip("\n")
    if not line: continue
    parts = line.split("|", 2)
    while len(parts) < 3: parts.append("")
    rows.append(tuple(parts))
rows.sort(key=lambda r: r[2])  # oldest first

def is_stale(status):
    s = status or ""
    return any(t in s for t in ("Paused", "Exited", "Dead", "Restarting", "hours", "days", "weeks"))

to_remove = []
keep_count = 0
for name, status, _ in reversed(rows):  # newest first to honour --keep
    if all_mode:
        to_remove.append(name); continue
    if is_stale(status):
        if keep_count < keep:
            keep_count += 1
            continue
        to_remove.append(name)
for n in to_remove:
    print(n)
PY
removal_plan=$(printf '%s\n' "$INVENTORY" | python3 "$PY_SCRIPT" "$KEEP" "$ALL")

to_remove=()
while IFS= read -r line; do
  [ -z "$line" ] && continue
  to_remove+=("$line")
done <<< "$removal_plan"

if [ "${#to_remove[@]}" -eq 0 ]; then
  echo "nothing to remove (kept ${keep_count} stale, KEEP=${KEEP})"
  exit 0
fi

echo "will remove ${#to_remove[@]} stale runtime(s):"
printf '  %s\n' "${to_remove[@]}"

if [ "$DRY_RUN" = 1 ]; then
  echo "(dry-run; no docker rm executed)"
  exit 0
fi

for name in "${to_remove[@]}"; do
  docker rm -f "$name" >/dev/null && echo "  removed: $name" || echo "  failed:  $name"
done

echo "done. Remaining agent-server containers:"
docker ps -a --filter "name=oh-agent-server-" --format '  {{.Names}}\t{{.Status}}'
