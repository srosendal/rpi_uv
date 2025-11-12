#!/usr/bin/env python3
"""
Raspberry Pi Test Strip Analyzer - Flask Backend
Simple and reliable camera streaming and capture
"""

import os
import subprocess
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, Response, jsonify, send_from_directory, request
from flask_cors import CORS
import base64
from hsv_analyzer import HSVAnalyzer

# Try to import RPi.GPIO for PWM control
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger = logging.getLogger('RPiAnalyzer')
    logger.warning("RPi.GPIO not available - PWM control disabled. This is normal if not running on a Raspberry Pi.")

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# Configuration
STREAM_WIDTH = 406
STREAM_HEIGHT = 304
CAPTURE_WIDTH = 4056  # Native camera resolution
CAPTURE_HEIGHT = 3040
PHOTOS_DIR = Path('photos')
CAPTURE_DIR = Path('/tmp/captures')

# Coordinate scaling factors for ROI mapping
SCALE_FACTOR_X = CAPTURE_WIDTH / STREAM_WIDTH   # ~9.99
SCALE_FACTOR_Y = CAPTURE_HEIGHT / STREAM_HEIGHT  # 10.0

# Create directories
PHOTOS_DIR.mkdir(exist_ok=True)
CAPTURE_DIR.mkdir(exist_ok=True)
LOG_DIR = Path('logs')
LOG_DIR.mkdir(exist_ok=True)

# Set up logging
# Uncomment the lines below to enable file logging to logs/rpi_analyzer.log
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler(LOG_DIR / 'rpi_analyzer.log'),
#         logging.StreamHandler()
#     ]
# )
# For now, only console logging is enabled
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('RPiAnalyzer')

# Simple global state
streaming_active = False
capture_in_progress = False
mjpeg_process = None

# Configuration file path
CONFIG_FILE = Path('config.json')

# PWM configuration
PWM_GPIO_PIN = 12  # GPIO12 (PWM0)
PWM_FREQUENCY = 1000  # 1 kHz
pwm_instance = None


def load_config():
    """Load configuration from config.json"""
    default_config = {
        "num_photos": 2,
        "startup_delay": 1.0,
        "capture_delay": 1.0,
        "save_location": "photos",
        "pwm_duty_cycle": 60,
        "camera_command": "rpicam-still",
        "rois": [
            {"id": 1, "x": 117, "y": 89, "width": 141, "height": 19},
            {"id": 2, "x": 117, "y": 136, "width": 141, "height": 19},
            {"id": 3, "x": 117, "y": 183, "width": 141, "height": 19},
            {"id": 4, "x": 117, "y": 230, "width": 141, "height": 19}
        ]
    }
    
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Merge with defaults to ensure all keys exist
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            # Create default config file
            save_config(default_config)
            return default_config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return default_config


