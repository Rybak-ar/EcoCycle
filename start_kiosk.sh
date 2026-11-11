#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR" || exit 1

# Prevent duplicate instances
if pgrep -f "index.py" > /dev/null; then
    exit 0
fi

sleep 4

# Check again after sleep in case both launched simultaneously
if pgrep -f "index.py" > /dev/null; then
    exit 0
fi

# Activate virtual environment
if [ -f "$PROJECT_DIR/../env/bin/activate" ]; then
    source "$PROJECT_DIR/../env/bin/activate"
elif [ -f "$HOME/projects/env/bin/activate" ]; then
    source "$HOME/projects/env/bin/activate"
elif [ -f "$PROJECT_DIR/env/bin/activate" ]; then
    source "$PROJECT_DIR/env/bin/activate"
fi

export DISPLAY="${DISPLAY:-:0}"
if [ -z "$WAYLAND_DISPLAY" ] && [ -e "$XDG_RUNTIME_DIR/wayland-0" ]; then
    export WAYLAND_DISPLAY="wayland-0"
fi

LOG_FILE="$PROJECT_DIR/kiosk.log"
echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] Starting EcoCycle Pro Kiosk ===" >> "$LOG_FILE"
echo "User: $USER, Python: $(which python3)" >> "$LOG_FILE"

exec python3 index.py >> "$LOG_FILE" 2>&1
