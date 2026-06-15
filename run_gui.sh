#!/bin/bash
# ── CPA Traffic Bot — GUI Launcher ──────────────────────────────
# Automatically uses the correct Python virtual environment.
# Usage: bash run_gui.sh  (or: chmod +x run_gui.sh && ./run_gui.sh)

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PYTHON="$DIR/venv/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "❌ Virtual environment not found at: $PYTHON"
    echo "   Run: python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
fi

exec "$PYTHON" gui.py "$@"
