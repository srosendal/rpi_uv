# RPi Test Strip Analyzer - Deployment Guide

## Overview

Web-based test strip analyzer for Raspberry Pi with camera streaming, OpenCV analysis, and USB auto-save.

**Key Features:**
- Real-time camera streaming (406x304)
- Full-resolution native camera capture for analysis
- Configurable photo count (default: 2 photos)
- Photo averaging for accuracy
- HSV color detection with OpenCV
- USB auto-save with local fallback
- Touch-friendly interface
- PWM LED control (GPIO12)

---

## Quick Installation

### Fresh Raspberry Pi Setup

Run these commands on your Raspberry Pi:

```bash
# Download the deployment script
wget https://raw.githubusercontent.com/srosendal/rpi_uv/main/deploy_rpi_uv.sh -O deploy_rpi_uv.sh

# Make it executable
chmod +x deploy_rpi_uv.sh

# Run the installation
bash deploy_rpi_uv.sh
```

This will automatically:
- Check prerequisites
- Install all dependencies
- Set up the application
- Add user to necessary groups (gpio, plugdev)
- Start the application in kiosk mode

**Installation time:** ~5-10 minutes

---

## Updating the Software

When updates are available, simply run:

```bash
bash deploy_rpi_uv.sh
```

Choose **"yes"** when prompted to remove and reinstall for a fresh installation.

---

## Manual Installation (Alternative Method)

If you prefer manual control:

```bash
# Clone the repository
git clone https://github.com/srosendal/rpi_uv.git
cd rpi_uv

# Run installation
chmod +x install.sh
bash install.sh
```

---

## Starting the Application

### Option 1: Kiosk Mode (Full Screen)
```bash
# From home directory
bash rpi_uv/start_kiosk.sh
```

### Option 2: Server Only
```bash
bash start_server.sh
```

Access at: `http://localhost:5000` (on RPi) or `http://raspberrypi.local:5000` (from network)

### Exiting the Application

**Option 1: Using the Exit Button (Recommended)**
- Click the **"Exit"** button in the top-right corner of the interface
- Confirm the shutdown when prompted
- The system will safely:
  - Set PWM duty cycle to 0%
  - Stop all camera processes
  - Clean up GPIO resources
  - Shut down the server

**Option 2: Keyboard Shortcuts**
- **To exit kiosk mode:** Press `Ctrl+W`
- **To stop the server:** Press `Ctrl+C` in the terminal

After exiting, you can restart the application by running:
```bash
bash rpi_uv/start_kiosk.sh
```

---

## Configuration

### Application Settings

Settings are stored in `config.json` and can be configured through the web interface:

- **Number of Photos:** 1-5 (default: 2)
- **Startup Delay:** 0.5-5.0 seconds (default: 1.0s)
- **Capture Delay:** 0.5-5.0 seconds (default: 1.0s)
- **Save Location:** Local directory or USB path
- **PWM Duty Cycle:** 0-100% (default: 60%)

### Region of Interest (ROI) Setup

1. Click **"Settings Mode"**
2. Select ROI (1-4)
3. Use arrows to position over test strips
4. Click **"Save Config"**

### HSV Color Detection

Edit thresholds in `hsv_analyzer.py` (lines 20-25):

```python
HSV_LOWER = np.array([H_min, S_min, V_min])
HSV_UPPER = np.array([H_max, S_max, V_max])
```

**Quick presets:**
- Red: `[0, 100, 100]` to `[10, 255, 255]`
- Blue: `[100, 100, 100]` to `[130, 255, 255]`
- Purple: `[130, 50, 50]` to `[160, 255, 255]`
- All colors: `[0, 80, 80]` to `[179, 255, 255]`

**Test calibration:**
```bash
python3 hsv_analyzer.py
# View debug_hsv_analysis.png
```

---

## Understanding Results

Results show **pixel counts** of detected color in each ROI. The system automatically scales ROIs from streaming resolution (406x304) to capture resolution for accurate analysis.

**Example results:**
```
ROI 1: 21107 pixels
ROI 2: 220 pixels
ROI 3: 60 pixels
ROI 4: 0 pixels
```

**Interpretation:**
- High (>30,000): Very strong band
- Medium (10,000-30,000): Moderate band
- Low (<10,000): Weak band
- Zero: No band detected

---

## USB Storage

The system automatically:
1. Detects available USB drives
2. Attempts to save photos and results to USB
3. Falls back to local directory (`~/rpi_uv_photos_backup/`) if USB is unavailable or permission denied

---

## Enable Auto-Start (Optional)

To start the application automatically on boot:

```bash
sudo systemctl enable rpi-analyzer
sudo reboot
```

System starts automatically in kiosk mode after reboot.

---

## Useful Commands

### Server Management
```bash
# Manual start
bash start_server.sh

# Kiosk mode
bash start_kiosk.sh

# Service control
sudo systemctl start/stop/restart rpi-analyzer
sudo systemctl status rpi-analyzer

# View logs
journalctl -u rpi-analyzer -f
```

### Camera Testing
```bash
# List cameras
rpicam-still --list-cameras

# Test capture
rpicam-still -o test.jpg -n --timeout 1000
```

### GPIO/PWM Testing
```bash
# Check if user is in gpio group
groups

# Test RPi.GPIO in virtual environment
source venv/bin/activate
python3 -c "import RPi.GPIO; print('RPi.GPIO version:', RPi.GPIO.VERSION)"
```

---

## Troubleshooting

**Camera not working:**
```bash
rpicam-still --list-cameras
sudo raspi-config  # Enable camera
```

**Server won't start:**
```bash
cd ~/rpi_uv && source venv/bin/activate && python3 server.py
# Check error messages
```

**GPIO/PWM not available:**
```bash
# Ensure RPi.GPIO is installed in virtual environment
source venv/bin/activate
pip install RPi.GPIO

# Check user is in gpio group
groups

# If not in gpio group, re-run installation
bash install.sh
```

**Wrong colors detected:**
- Edit `hsv_analyzer.py` thresholds (lines 20-25)
- Run `python3 hsv_analyzer.py` to test
- View `debug_hsv_analysis.png`

**USB not saving:**
- Check if USB is mounted: `ls /media/`
- System automatically falls back to `~/rpi_uv_photos_backup/`
- Check permissions: User should be in `plugdev` group

**Port 5000 already in use:**
```bash
# The startup scripts automatically clean up existing processes
# If issues persist, manually kill:
lsof -ti:5000 | xargs kill -9
```

---

## System Architecture

```
┌─────────────────────┐
│   Web Browser       │  ← User Interface (406x304 streaming)
│  (localhost:5000)   │
└──────────┬──────────┘
           │ HTTP/SSE
           ↓
┌─────────────────────┐
│   Flask Server      │  ← API & Camera Control
│    (server.py)      │  ← PWM LED Control (GPIO12)
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    ↓             ↓
┌─────────┐  ┌──────────────┐
│ Camera  │  │ HSV Analyzer │  ← OpenCV Processing
│ Stream  │  │ (hsv_analyzer│
│ 406x304 │  │     .py)     │
└─────────┘  └──────────────┘
    ↓             ↓
┌─────────┐  ┌──────────────┐
│Capture  │  │   Analysis   │
│Native   │  │   Results    │
│ Full    │  │  (photo      │
│  Res    │  │   average)   │
└─────────┘  └──────────────┘
    ↓             ↓
┌─────────────────────┐
│   Save to USB or    │  ← Photos + JSON
│   Local Backup      │
└─────────────────────┘
```

---

## File Structure

```
rpi_uv/
├── server.py                 # Flask backend with PWM control
├── hsv_analyzer.py           # OpenCV analysis
├── requirements.txt          # Dependencies (includes RPi.GPIO)
├── config.json               # Configuration persistence
├── install.sh                # Installation script
├── deploy_rpi_uv.sh          # One-click deployment
├── start_server.sh           # Server-only start
├── start_kiosk.sh            # Kiosk mode start
├── rpi-analyzer.service.template  # Auto-start service
├── DEPLOYMENT_GUIDE.md       # This file
├── photos/                   # Local photo storage
└── static/                   # Web interface
    ├── index.html
    ├── css/style.css
    └── js/
        ├── app.js
        ├── image-analyzer.js
        └── roi-manager.js
```

---

## Version Info

**Version:** 1.0.3  
**Date:** November 2025

**Recent Updates:**
- Streaming: 406x304 resolution
- Capture: Native full camera resolution
- Configurable photo count (1-5, default: 2)
- Configurable delays (0.5-5.0s, default: 1.0s)
- USB save with automatic local fallback
- PWM LED control on GPIO12
- Streamlined process cleanup
- User automatically added to gpio and plugdev groups

---

## Production Checklist

- [ ] Camera tested (`rpicam-still --list-cameras`)
- [ ] ROIs positioned correctly
- [ ] HSV thresholds calibrated
- [ ] Test captures give expected results
- [ ] GPIO available (check startup logs)
- [ ] PWM duty cycle configured
- [ ] USB saving works (or local fallback confirmed)
- [ ] Auto-start enabled (if desired)
