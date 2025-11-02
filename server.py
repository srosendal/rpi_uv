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


def analysis_capture(output_path, timeout_ms=2000):
    """
    High quality camera capture for analysis - full native resolution
    Returns True if successful, False otherwise
    """
    try:
        logger.info(f"Capturing full resolution to: {output_path}")
        
        cmd = [
            'rpicam-still',
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
            if not analysis_capture(photo_path, timeout_ms=2000):
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
    Capture 3 photos in sequence with real-time progress updates via SSE
    """
    def generate():
        global streaming_active, capture_in_progress
        
        if capture_in_progress:
            yield f'data: {json.dumps({"status": "error", "message": "Capture already in progress"})}\n\n'
            return
        
        # Stop streaming
        streaming_active = False
        capture_in_progress = True
        
        try:
            yield f'data: {json.dumps({"status": "starting", "message": "Starting capture sequence..."})}\n\n'
            logger.info("=== Starting capture sequence (SSE) ===")
            
            yield f'data: {json.dumps({"status": "preparing", "message": "Stopping stream and preparing camera..."})}\n\n'
            
            # Wait for streaming to fully stop
            time.sleep(1.0)
            
            # Kill any leftover camera processes
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
            
            # Capture 3 photos with progress updates
            for i in range(1, 4):
                yield f'data: {json.dumps({"status": "capturing", "photo": i, "total": 3, "message": f"Capturing photo {i}/3..."})}\n\n'
                logger.info(f"Capturing photo {i}/3")
                
                photo_name = f"{timestamp}_{i:03d}.jpg"
                photo_path = folder_path / photo_name
                
                # High quality capture at native resolution
                if not analysis_capture(photo_path, timeout_ms=2000):
                    logger.error(f"Failed to capture photo {i}/3")
                    yield f'data: {json.dumps({"status": "error", "message": f"Failed to capture photo {i}/3"})}\n\n'
                    capture_in_progress = False
                    streaming_active = True
                    return
                
                photos.append(photo_name)
                logger.info(f"Captured: {photo_name}")
                
                # Send success with image URL
                yield f'data: {json.dumps({"status": "captured", "photo": i, "total": 3, "filename": photo_name, "folder": timestamp, "message": f"Captured photo {i}/3"})}\n\n'
                
                # Delay before next capture (except after last)
                if i < 3:
                    time.sleep(2.0)
            
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
    """Save captured photos to USB"""
    data = request.get_json()
    
    if not data or 'folder' not in data:
        return jsonify({'success': False, 'error': 'Missing folder'}), 400
    
    folder = data['folder']
    results = data.get('results', {})
    folder_path = PHOTOS_DIR / folder
    
    if not folder_path.exists():
        return jsonify({'success': False, 'error': 'Folder not found'}), 404
    
    try:
        usb_drives = find_usb_drives()
        
        if not usb_drives:
            return jsonify({'success': False, 'message': 'No USB drive found'}), 404
        
        usb_path = Path(usb_drives[0])
        save_dir = usb_path / 'test_strip_images' / folder
        save_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Saving to USB: {save_dir}")
        
        # Copy all photos
        import shutil
        saved_files = []
        
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
            'message': f'Saved {len(saved_files)} files',
            'saved_path': str(save_dir),
            'files': saved_files
        })
        
    except Exception as e:
        logger.error(f"USB save failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


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


@app.route('/api/system/info', methods=['GET'])
def system_info():
    """Get system information"""
    import platform
    return jsonify({
        'platform': platform.system(),
        'camera_available': True,
        'version': '1.0.2'
    })


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("RPi Test Strip Analyzer - Server Starting (v1.0.2)")
    logger.info("=" * 60)
    logger.info(f"Stream resolution: {STREAM_WIDTH}x{STREAM_HEIGHT}")
    logger.info(f"Capture resolution: Native (full camera resolution)")
    logger.info(f"Photos directory: {PHOTOS_DIR.absolute()}")
    logger.info(f"Log directory: {LOG_DIR.absolute()}")
    logger.info(f"Server: http://0.0.0.0:5000")
    logger.info("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
