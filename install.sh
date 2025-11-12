#!/bin/bash
# Installation script for RPi Test Strip Analyzer
# Run with: bash install.sh

set -e

echo "=================================================="
echo "RPi Test Strip Analyzer - Installation Script"
echo "=================================================="
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update system
echo "Step 1: Updating system packages..."
sudo apt update

# Install Python 3 and pip if not present
echo "Step 2: Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "Installing Python 3..."
    sudo apt install -y python3 python3-pip python3-venv
else
    echo "Python 3 already installed: $(python3 --version)"
fi

# Install rpicam-apps if not present
echo "Step 3: Checking rpicam-apps..."
if ! command -v rpicam-still &> /dev/null; then
    echo "Installing rpicam-apps..."
    sudo apt install -y rpicam-apps
else
    echo "rpicam-apps already installed"
fi

# Install Chromium browser for kiosk mode
echo "Step 4: Installing Chromium browser..."
# Try different chromium package names as they vary by distribution
if sudo apt install -y chromium-browser unclutter 2>/dev/null; then
    echo "Chromium browser installed successfully"
elif sudo apt install -y chromium unclutter 2>/dev/null; then
    echo "Chromium installed successfully"
else
    echo "Warning: Could not install chromium-browser. You may need to install it manually."
    echo "Try: sudo apt install chromium"
    echo "Continuing with installation..."
fi

# Create Python virtual environment
echo "Step 5: Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Step 6: Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
echo "Step 7: Creating directories..."
sudo mkdir -p /tmp/captures
sudo chmod 777 /tmp/captures

# Add user to plugdev group for USB access
echo "Step 8: Adding user to plugdev group for USB access..."
if ! groups $USER | grep -q plugdev; then
    sudo usermod -a -G plugdev $USER
    echo "User $USER added to plugdev group (logout/login required for changes to take effect)"
else
    echo "User $USER already in plugdev group"
fi

# Install systemd service
echo "Step 9: Installing systemd service..."
INSTALL_DIR="$(pwd)"
sudo sed "s|INSTALL_DIR|$INSTALL_DIR|g" rpi-analyzer.service.template > /tmp/rpi-analyzer.service
sudo mv /tmp/rpi-analyzer.service /etc/systemd/system/rpi-analyzer.service
sudo systemctl daemon-reload
sudo systemctl enable rpi-analyzer.service

# Install kiosk mode autostart
echo "Step 10: Setting up kiosk mode..."
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/rpi-analyzer-kiosk.desktop << EOF
[Desktop Entry]
Type=Application
Name=RPi Analyzer Kiosk
Exec=$INSTALL_DIR/start_kiosk.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF

# Make scripts executable
chmod +x start_server.sh
chmod +x start_kiosk.sh

echo ""
echo "=================================================="
echo "Installation Complete!"
echo "=================================================="
echo ""
echo "To start the server manually:"
echo "  bash start_server.sh"
echo ""
echo "To start in kiosk mode:"
echo "  bash start_kiosk.sh"
echo ""
echo "To enable auto-start on boot:"
echo "  sudo systemctl start rpi-analyzer"
echo ""
echo "To check service status:"
echo "  sudo systemctl status rpi-analyzer"
echo ""
echo "The application will be available at:"
echo "  http://localhost:5000"
echo ""
echo "=================================================="
