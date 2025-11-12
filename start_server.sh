#!/bin/bash
# Start the RPi Test Strip Analyzer server

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

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

# Activate virtual environment
source venv/bin/activate

# Start the server
echo "Starting RPi Test Strip Analyzer server..."
echo "Server will be available at http://localhost:5000"
echo "Press Ctrl+C to stop"
echo ""

python3 server.py
