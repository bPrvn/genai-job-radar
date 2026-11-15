#!/bin/bash
# Sets up the daily run (08:30 local time by default; pass HOUR MINUTE to change).
#
# macOS blocks scheduled jobs from reading ~/Desktop, ~/Documents and ~/Downloads, so the
# daily job runs from a clone at ~/dev/genai-job-radar (RADAR_RUNTIME to change). That clone
# holds the database. Keep editing code here, push it, and each daily run pulls it.
#
# Uninstall: launchctl bootout gui/$(id -u)/com.genai-job-radar.daily && rm ~/Library/LaunchAgents/com.genai-job-radar.daily.plist
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME="${RADAR_RUNTIME:-$HOME/dev/genai-job-radar}"
HOUR="${1:-8}"; MINUTE="${2:-30}"
LABEL=com.genai-job-radar.daily
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

REMOTE="$(git -C "$SRC" remote get-url origin)"
if [ ! -d "$RUNTIME/.git" ]; then
  git clone -q "$REMOTE" "$RUNTIME"
else
  git -C "$RUNTIME" pull -q --rebase --autostash
fi

PY="$(command -v python3.12 || ls "$HOME"/.local/share/uv/python/cpython-3.12*/bin/python3.12 2>/dev/null | head -1 || true)"
[ -x "$PY" ] || { echo "Python 3.12 not found. Install it (e.g. uv python install 3.12)"; exit 1; }
[ -d "$RUNTIME/backend/.venv" ] || "$PY" -m venv "$RUNTIME/backend/.venv"
"$RUNTIME/backend/.venv/bin/pip" install -q -r "$RUNTIME/backend/requirements.txt"

# Secrets and an existing database come across once; they are never committed.
[ -f "$SRC/backend/.env" ] && cp "$SRC/backend/.env" "$RUNTIME/backend/.env"
if [ -f "$SRC/data/radar.db" ] && [ ! -f "$RUNTIME/data/radar.db" ]; then
  mkdir -p "$RUNTIME/data" && cp "$SRC/data/radar.db" "$RUNTIME/data/"
fi
mkdir -p "$RUNTIME/data/logs" "$HOME/Library/LaunchAgents"

cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$RUNTIME/scripts/daily.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MINUTE</integer></dict>
  <key>StandardOutPath</key><string>$RUNTIME/data/logs/launchd.log</string>
  <key>StandardErrorPath</key><string>$RUNTIME/data/logs/launchd.log</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
</dict>
</plist>
PL
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Daily run scheduled at $(printf %02d:%02d "$HOUR" "$MINUTE") from $RUNTIME"
echo "Run it now:   launchctl kickstart gui/$(id -u)/$LABEL"
echo "Logs:         $RUNTIME/data/logs/"
