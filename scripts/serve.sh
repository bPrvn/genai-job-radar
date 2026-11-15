#!/bin/bash
# Starts the local API against the daily job's database, for the dashboard's live mode.
RUNTIME="${RADAR_RUNTIME:-$HOME/dev/genai-job-radar}"
cd "$RUNTIME/backend" && exec .venv/bin/python -m radar serve "$@"
