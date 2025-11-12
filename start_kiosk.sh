#!/bin/bash
# Start the application in kiosk mode (fullscreen Chromium browser)

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Kill any existing processes
echo "Cleaning up existing processes..."

# Kill any existing server on port 5000 (try multiple times)
echo "  Killing existing server on port 5000..."
lsof -ti:5000 | xargs kill -9 2>/dev/null || true
sleep 1
# Second attempt to ensure cleanup
lsof -ti:5000 | xargs kill -9 2>/dev/null || true

# Kill any stray Python server processes (multiple passes)
echo "  Killing stray server.py processes..."
pkill -9 -f "server.py" 2>/dev/null || true
sleep 1
# Second pass to catch any lingering processes
pkill -9 -f "server.py" 2>/dev/null || true

# Kill any stray Chromium browser processes (multiple passes)
echo "  Killing stray chromium processes..."
pkill -9 -f "chromium" 2>/dev/null || true
pkill -9 chromium-browser 2>/dev/null || true
sleep 1
# Second pass to ensure cleanup
pkill -9 -f "chromium" 2>/dev/null || true
pkill -9 chromium-browser 2>/dev/null || true

# Kill any rpicam processes to free camera (multiple attempts)
pkill -9 rpicam-vid 2>/dev/null || true
pkill -9 rpicam-still 2>/dev/null || true
sleep 1
# Second pass to ensure camera is freed
pkill -9 rpicam-vid 2>/dev/null || true
pkill -9 rpicam-still 2>/dev/null || true

echo "Cleanup complete!"
sleep 1

# Start the server in background
echo "Starting server..."
cd "$SCRIPT_DIR"
bash start_server.sh &
SERVER_PID=$!

# Set up cleanup trap to kill server when script exits
trap "echo 'Stopping server...'; kill $SERVER_PID 2>/dev/null" EXIT

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
# Redirect stderr to suppress harmless Chromium warnings
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
    --disable-gpu \
    --disable-software-rasterizer \
    --disable-dev-shm-usage \
    --disable-background-networking \
    --disable-sync \
    --metrics-recording-only \
    --disable-default-apps \
    --mute-audio \
    --no-pings \
    --no-crash-upload \
    http://localhost:5000 2>&1 | grep -v -E '(disk_cache|cache|EGL|eglCreateContext|GPU|gpu|texStorage2D|ANGLE|google_apis|gcm|registration_request)' &

# Wait for Chromium (it's now in background due to the pipe)
wait
