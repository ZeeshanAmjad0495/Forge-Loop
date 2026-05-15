#!/usr/bin/env bash
#
# Install the OpenHands runtime reaper as a macOS LaunchAgent.
#
# Why a copied script instead of running it from the repo:
# launchd agents cannot read files under ~/Documents without Full Disk
# Access (macOS TCC). So we copy cleanup_stale_openhands_runtimes.sh to
# ~/Library/Application Support/forgeloop/ (not TCC-protected for the
# user's own agents) and point the LaunchAgent there. The repo copy
# under tools/ stays the canonical, reviewable source.
#
# Idempotent: re-running re-copies the script and reloads the agent.
#
# Usage: tools/install_oh_reaper.sh   (uninstall: tools/install_oh_reaper.sh --uninstall)

set -e -o pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_SUPPORT="$HOME/Library/Application Support/forgeloop"
LA_DIR="$HOME/Library/LaunchAgents"
PLIST_DST="$LA_DIR/ai.forgeloop.oh-reaper.plist"
LABEL="ai.forgeloop.oh-reaper"

if [ "${1:-}" = "--uninstall" ]; then
  launchctl unload "$PLIST_DST" 2>/dev/null || true
  rm -f "$PLIST_DST"
  echo "uninstalled $LABEL"
  exit 0
fi

mkdir -p "$APP_SUPPORT" "$LA_DIR"
install -m 0755 "$REPO_DIR/cleanup_stale_openhands_runtimes.sh" \
  "$APP_SUPPORT/cleanup_stale_openhands_runtimes.sh"

# Materialise the plist from the template with the real home path.
sed "s|__HOME__|$HOME|g" "$REPO_DIR/ai.forgeloop.oh-reaper.plist" > "$PLIST_DST"
plutil -lint "$PLIST_DST" >/dev/null

launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load -w "$PLIST_DST"

echo "installed $LABEL"
echo "  script:  $APP_SUPPORT/cleanup_stale_openhands_runtimes.sh"
echo "  plist:   $PLIST_DST"
echo "  cadence: every 1800s, --keep 6, log /tmp/forgeloop_oh_reaper.log"
launchctl list "$LABEL" 2>/dev/null | grep -E '"Label"|LastExitStatus' || true
