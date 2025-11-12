/**
 * Main Application Controller - Raspberry Pi Version
 * Handles UI interactions, camera streaming via API, and coordinates between modules
 */

class App {
    constructor() {
        // Initialize modules
        this.analyzer = new ImageAnalyzer();
        this.roiManager = new ROIManager();
        
        // State
        this.isSettingsMode = false;
        this.streamingInterval = null;
        this.isCapturing = false;
        this.apiBaseUrl = window.location.origin;
        this.lastCapturedImage = null;
        this.lastCapturedFilename = null;
        
        // DOM elements
        this.canvas = document.getElementById('camera-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.mjpegStream = document.getElementById('mjpeg-stream');
        this.captureBtn = document.getElementById('capture-btn');
        this.normalModeBtn = document.getElementById('normal-mode-btn');
        this.settingsModeBtn = document.getElementById('settings-mode-btn');
        this.normalControls = document.getElementById('normal-controls');
        this.settingsControls = document.getElementById('settings-controls');
        this.statusMessage = document.getElementById('status-message');
        this.fpsCounter = document.getElementById('fps-counter');
        this.lastCaptureTime = null;
        
        this.init();
    }

    async init() {
        // Load configuration from backend
        await this.loadConfiguration();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Check system status
        await this.checkSystemStatus();
        
        // Start streaming
        this.startStreaming();
        
        // Update UI
        this.roiManager.updateAllROIVisuals();
        this.updateSettingsDisplay();
    }

    async checkSystemStatus() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/system/info`);
            const data = await response.json();
            console.log('System info:', data);
            
            // Check USB status
            const usbResponse = await fetch(`${this.apiBaseUrl}/api/usb/status`);
            const usbData = await usbResponse.json();
            console.log('USB status:', usbData);
            
            if (!usbData.available) {
                console.warn('No USB drive detected');
            }
        } catch (error) {
            console.error('Failed to check system status:', error);
        }
    }

    setupEventListeners() {
        // Capture button
        this.captureBtn.addEventListener('click', () => this.handleCapture());
        
        // Mode toggle buttons
        this.normalModeBtn.addEventListener('click', () => this.switchToNormalMode());
        this.settingsModeBtn.addEventListener('click', () => this.switchToSettingsMode());
        
        // ROI selection buttons
        document.querySelectorAll('.roi-select-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const roiId = parseInt(e.target.dataset.roi);
                this.selectROI(roiId);
            });
        });
        
        // Mode selector buttons
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const mode = e.target.dataset.mode;
                this.selectMode(mode);
            });
        });
        
        // Direction buttons
        document.querySelectorAll('.dir-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const direction = e.target.dataset.dir;
                this.roiManager.moveSelectedROI(direction);
            });
        });
        
        // Number of photos input
        const numPhotosInput = document.getElementById('num-photos');
        numPhotosInput.addEventListener('change', (e) => {
            const value = parseInt(e.target.value);
            if (value >= 1 && value <= 5) {
                console.log(`Number of photos set to: ${value}`);
            }
        });
        
        // PWM duty cycle slider
        const pwmSlider = document.getElementById('pwm-duty-cycle');
        const pwmValue = document.getElementById('pwm-duty-value');
        
        // Update display while sliding
        pwmSlider.addEventListener('input', (e) => {
            const value = parseInt(e.target.value);
            pwmValue.textContent = `${value}%`;
        });
        
        // Apply PWM when slider is released
        pwmSlider.addEventListener('change', async (e) => {
            const value = parseInt(e.target.value);
            await this.setPWMDutyCycle(value);
        });
        
        // Camera command input
        const cameraCommandInput = document.getElementById('camera-command');
        cameraCommandInput.addEventListener('blur', () => {
            console.log(`Camera command: ${cameraCommandInput.value}`);
        });
        
        // Save configuration
        document.getElementById('save-config-btn').addEventListener('click', () => {
            this.saveConfiguration();
        });
        
        // Reset configuration
        document.getElementById('reset-config-btn').addEventListener('click', () => {
            this.resetConfiguration();
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (this.isSettingsMode && !e.ctrlKey && !e.metaKey) {
                switch(e.key) {
                    case 'ArrowUp':
                        e.preventDefault();
                        this.roiManager.moveSelectedROI('up');
                        break;
                    case 'ArrowDown':
                        e.preventDefault();
                        this.roiManager.moveSelectedROI('down');
                        break;
                    case 'ArrowLeft':
                        e.preventDefault();
                        this.roiManager.moveSelectedROI('left');
                        break;
                    case 'ArrowRight':
                        e.preventDefault();
                        this.roiManager.moveSelectedROI('right');
                        break;
                }
            }
        });
    }

    startStreaming() {
        // Start MJPEG streaming from API
        fetch(`${this.apiBaseUrl}/api/stream/start`, { method: 'POST' })
            .then(() => {
                console.log('MJPEG stream started');
                // Set the MJPEG stream source with cache-busting timestamp
                this.mjpegStream.src = `${this.apiBaseUrl}/stream?t=${Date.now()}`;
                this.mjpegStream.style.display = 'block';
            })
            .catch(err => console.error('Failed to start stream:', err));
    }

    stopStreaming(keepVisual = false) {
        // Optionally capture current frame before stopping
        if (keepVisual) {
            this.captureCurrentFrameToCanvas();
        }
        
        // Stop streaming on server
        fetch(`${this.apiBaseUrl}/api/stream/stop`, { method: 'POST' })
            .then(() => {
                console.log('MJPEG stream stopped');
                // Clear the stream source
                this.mjpegStream.src = '';
                this.mjpegStream.style.display = 'none';
                
                // Show canvas if we want to keep visual
                if (keepVisual) {
                    this.canvas.style.display = 'block';
                }
            })
            .catch(err => console.error('Failed to stop stream:', err));
    }

    captureCurrentFrameToCanvas() {
        // Draw the current MJPEG frame to canvas
        this.ctx.drawImage(this.mjpegStream, 0, 0, this.canvas.width, this.canvas.height);
    }

    async handleCaptureWithProgress() {
        return new Promise((resolve, reject) => {
            const eventSource = new EventSource(`${this.apiBaseUrl}/api/capture-sequence-stream`);
            
            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('SSE event:', data);
                    
                    // Update status message
                    this.updateStatus(data.message, 'processing');
                    
                    // Handle different event types
                    if (data.status === 'captured' && data.folder && data.filename) {
                        // Display the captured image as thumbnail
                        this.displayCapturedImage(data.folder, data.filename);
                        
                        // Store for later use
                        if (!this.lastCapturedFolder) {
                            this.lastCapturedFolder = data.folder;
                            this.lastCapturedPhotos = [];
                        }
                        this.lastCapturedPhotos.push(data.filename);
                    }
                    
                    if (data.status === 'complete') {
                        // Capture complete
                        this.lastCapturedFolder = data.folder;
                        this.lastCapturedPhotos = data.photos;
                        eventSource.close();
                        resolve(data);
                    }
                    
                    if (data.status === 'error') {
                        eventSource.close();
                        reject(new Error(data.message));
                    }
                } catch (error) {
                    console.error('Error parsing SSE data:', error);
                    eventSource.close();
                    reject(error);
                }
            };
            
            eventSource.onerror = (error) => {
                console.error('SSE error:', error);
                eventSource.close();
                reject(new Error('Connection to server lost'));
            };
        });
    }

    async handleCapture() {
        if (this.isCapturing) return;
        
        this.isCapturing = true;
        this.captureBtn.disabled = true;
        
        // Stop MJPEG streaming during capture, but keep visual
        this.stopStreaming(true);
        
        // Update status
        this.updateStatus('Starting capture sequence...', 'processing');
        
        try {
            // Use Server-Sent Events for real-time progress
            await this.handleCaptureWithProgress();
            
            // Step 2: Analyze the captured photos
            this.updateStatus('Analyzing photos...', 'processing');
            
            // Get ROIs for analysis
            const rois = this.roiManager.getROIs();
            
            const analyzeResponse = await fetch(`${this.apiBaseUrl}/api/analyze-sequence`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    folder: this.lastCapturedFolder,
                    photos: this.lastCapturedPhotos,
                    rois: rois
                })
            });
            
            if (!analyzeResponse.ok) {
                const errorData = await analyzeResponse.json();
                throw new Error(errorData.error || 'Analysis failed');
            }
            
            const analyzeData = await analyzeResponse.json();
            
            if (!analyzeData.success) {
                throw new Error(analyzeData.error || 'Analysis failed');
            }
            
            // Display averaged results
            this.displayResults(analyzeData.results);
            
            // Save timestamp
            this.lastCaptureTime = new Date();
            
            // Format timestamp
            const timeStr = this.lastCaptureTime.toLocaleTimeString('en-GB', { 
                hour: '2-digit', 
                minute: '2-digit', 
                second: '2-digit' 
            });
            this.updateStatus(`Analysis complete! [${timeStr}]`, 'success');
            
            console.log('Individual results:', analyzeData.individual_results);
            console.log('Averaged results:', analyzeData.results);
            
            // Automatically save to USB if available
            await this.saveToUSB(analyzeData.results);
            
            // Display one of the captured images on canvas
            if (this.lastCapturedPhotos && this.lastCapturedPhotos.length > 0) {
                await this.displayCapturedImage(this.lastCapturedFolder, this.lastCapturedPhotos[0]);
            }
            
        } catch (error) {
            console.error('Error during capture:', error);
            this.updateStatus(`Error: ${error.message}`, 'error');
        } finally {
            this.isCapturing = false;
            this.captureBtn.disabled = false;
            
            // Hide canvas and restart streaming
            this.canvas.style.display = 'none';
            this.startStreaming();
        }
    }

    async displayCapturedImage(folder, filename) {
        try {
            // Fetch the captured image
            const response = await fetch(`${this.apiBaseUrl}/api/get-image/${folder}/${filename}`);
            if (!response.ok) {
                console.error('Failed to fetch captured image');
                return;
            }
            
            const blob = await response.blob();
            const img = await createImageBitmap(blob);
            
            // Draw scaled down version to canvas (4056x3040 -> 406x304)
            this.ctx.drawImage(img, 0, 0, this.canvas.width, this.canvas.height);
            
        } catch (error) {
            console.error('Error displaying captured image:', error);
        }
    }

    loadImageFromBase64(base64Data) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = reject;
            img.src = base64Data;
        });
    }

    averageResults(allResults) {
        // allResults is an array of 3 result arrays
        // Each result array has 4 intensity values
        const numStripes = allResults[0].length;
        const averaged = [];
        
        for (let i = 0; i < numStripes; i++) {
            const sum = allResults.reduce((acc, results) => acc + results[i], 0);
            const avg = Math.round(sum / allResults.length);
            averaged.push(avg);
        }
        
        return averaged;
    }

    async saveToUSB(results) {
        if (!this.lastCapturedFolder) {
            console.warn('No captured folder to save');
            return;
        }
        
        try {
            // Check USB status first
            const usbResponse = await fetch(`${this.apiBaseUrl}/api/usb/status`);
            const usbData = await usbResponse.json();
            
            if (!usbData.available) {
                console.warn('No USB drive available for saving');
                return;
            }
            
            // Prepare results data
            const resultsData = {
                stripe_1: results[0],
                stripe_2: results[1],
                stripe_3: results[2],
                stripe_4: results[3]
            };
            
            // Save to USB (saves entire folder with all 3 photos)
            const saveResponse = await fetch(`${this.apiBaseUrl}/api/save-to-usb`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    folder: this.lastCapturedFolder,
                    results: resultsData
                })
            });
            
            const saveData = await saveResponse.json();
            
            if (saveData.success) {
                console.log('Saved to USB:', saveData.saved_path);
                console.log('Files saved:', saveData.files);
                // Optionally show a brief notification
                const currentStatus = this.statusMessage.textContent;
                this.updateStatus(currentStatus + ' (Saved to USB)', 'success');
            } else {
                console.warn('Failed to save to USB:', saveData.message);
            }
            
        } catch (error) {
            console.error('Error saving to USB:', error);
        }
    }

    displayResults(results) {
        for (let i = 0; i < results.length; i++) {
            const resultElement = document.getElementById(`result-${i + 1}`);
            if (resultElement) {
                resultElement.textContent = results[i];
            }
        }
    }

    updateStatus(message, type = '') {
        this.statusMessage.textContent = message;
        this.statusMessage.className = type;
    }

    switchToNormalMode() {
        if (!this.isSettingsMode) return;
        
        this.isSettingsMode = false;
        this.normalControls.style.display = 'block';
        this.settingsControls.style.display = 'none';
        
        // Toggle action rows
        document.getElementById('normal-actions').style.display = 'block';
        document.getElementById('settings-actions').style.display = 'none';
        
        // Update button states
        this.normalModeBtn.classList.add('active');
        this.settingsModeBtn.classList.remove('active');
        
        // Clear ROI selection highlighting
        document.querySelectorAll('.roi-rect').forEach(rect => {
            rect.classList.remove('selected');
        });
        document.querySelectorAll('.roi-label').forEach(label => {
            label.classList.remove('selected');
        });
    }
    
    switchToSettingsMode() {
        if (this.isSettingsMode) return;
        
        this.isSettingsMode = true;
        this.normalControls.style.display = 'none';
        this.settingsControls.style.display = 'block';
        
        // Toggle action rows
        document.getElementById('normal-actions').style.display = 'none';
        document.getElementById('settings-actions').style.display = 'flex';
        
        // Update button states
        this.normalModeBtn.classList.remove('active');
        this.settingsModeBtn.classList.add('active');
        
        this.roiManager.updateROISelection();
    }

    selectROI(roiId) {
        this.roiManager.selectROI(roiId);
        this.roiManager.updateROISelection();
        
        // Update button states
        document.querySelectorAll('.roi-select-btn').forEach(btn => {
            if (parseInt(btn.dataset.roi) === roiId) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    selectMode(mode) {
        this.roiManager.setAdjustmentMode(mode);
        
        // Update button states
        document.querySelectorAll('.mode-btn').forEach(btn => {
            if (btn.dataset.mode === mode) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    async loadConfiguration() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/config`);
            const data = await response.json();
            
