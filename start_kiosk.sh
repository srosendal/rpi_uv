#!/bin/bash
# Start the application in kiosk mode (fullscreen Chromium browser)

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Start the server in background
echo "Starting server..."
cd "$SCRIPT_DIR"
bash start_server.sh &
SERVER_PID=$!

# Wait for server to be ready (check if port 5000 is responding)
echo "Waiting for server to be ready..."
MAX_ATTEMPTS=30
ATTEMPT=0
while ! curl -s http://localhost:5000 > /dev/null 2>&1; do
    sleep 1
    ATTEMPT=$((ATTEMPT+1))
    if [ $ATTEMPT -ge $MAX_ATTEMPTS ]; then
        echo "Error: Server failed to start after 30 seconds"
        echo "Check if port 5000 is already in use or if there are errors in start_server.sh"
        exit 1
    fi
    echo "  Attempt $ATTEMPT/$MAX_ATTEMPTS..."
done

echo "Server is ready!"

# Hide mouse cursor
unclutter -idle 0.1 &

# Detect which chromium command is available (newer OS uses 'chromium', older uses 'chromium-browser')
if command -v chromium &> /dev/null; then
    BROWSER="chromium"
elif command -v chromium-browser &> /dev/null; then
    BROWSER="chromium-browser"
else
    echo "Error: Neither chromium nor chromium-browser found!"
    echo "Install with: sudo apt install chromium-browser"
    exit 1
fi

echo "Starting kiosk mode with $BROWSER..."

# Start Chromium in kiosk mode
$BROWSER \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-translate \
    --disable-features=TranslateUI \
    --disk-cache-dir=/dev/null \
    --password-store=basic \
    --disable-pinch \
    --overscroll-history-navigation=0 \
    --disable-session-crashed-bubble \
    http://localhost:5000
