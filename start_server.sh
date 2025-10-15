#!/bin/bash
# Start the RPi Test Strip Analyzer server

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Kill any existing server on port 5000
echo "Checking for existing server on port 5000..."
if lsof -ti:5000 > /dev/null 2>&1; then
    echo "Found existing server, stopping it..."
    lsof -ti:5000 | xargs kill -9 2>/dev/null
    sleep 2
fi

# Activate virtual environment
source venv/bin/activate

# Start the server
echo "Starting RPi Test Strip Analyzer server..."
echo "Server will be available at http://localhost:5000"
echo "Press Ctrl+C to stop"
echo ""

python3 server.py
