#!/bin/bash
# Daily job: pull latest code -> scrape -> update DB -> AI brief -> publish snapshot (GitHub Pages).
# Run by launchd (scripts/install-schedule.sh) from the ~/dev clone; safe to run by hand.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/data/logs"; mkdir -p "$LOG_DIR"
exec >>"$LOG_DIR/daily-$(date +%F).log" 2>&1
echo "=== $(date) ==="

cd "$ROOT"
git pull -q --rebase --autostash || echo "git pull failed, running current code"
backend/.venv/bin/pip install -q -r backend/requirements.txt || true

cd "$ROOT/backend"
.venv/bin/python -m radar run || { echo "pipeline failed"; exit 1; }

cd "$ROOT"
git add frontend/public/data/snapshot.json
if git diff --cached --quiet; then
  echo "snapshot unchanged"
else
  git commit -q -m "Daily snapshot $(date +%F)" && git push -q origin main && echo "published"
fi
find "$LOG_DIR" -name 'daily-*.log' -mtime +30 -delete