            if (data.success && data.config) {
                // Load ROIs
                if (data.config.rois) {
                    this.roiManager.loadConfiguration({ rois: data.config.rois });
                }
                
                // Update settings inputs
                const numPhotosInput = document.getElementById('num-photos');
                const pwmSlider = document.getElementById('pwm-duty-cycle');
                const pwmValue = document.getElementById('pwm-duty-value');
                const cameraCommandInput = document.getElementById('camera-command');
                
                if (numPhotosInput) numPhotosInput.value = data.config.num_photos || 3;
                if (pwmSlider) pwmSlider.value = data.config.pwm_duty_cycle || 60;
                if (pwmValue) pwmValue.textContent = `${data.config.pwm_duty_cycle || 60}%`;
                if (cameraCommandInput) cameraCommandInput.value = data.config.camera_command || 'rpicam-still';
                
                console.log('Configuration loaded from backend:', data.config);
            }
        } catch (error) {
            console.error('Error loading configuration:', error);
        }
    }

    async saveConfiguration() {
        try {
            // Gather all settings
            const config = {
                num_photos: parseInt(document.getElementById('num-photos').value),
                pwm_duty_cycle: parseInt(document.getElementById('pwm-duty-cycle').value),
                camera_command: document.getElementById('camera-command').value,
                rois: this.roiManager.getROIs()
            };
            
            // Save to backend
            const response = await fetch(`${this.apiBaseUrl}/api/config`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(config)
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Also save to localStorage as backup
                this.roiManager.saveToLocalStorage();
                
                this.updateStatus('Configuration saved!', 'success');
                setTimeout(() => {
                    this.updateStatus('', '');
                }, 3000);
            } else {
                throw new Error(data.error || 'Failed to save configuration');
            }
        } catch (error) {
            console.error('Error saving configuration:', error);
            this.updateStatus(`Error: ${error.message}`, 'error');
        }
    }
    
    async setPWMDutyCycle(dutyCycle) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/pwm/set`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ duty_cycle: dutyCycle })
            });
            
            const data = await response.json();
            
            if (data.success) {
                console.log(`PWM duty cycle set to ${dutyCycle}%`);
            } else {
                console.error('Failed to set PWM:', data.error);
            }
        } catch (error) {
            console.error('Error setting PWM duty cycle:', error);
        }
    }

    async resetConfiguration() {
        if (confirm('Reset to default configuration?')) {
            this.roiManager.resetToDefault();
            
            // Reset all settings to defaults
            document.getElementById('num-photos').value = 3;
            document.getElementById('pwm-duty-cycle').value = 60;
            document.getElementById('pwm-duty-value').textContent = '60%';
            document.getElementById('camera-command').value = 'rpicam-still';
            
            // Save the reset configuration
            await this.saveConfiguration();
            
            this.updateStatus('Configuration reset to defaults', 'success');
            setTimeout(() => {
                this.updateStatus('', '');
            }, 3000);
        }
    }

    updateSettingsDisplay() {
        // This will be populated from loadConfiguration
        // No need to do anything here as it's handled in loadConfiguration
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