def save_config(config):
    """Save configuration to config.json"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info("Configuration saved")
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False


def init_pwm(duty_cycle=60):
    """Initialize PWM on GPIO12"""
    global pwm_instance
    
    if not GPIO_AVAILABLE:
        logger.warning("GPIO not available, skipping PWM initialization")
        return False
    
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PWM_GPIO_PIN, GPIO.OUT)
        pwm_instance = GPIO.PWM(PWM_GPIO_PIN, PWM_FREQUENCY)
        pwm_instance.start(duty_cycle)
        logger.info(f"PWM initialized on GPIO{PWM_GPIO_PIN} at {duty_cycle}% duty cycle")
        return True
    except Exception as e:
        logger.error(f"Error initializing PWM: {e}")
        return False


def set_pwm_duty_cycle(duty_cycle):
    """Set PWM duty cycle (0-100%)"""
    global pwm_instance
    
    if not GPIO_AVAILABLE or pwm_instance is None:
        logger.warning("PWM not available")
        return False
    
    try:
        duty_cycle = max(0, min(100, duty_cycle))  # Clamp to 0-100
        pwm_instance.ChangeDutyCycle(duty_cycle)
        logger.info(f"PWM duty cycle set to {duty_cycle}%")
        return True
    except Exception as e:
        logger.error(f"Error setting PWM duty cycle: {e}")
        return False


def cleanup_pwm():
    """Cleanup GPIO on exit"""
    global pwm_instance
    
    if GPIO_AVAILABLE and pwm_instance is not None:
        try:
            pwm_instance.stop()
            GPIO.cleanup()
            logger.info("PWM cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up PWM: {e}")


# Load configuration at startup
app_config = load_config()

# Initialize PWM with configured duty cycle
if GPIO_AVAILABLE:
    init_pwm(app_config.get('pwm_duty_cycle', 60))


def stream_capture(output_path, timeout_ms=500):
    """
    Fast camera capture for streaming - lower resolution, balanced timeout
    Returns True if successful, False otherwise
    """
    try:
        cmd = [
            'rpicam-still',
            '-o', str(output_path),
            '--width', str(STREAM_WIDTH),
            '--height', str(STREAM_HEIGHT),
            '--timeout', str(timeout_ms),
            '--nopreview',
            '-n',
            '--rotation', '0'      # Force no rotation to prevent orientation issues
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0 and output_path.exists():
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"Stream capture error: {e}")
        return False


def analysis_capture(output_path, timeout_ms=2000, camera_command=None):
    """
    High quality camera capture for analysis - full native resolution
    Returns True if successful, False otherwise
    """
    try:
        logger.info(f"Capturing full resolution to: {output_path}")
        
        # Use configured camera command if not provided
        if camera_command is None:
            camera_command = app_config.get('camera_command', 'rpicam-still')
        
        # Build command - split the camera_command in case it has arguments
        cmd_parts = camera_command.split()
        cmd = cmd_parts + [
            '-o', str(output_path),
            # No width/height - use native resolution
            '--timeout', str(timeout_ms),
            '--nopreview',
            '-n'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and output_path.exists():
            logger.info(f"Capture successful")
            return True
        else:
            logger.error(f"Capture failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Capture error: {e}")
        return False


def find_usb_drives():
    """Find mounted USB drives"""
    usb_drives = []
    for mount_base in ['/media', '/mnt']:
        mount_path = Path(mount_base)
        if mount_path.exists():
            for item in mount_path.iterdir():
                if item.is_dir() and item.name not in ['cdrom', 'floppy']:
                    try:
                        test_file = item / '.write_test'
                        test_file.touch()
                        test_file.unlink()
                        usb_drives.append(str(item))
                    except:
                        pass
    return usb_drives


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/stream/start', methods=['POST'])
def start_stream():
    global streaming_active
    streaming_active = True
    logger.info("Streaming started")
    return jsonify({'status': 'streaming'})


@app.route('/api/stream/stop', methods=['POST'])
def stop_stream():
    global streaming_active, mjpeg_process
    streaming_active = False
    
    # Kill MJPEG process if running
    if mjpeg_process:
        try:
            mjpeg_process.terminate()
            mjpeg_process.wait(timeout=2)
        except:
            try:
                mjpeg_process.kill()
            except:
                pass
        mjpeg_process = None
    
    # Also kill any stray rpicam-vid processes
    try:
        subprocess.run(['pkill', '-9', 'rpicam-vid'], capture_output=True)
    except:
        pass
    
    logger.info("Streaming stopped")
    time.sleep(0.2)  # Brief pause
    return jsonify({'status': 'stopped'})


def generate_mjpeg_stream():
    """
    Generator function for MJPEG streaming using rpicam-vid
    Yields JPEG frames continuously
    """
    global mjpeg_process, streaming_active
    
    try:
        # Start rpicam-vid process for continuous JPEG streaming
        cmd = [
            'rpicam-vid',
            '--width', str(STREAM_WIDTH),
            '--height', str(STREAM_HEIGHT),
            '--timeout', '0',  # Run indefinitely
            '--nopreview',
            '--codec', 'mjpeg',
            '--inline',
            '--flush',
            '--framerate', '15',  # Limit framerate to reduce memory usage
            '--rotation', '0',
            '-o', '-'  # Output to stdout
        ]
        
        mjpeg_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=10**8
        )
        
        logger.info("MJPEG stream started with rpicam-vid")
        
        # Read and yield JPEG frames
        while streaming_active and mjpeg_process and mjpeg_process.poll() is None:
            # Read frame header (look for JPEG start marker)
            chunk = mjpeg_process.stdout.read(2)
            if not chunk or len(chunk) != 2:
                break
            
            # Check for JPEG start marker (0xFF 0xD8)
            if chunk[0] == 0xFF and chunk[1] == 0xD8:
                frame_data = chunk
                
                # Read until JPEG end marker (0xFF 0xD9)
                while True:
                    byte = mjpeg_process.stdout.read(1)
                    if not byte:
                        break
                    frame_data += byte
                    
                    # Check for JPEG end marker
                    if len(frame_data) >= 2 and frame_data[-2] == 0xFF and frame_data[-1] == 0xD9:
                        # Yield complete JPEG frame
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
                        break
            
            # Don't stream during capture
            if capture_in_progress:
                time.sleep(0.1)
                
    except Exception as e:
        logger.error(f"MJPEG stream error: {e}")
    finally:
        if mjpeg_process:
            mjpeg_process.terminate()
            mjpeg_process.wait()
            mjpeg_process = None


@app.route('/stream')
def video_stream():
    """MJPEG video stream endpoint"""
    global streaming_active
    
    if not streaming_active:
        return "Stream not active", 503
    
    return Response(
        generate_mjpeg_stream(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/api/stream/frame', methods=['GET'])
def get_frame():
    """Legacy endpoint - kept for compatibility but deprecated"""
    global streaming_active, capture_in_progress
    
    # Don't stream during capture
    if capture_in_progress or not streaming_active:
        return jsonify({'success': False, 'error': 'Not streaming'}), 503
    
    # Capture a frame to temp file
    temp_path = CAPTURE_DIR / f'stream_{time.time()}.jpg'
    
    if stream_capture(temp_path, timeout_ms=500):
        try:
            with open(temp_path, 'rb') as f:
                frame_data = f.read()
            temp_path.unlink()
            
            # Encode as base64
            frame_b64 = base64.b64encode(frame_data).decode('utf-8')
            return jsonify({
                'success': True,
                'image': f'data:image/jpeg;base64,{frame_b64}'
            })
        except Exception as e:
            logger.error(f"Frame read error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    else:
        return jsonify({'success': False, 'error': 'Capture failed'}), 500


@app.route('/api/capture-sequence', methods=['POST'])
def capture_sequence():
    """
    Capture 3 photos in sequence with delays (legacy endpoint)
    """
    global streaming_active, capture_in_progress
    
    if capture_in_progress:
        return jsonify({'success': False, 'error': 'Capture already in progress'}), 409
    
    # Stop streaming
    streaming_active = False
    capture_in_progress = True
    
    try:
        logger.info("=== Starting capture sequence ===")
        logger.info("Stopping stream and waiting for camera...")
        
        # Wait for streaming to fully stop
        time.sleep(1.0)
        
        # Kill any leftover camera processes to ensure camera is free
        try:
            subprocess.run(['pkill', '-9', 'rpicam-vid'], capture_output=True)
            time.sleep(3.5)  # Critical: wait for memory to be freed
            subprocess.run(['pkill', '-9', 'rpicam-still'], capture_output=True)
            time.sleep(0.5)
        except:
            pass
        
        logger.info("Camera should be free now")
        
        # Create timestamped folder
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        folder_path = PHOTOS_DIR / timestamp
        folder_path.mkdir(exist_ok=True)
        logger.info(f"Created folder: {folder_path}")
        
        photos = []
        
        # Capture 3 photos
        for i in range(1, 4):
            logger.info(f"Capturing photo {i}/3")
            
            photo_name = f"{timestamp}_{i:03d}.jpg"
            photo_path = folder_path / photo_name
            
            # High quality capture at native resolution
            if not analysis_capture(photo_path, timeout_ms=4000):
                logger.error(f"Failed to capture photo {i}/3")
                capture_in_progress = False
                streaming_active = True
                return jsonify({
                    'success': False,
                    'error': f'Failed to capture photo {i}/3'
                }), 500
            
            photos.append(photo_name)
            logger.info(f"Captured: {photo_name}")
            
            # Delay before next capture (except after last)
            if i < 3:
                time.sleep(2.0)
        
        logger.info(f"=== Capture sequence complete: {len(photos)} photos ===")
        
        return jsonify({
            'success': True,
            'folder': timestamp,
            'photos': photos,
            'folder_path': str(folder_path)
        })
        
    except Exception as e:
        logger.error(f"Capture sequence error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Capture failed: {str(e)}'
        }), 500
    finally:
        # Always reset flags
        capture_in_progress = False
        time.sleep(0.5)
        streaming_active = True
        logger.info("Resuming stream")


@app.route('/api/capture-sequence-stream')
def capture_sequence_stream():
    """
    Capture photos in sequence with real-time progress updates via SSE
    Number of photos is configurable via config.json
    """
    def generate():
        global streaming_active, capture_in_progress, app_config
        
        if capture_in_progress:
            yield f'data: {json.dumps({"status": "error", "message": "Capture already in progress"})}\n\n'
            return
        
        # Stop streaming
        streaming_active = False
        capture_in_progress = True
        
        try:
            # Get number of photos, delays, and save location from config
            num_photos = app_config.get('num_photos', 3)
            startup_delay = app_config.get('startup_delay', 3.5)
            capture_delay = app_config.get('capture_delay', 2.0)
            save_location = app_config.get('save_location', 'photos')
            camera_command = app_config.get('camera_command', 'rpicam-still')
            
            yield f'data: {json.dumps({"status": "starting", "message": "Starting capture sequence..."})}\n\n'
            logger.info(f"=== Starting capture sequence ({num_photos} photos) ===")
            
            yield f'data: {json.dumps({"status": "preparing", "message": "Stopping stream and preparing camera..."})}\n\n'
            
            # Wait for streaming to fully stop
            time.sleep(1.0)
            
            # Kill any leftover camera processes
            try:
                subprocess.run(['pkill', '-9', 'rpicam-vid'], capture_output=True)
                time.sleep(startup_delay)  # Configurable startup delay
                subprocess.run(['pkill', '-9', 'rpicam-still'], capture_output=True)
                time.sleep(0.5)
            except:
                pass
            
            logger.info("Camera should be free now")
            
            # Create timestamped folder in configured save location
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_path = Path(save_location)
            folder_path = base_path / timestamp
            folder_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created folder: {folder_path}")
            
            photos = []
            
            # Capture photos with progress updates
            for i in range(1, num_photos + 1):
                yield f'data: {json.dumps({"status": "capturing", "photo": i, "total": num_photos, "message": f"Capturing photo {i}/{num_photos}..."})}\n\n'
                logger.info(f"Capturing photo {i}/{num_photos}")
                
                photo_name = f"{timestamp}_{i:03d}.jpg"
                photo_path = folder_path / photo_name
                
                # High quality capture at native resolution with configured command
                if not analysis_capture(photo_path, timeout_ms=2000, camera_command=camera_command):
                    logger.error(f"Failed to capture photo {i}/{num_photos}")
                    yield f'data: {json.dumps({"status": "error", "message": f"Failed to capture photo {i}/{num_photos}"})}\n\n'
                    capture_in_progress = False
                    streaming_active = True
                    return
                
                photos.append(photo_name)
                logger.info(f"Captured: {photo_name}")
                
                # Send success with image URL
                yield f'data: {json.dumps({"status": "captured", "photo": i, "total": num_photos, "filename": photo_name, "folder": timestamp, "message": f"Captured photo {i}/{num_photos}"})}\n\n'
                
                # Delay before next capture (except after last)
                if i < num_photos:
                    time.sleep(capture_delay)
            
            logger.info(f"=== Capture sequence complete: {len(photos)} photos ===")
            
            # Send completion event
            yield f'data: {json.dumps({"status": "complete", "folder": timestamp, "photos": photos, "message": "All photos captured successfully"})}\n\n'
            
        except Exception as e:
            logger.error(f"Capture sequence error: {e}", exc_info=True)
            yield f'data: {json.dumps({"status": "error", "message": f"Capture failed: {str(e)}"})}\n\n'
        finally:
            # Always reset flags
            capture_in_progress = False
            time.sleep(0.5)
            streaming_active = True
            logger.info("Resuming stream")
    
    return Response(generate(), mimetype='text/event-stream')


def scale_rois_to_capture_resolution(streaming_rois):
    """
    Scale ROI coordinates from streaming resolution to capture resolution
    
    Args:
        streaming_rois: List of ROI dicts with x, y, width, height in streaming coordinates
    
    Returns:
        List of ROI dicts scaled to capture resolution
    """
    scaled_rois = []
    for roi in streaming_rois:
        scaled_roi = {
            'x': int(roi['x'] * SCALE_FACTOR_X),
            'y': int(roi['y'] * SCALE_FACTOR_Y),
            'width': int(roi['width'] * SCALE_FACTOR_X),
            'height': int(roi['height'] * SCALE_FACTOR_Y)
        }
        scaled_rois.append(scaled_roi)
        logger.debug(f"Scaled ROI: {roi} -> {scaled_roi}")
    return scaled_rois


@app.route('/api/analyze-sequence', methods=['POST'])
def analyze_sequence():
    """Analyze a sequence of captured photos"""
    data = request.get_json()
    
    if not data or 'folder' not in data or 'photos' not in data or 'rois' not in data:
        return jsonify({'success': False, 'error': 'Missing data'}), 400
    
    folder = data['folder']
    photos = data['photos']
    streaming_rois = data['rois']  # ROIs in streaming coordinates
    folder_path = PHOTOS_DIR / folder
    
    if not folder_path.exists():
        return jsonify({'success': False, 'error': 'Folder not found'}), 404
    
    try:
        logger.info(f"Analyzing {len(photos)} photos in: {folder}")
        
        # Scale ROIs from streaming resolution to capture resolution
        capture_rois = scale_rois_to_capture_resolution(streaming_rois)
        logger.info(f"Scaled {len(streaming_rois)} ROIs to capture resolution")
        
        analyzer = HSVAnalyzer()
        all_results = []
        
        # Analyze each photo
        for i, photo_name in enumerate(photos, 1):
            photo_path = folder_path / photo_name
            
            if not photo_path.exists():
                return jsonify({'success': False, 'error': f'Photo not found: {photo_name}'}), 404
            
            logger.info(f"Analyzing photo {i}/{len(photos)}: {photo_name}")
            results = analyzer.analyze_image(photo_path, capture_rois)
            all_results.append(results)
            logger.info(f"Results: {results}")
        
        # Average the results
        num_rois = len(streaming_rois)
        averaged_results = []
        
        for roi_idx in range(num_rois):
            total = sum(result[roi_idx] for result in all_results)
            avg = total / len(all_results)
            averaged_results.append(round(avg))
        
        logger.info(f"Averaged results: {averaged_results}")
        
        return jsonify({
            'success': True,
            'results': averaged_results,
            'individual_results': all_results
        })
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/save-to-usb', methods=['POST'])
def save_to_usb():
    """Save captured photos to USB with fallback to local directory"""
    import shutil
    
    data = request.get_json()
    
    if not data or 'folder' not in data:
        return jsonify({'success': False, 'error': 'Missing folder'}), 400
    
    folder = data['folder']
    results = data.get('results', {})
    folder_path = PHOTOS_DIR / folder
    
    if not folder_path.exists():
        return jsonify({'success': False, 'error': 'Folder not found'}), 404
    
    # Try USB first
    try:
        usb_drives = find_usb_drives()
        
        if usb_drives:
            usb_path = Path(usb_drives[0])
            save_dir = usb_path / 'test_strip_images' / folder
            
            try:
                save_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Saving to USB: {save_dir}")
                
                saved_files = []
                
                # Copy all photos
                for photo in folder_path.glob('*.jpg'):
                    dest = save_dir / photo.name
                    shutil.copy2(photo, dest)
                    saved_files.append(photo.name)
                    logger.info(f"Copied: {photo.name}")
                
                # Save results JSON
                if results:
                    json_filename = f"{folder}_results.json"
                    json_path = save_dir / json_filename
                    with open(json_path, 'w') as f:
                        json.dump({
                            'folder': folder,
                            'timestamp': datetime.now().isoformat(),
                            'results': results
                        }, f, indent=2)
                    saved_files.append(json_filename)
                    logger.info(f"Saved results JSON")
                
                return jsonify({
                    'success': True,
                    'message': f'Saved {len(saved_files)} files to USB',
                    'saved_path': str(save_dir),
                    'files': saved_files,
                    'location': 'usb'
                })
                
            except PermissionError as e:
                logger.warning(f"USB permission denied: {e}. Falling back to local directory.")
            except Exception as e:
                logger.warning(f"USB save failed: {e}. Falling back to local directory.")
        else:
            logger.info("No USB drive found. Using local backup directory.")
    
    except Exception as e:
        logger.warning(f"Error detecting USB: {e}. Falling back to local directory.")
    
    # Fallback to local backup directory
    try:
        home_dir = Path.home()
        backup_base = home_dir / 'rpi_uv_photos_backup'
        save_dir = backup_base / folder
        save_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Saving to local backup: {save_dir}")
        
        saved_files = []
        
        # Copy all photos
        for photo in folder_path.glob('*.jpg'):
            dest = save_dir / photo.name
            shutil.copy2(photo, dest)
            saved_files.append(photo.name)
            logger.info(f"Copied: {photo.name}")
        
        # Save results JSON
        if results:
            json_filename = f"{folder}_results.json"
            json_path = save_dir / json_filename
            with open(json_path, 'w') as f:
                json.dump({
                    'folder': folder,
                    'timestamp': datetime.now().isoformat(),
                    'results': results
                }, f, indent=2)
            saved_files.append(json_filename)
            logger.info(f"Saved results JSON")
        
        return jsonify({
            'success': True,
            'message': f'Saved {len(saved_files)} files to local backup (USB not available)',
            'saved_path': str(save_dir),
            'files': saved_files,
            'location': 'local_backup'
        })
        
    except Exception as e:
        logger.error(f"Backup save failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Failed to save files: {str(e)}'}), 500


@app.route('/api/usb/status', methods=['GET'])
def usb_status():
    """Check USB drive status"""
    drives = find_usb_drives()
    return jsonify({
        'available': len(drives) > 0,
        'drives': drives,
        'count': len(drives)
    })


@app.route('/api/get-image/<folder>/<filename>', methods=['GET'])
def get_image(folder, filename):
    """Serve a captured image from the photos directory"""
    try:
        folder_path = PHOTOS_DIR / folder
        if not folder_path.exists():
            return jsonify({'error': 'Folder not found'}), 404
        
        image_path = folder_path / filename
        if not image_path.exists():
            return jsonify({'error': 'Image not found'}), 404
        
        # Serve the image file
        return send_from_directory(folder_path, filename, mimetype='image/jpeg')
    
    except Exception as e:
        logger.error(f"Error serving image: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    global app_config
    return jsonify({
        'success': True,
        'config': app_config
    })


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration"""
    global app_config
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    try:
        # Update config
        for key, value in data.items():
            if key in ['num_photos', 'startup_delay', 'capture_delay', 'save_location', 'pwm_duty_cycle', 'camera_command', 'rois']:
                app_config[key] = value
        
        # Save to file
        if save_config(app_config):
            # Update PWM if duty cycle changed
            if 'pwm_duty_cycle' in data:
                set_pwm_duty_cycle(data['pwm_duty_cycle'])
            
            return jsonify({
                'success': True,
                'message': 'Configuration updated',
                'config': app_config
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to save config'}), 500
            
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pwm/set', methods=['POST'])
def set_pwm():
    """Set PWM duty cycle"""
    data = request.get_json()
    
    if not data or 'duty_cycle' not in data:
        return jsonify({'success': False, 'error': 'Missing duty_cycle'}), 400
    
    duty_cycle = data['duty_cycle']
    
    if set_pwm_duty_cycle(duty_cycle):
        # Update config
        app_config['pwm_duty_cycle'] = duty_cycle
        save_config(app_config)
        
        return jsonify({
            'success': True,
            'duty_cycle': duty_cycle
        })
    else:
        return jsonify({'success': False, 'error': 'Failed to set PWM'}), 500


@app.route('/api/system/info', methods=['GET'])
def system_info():
    """Get system information"""
    import platform
    return jsonify({
        'platform': platform.system(),
        'camera_available': True,
        'gpio_available': GPIO_AVAILABLE,
        'version': '1.0.3'
    })


@app.route('/api/shutdown', methods=['POST'])
def shutdown_server():
    """Safely shutdown the server and clean up resources"""
    global streaming_active, mjpeg_process
    
    logger.info("=== Shutdown requested ===")
    
    try:
        # Stop streaming
        streaming_active = False
        
        # Kill MJPEG process if running
        if mjpeg_process:
            try:
                mjpeg_process.terminate()
                mjpeg_process.wait(timeout=2)
            except:
                try:
                    mjpeg_process.kill()
                except:
                    pass
            mjpeg_process = None
        
        # Kill any camera processes
        try:
            subprocess.run(['pkill', '-9', 'rpicam-vid'], capture_output=True)
            subprocess.run(['pkill', '-9', 'rpicam-still'], capture_output=True)
        except:
            pass
        
        # Set PWM duty cycle to 0
        if GPIO_AVAILABLE:
            logger.info("Setting PWM duty cycle to 0%")
            set_pwm_duty_cycle(0)
        
        # Cleanup GPIO
        cleanup_pwm()
        
        logger.info("Cleanup complete, shutting down Flask server...")
        
        # Shutdown Flask server
        shutdown = request.environ.get('werkzeug.server.shutdown')
        if shutdown is None:
            # Werkzeug 2.1+ doesn't have server.shutdown, use os._exit as fallback
            import os
            import threading
            def delayed_shutdown():
                time.sleep(1)
                os._exit(0)
            threading.Thread(target=delayed_shutdown, daemon=True).start()
        else:
            shutdown()
        
        return jsonify({'success': True, 'message': 'Server shutting down safely'})
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("RPi Test Strip Analyzer - Server Starting (v1.0.3)")
    logger.info("=" * 60)
    logger.info(f"Stream resolution: {STREAM_WIDTH}x{STREAM_HEIGHT}")
    logger.info(f"Capture resolution: Native (full camera resolution)")
    logger.info(f"Photos directory: {PHOTOS_DIR.absolute()}")
    logger.info(f"Log directory: {LOG_DIR.absolute()}")
    logger.info(f"Config file: {CONFIG_FILE.absolute()}")
    logger.info(f"Number of photos per capture: {app_config.get('num_photos', 3)}")
    logger.info(f"PWM duty cycle: {app_config.get('pwm_duty_cycle', 60)}%")
    logger.info(f"Camera command: {app_config.get('camera_command', 'rpicam-still')}")
    logger.info(f"GPIO available: {GPIO_AVAILABLE}")
    logger.info(f"Server: http://0.0.0.0:5000")
    logger.info("=" * 60)
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    finally:
        # Cleanup on exit
        cleanup_pwm()
