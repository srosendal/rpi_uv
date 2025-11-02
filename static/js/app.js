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
        // Try to load saved configuration
        this.roiManager.loadFromLocalStorage();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Check system status
        await this.checkSystemStatus();
        
        // Start streaming
        this.startStreaming();
        
        // Update UI
        this.roiManager.updateAllROIVisuals();
        this.updateLEDBrightnessDisplay();
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
        
        // LED brightness slider
        const ledBrightness = document.getElementById('led-brightness');
        const ledValue = document.getElementById('led-value');
        ledBrightness.addEventListener('input', (e) => {
            const value = parseInt(e.target.value);
            this.roiManager.setLEDBrightness(value);
            ledValue.textContent = value;
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
        // Start streaming from API
        fetch(`${this.apiBaseUrl}/api/stream/start`, { method: 'POST' })
            .catch(err => console.error('Failed to start stream:', err));
        
        // Request frames every 200ms for 4-5 fps streaming
        this.streamingInterval = setInterval(() => {
            this.updateStreamingImage();
        }, 200);
    }

    stopStreaming() {
        if (this.streamingInterval) {
            clearInterval(this.streamingInterval);
            this.streamingInterval = null;
        }
        
        // Stop streaming on server
        fetch(`${this.apiBaseUrl}/api/stream/stop`, { method: 'POST' })
            .catch(err => console.error('Failed to stop stream:', err));
    }

    async updateStreamingImage() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/stream/frame`);
            const data = await response.json();
            
            if (data.success && data.image) {
                const img = new Image();
                img.onload = () => {
                    this.ctx.drawImage(img, 0, 0, 406, 304);
                };
                img.src = data.image;
            }
        } catch (error) {
            // Silently fail during streaming - camera may be temporarily busy
            console.debug('Stream frame error:', error);
        }
    }

    async handleCapture() {
        if (this.isCapturing) return;
        
        this.isCapturing = true;
        this.captureBtn.disabled = true;
        
        // Stop streaming requests during capture
        if (this.streamingInterval) {
            clearInterval(this.streamingInterval);
            this.streamingInterval = null;
        }
        
        // Update status
        this.updateStatus('Starting capture sequence...', 'processing');
        
        try {
            // NEW WORKFLOW: Capture 3 photos first, then analyze
            
            // Step 1: Capture 3 photos in sequence
            this.updateStatus('Capturing 3 photos...', 'processing');
            
            const captureResponse = await fetch(`${this.apiBaseUrl}/api/capture-sequence`, {
                method: 'POST'
            });
            
            if (!captureResponse.ok) {
                const errorData = await captureResponse.json();
                throw new Error(errorData.error || 'Capture sequence failed');
            }
            
            const captureData = await captureResponse.json();
            
            if (!captureData.success) {
                throw new Error(captureData.error || 'Capture sequence failed');
            }
            
            // Store folder info for USB saving
            this.lastCapturedFolder = captureData.folder;
            this.lastCapturedPhotos = captureData.photos;
            
            console.log(`Captured ${captureData.photos.length} photos to folder: ${captureData.folder}`);
            
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
                    folder: captureData.folder,
                    photos: captureData.photos,
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
            
        } catch (error) {
            console.error('Error during capture:', error);
            this.updateStatus(`Error: ${error.message}`, 'error');
        } finally {
            this.isCapturing = false;
            this.captureBtn.disabled = false;
            
            // Restart streaming
            this.startStreaming();
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

    saveConfiguration() {
        try {
            // Save to localStorage
            this.roiManager.saveToLocalStorage();
            
            // Also export as downloadable file
            this.roiManager.exportConfiguration();
            
            this.updateStatus('Configuration saved!', 'success');
            setTimeout(() => {
                this.updateStatus('', '');
            }, 3000);
        } catch (error) {
            console.error('Error saving configuration:', error);
            alert('Error saving configuration');
        }
    }

    resetConfiguration() {
        if (confirm('Reset to default configuration?')) {
            this.roiManager.resetToDefault();
            this.updateLEDBrightnessDisplay();
            this.updateStatus('Configuration reset to defaults', 'success');
            setTimeout(() => {
                this.updateStatus('', '');
            }, 3000);
        }
    }

    updateLEDBrightnessDisplay() {
        const brightness = this.roiManager.getLEDBrightness();
        document.getElementById('led-brightness').value = brightness;
        document.getElementById('led-value').textContent = brightness;
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
