# RPi Test Strip Analyzer - Deployment Guide

## Overview

Web-based test strip analyzer for Raspberry Pi with camera streaming, OpenCV analysis, and USB auto-save.

**Key Features:**
- Real-time camera streaming (432x324)
- Full-resolution capture (2592x1944) for analysis
- 3-photo averaging for accuracy
- HSV color detection with OpenCV
- USB auto-save
- Touch-friendly interface

---

## Quick Deployment

### 1. Transfer Files to RPi

```bash
# From your computer
scp -r rpi/ pi@raspberrypi.local:~/
```

### 2. Install

```bash
ssh pi@raspberrypi.local
cd ~/rpi
chmod +x install.sh
bash install.sh
```

Installation includes Python, camera software, dependencies, and systemd service setup (~5-10 min).

### 3. Start Server

```bash
bash start_server.sh
```

Access at: `http://localhost:5000` (on RPi) or `http://raspberrypi.local:5000` (from network)

### 4. Configure ROIs (Region of Interest)

1. Click **"Settings Mode"**
2. Select ROI (1-4)
3. Use arrows to position over test strips
4. Click **"Save Config"**

### 5. Enable Auto-Start (Optional)

```bash
sudo systemctl enable rpi-analyzer
sudo reboot
```

System starts automatically in kiosk mode after reboot.

---

## Configuration Files

### Camera Settings (`server.py`)

```python
STREAM_WIDTH = 432    # Streaming resolution
STREAM_HEIGHT = 324   # (Faster performance)

# Full native resolution used for capture/analysis
```

### HSV Color Detection (`hsv_analyzer.py`)

Lines 20-25:
```python
HSV_LOWER = np.array([H_min, S_min, V_min])
HSV_UPPER = np.array([H_max, S_max, V_max])
```

**Quick presets (uncomment in file):**
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

Results show **pixel counts** of detected color in each ROI:

```
ROI 1: 4519 pixels  (Strong band - ~75% of ROI)
ROI 2: 2471 pixels  (Moderate band - ~41%)
ROI 3: 2452 pixels  (Moderate band - ~41%)
ROI 4: 2409 pixels  (Moderate band - ~40%)
```

**ROI area:** 150×324 = 48,600 pixels max

**Interpretation:**
- High (>30,000): Very strong band
- Medium (10,000-30,000): Moderate band
- Low (<10,000): Weak band
- Zero: No band detected

---

## Quick Updates

When updating code (no need to reinstall):

```bash
# From your computer
scp rpi/server.py pi@raspberrypi.local:~/rpi/server.py
scp rpi/static/index.html pi@raspberrypi.local:~/rpi/static/index.html
scp rpi/static/js/app.js pi@raspberrypi.local:~/rpi/static/js/app.js

# On RPi
sudo systemctl restart rpi-analyzer
# OR if running manually: Ctrl+C and bash start_server.sh
```

---

## Useful Commands

### Server Management
```bash
# Manual start
bash start_server.sh

# Service control
sudo systemctl start/stop/restart rpi-analyzer
sudo systemctl status rpi-analyzer

# View logs (console only, file logging disabled)
journalctl -u rpi-analyzer -f
```

### Camera Testing
```bash
# List cameras
rpicam-still --list-cameras

# Test capture
rpicam-still -o test.jpg -n --timeout 1000
```

### Kiosk Mode
```bash
# Start kiosk
bash start_kiosk.sh

# Exit kiosk
pkill chromium
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
cd ~/rpi && source venv/bin/activate && python3 server.py
# Check error messages
```

**Wrong colors detected:**
- Edit `hsv_analyzer.py` thresholds (lines 20-25)
- Run `python3 hsv_analyzer.py` to test
- View `debug_hsv_analysis.png`

**USB not saving:**
```bash
ls /media/pi/  # Check if USB mounted
```

---

## System Architecture

```
┌─────────────────────┐
│   Web Browser       │  ← User Interface (432x324 display)
│  (localhost:5000)   │
└──────────┬──────────┘
           │ HTTP
           ↓
┌─────────────────────┐
│   Flask Server      │  ← API & Camera Control
│    (server.py)      │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    ↓             ↓
┌─────────┐  ┌──────────────┐
│ Camera  │  │ HSV Analyzer │  ← OpenCV Processing
│ Stream  │  │ (hsv_analyzer│
│ 432x324 │  │     .py)     │
└─────────┘  └──────────────┘
    ↓             ↓
┌─────────┐  ┌──────────────┐
│Capture  │  │   Analysis   │
│Full Res │  │   Results    │
│2592x1944│  │  (3-photo    │
│         │  │   average)   │
└─────────┘  └──────────────┘
    ↓             ↓
┌─────────────────────┐
│   USB Auto-Save     │  ← Photos + JSON
│  /media/pi/USB/     │
└─────────────────────┘
```

---

## File Structure

```
rpi/
├── server.py                 # Flask backend
├── hsv_analyzer.py           # OpenCV analysis
├── requirements.txt          # Dependencies
├── install.sh                # Installation script
├── start_server.sh           # Manual start
├── start_kiosk.sh            # Kiosk mode
├── rpi-analyzer.service.template  # Auto-start
├── DEPLOYMENT_GUIDE.md       # This file
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
**Client:** Meka Innovation Pte Ltd  
**Date:** October 2025

**Recent Updates:**
- Streaming: 432x324 @ 500ms timeout
- Capture: Native resolution (2592x1944)
- File logging disabled (console only)
- Simplified documentation

---

## Production Checklist

- [ ] Camera tested (`rpicam-still --list-cameras`)
- [ ] ROIs positioned correctly
- [ ] HSV thresholds calibrated
- [ ] Test captures give expected results
- [ ] USB saving works (if needed)
- [ ] Auto-start enabled (if desired)
