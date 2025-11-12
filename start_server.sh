#!/bin/bash
# Start the RPi Test Strip Analyzer server

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Kill any existing processes
echo "Cleaning up existing processes..."

# Kill any existing server on port 5000
if lsof -ti:5000 > /dev/null 2>&1; then
    echo "  Killing existing server on port 5000..."
    lsof -ti:5000 | xargs kill -9 2>/dev/null
    sleep 1
fi

# Kill any stray Python server processes
if pgrep -f "server.py" > /dev/null 2>&1; then
    echo "  Killing stray server.py processes..."
    pkill -9 -f "server.py" 2>/dev/null
    sleep 1
fi

# Kill any rpicam processes to free camera
pkill -9 rpicam-vid 2>/dev/null
pkill -9 rpicam-still 2>/dev/null

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
