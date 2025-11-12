#!/bin/bash
# Start the application in kiosk mode (fullscreen Chromium browser)

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Kill any existing processes
echo "Cleaning up existing processes..."

# Kill processes on port 5000
lsof -ti:5000 | xargs kill -9 2>/dev/null || true

# Kill server.py processes
pkill -9 -f "server.py" 2>/dev/null || true

# Kill chromium processes
pkill -9 -f "chromium" 2>/dev/null || true
pkill -9 chromium-browser 2>/dev/null || true

# Kill rpicam processes
pkill -9 rpicam-vid 2>/dev/null || true
pkill -9 rpicam-still 2>/dev/null || true

# Wait for processes to fully terminate
sleep 2

# Clean up Chromium resources to prevent stack smashing errors
echo "Cleaning up Chromium resources..."

# Remove Chromium lock files
rm -f ~/.config/chromium/SingletonLock 2>/dev/null || true
rm -f ~/.config/chromium/SingletonSocket 2>/dev/null || true
rm -f ~/.config/chromium/SingletonCookie 2>/dev/null || true

# Clean up shared memory (common cause of Chromium crashes)
rm -rf /dev/shm/.org.chromium.* 2>/dev/null || true
rm -rf /dev/shm/pulse-shm-* 2>/dev/null || true

# Clear Chromium cache to prevent corruption issues
rm -rf ~/.cache/chromium/Default/Cache/* 2>/dev/null || true
rm -rf ~/.cache/chromium/Default/Code\ Cache/* 2>/dev/null || true

# Additional wait for resource cleanup
sleep 1

echo "Cleanup complete!"

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

# Retry logic for Chromium startup (handles stack smashing and other crashes)
MAX_CHROMIUM_RETRIES=3
CHROMIUM_RETRY=0
CHROMIUM_SUCCESS=false

while [ $CHROMIUM_RETRY -lt $MAX_CHROMIUM_RETRIES ] && [ "$CHROMIUM_SUCCESS" = "false" ]; do
    if [ $CHROMIUM_RETRY -gt 0 ]; then
        echo "Chromium crashed, retrying ($((CHROMIUM_RETRY + 1))/$MAX_CHROMIUM_RETRIES)..."
        
        # Clean up crashed Chromium processes
        pkill -9 -f "chromium" 2>/dev/null || true
        pkill -9 chromium-browser 2>/dev/null || true
        
        # Additional cleanup for retry
        rm -rf /dev/shm/.org.chromium.* 2>/dev/null || true
        rm -f ~/.config/chromium/SingletonLock 2>/dev/null || true
        
        sleep 2
    fi
    
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
    
    CHROMIUM_PID=$!
    
    # Wait a bit to see if Chromium crashes immediately
    sleep 3
    
    # Check if Chromium is still running
    if ps -p $CHROMIUM_PID > /dev/null 2>&1; then
        echo "Chromium started successfully!"
        CHROMIUM_SUCCESS=true
        # Wait for Chromium to exit normally
        wait $CHROMIUM_PID
    else
        echo "Chromium failed to start or crashed immediately"
        CHROMIUM_RETRY=$((CHROMIUM_RETRY + 1))
    fi
done

if [ "$CHROMIUM_SUCCESS" = "false" ]; then
    echo "Error: Chromium failed to start after $MAX_CHROMIUM_RETRIES attempts"
    exit 1
fi
