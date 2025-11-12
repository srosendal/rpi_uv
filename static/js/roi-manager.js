/**
 * ROI Manager Module
 * Handles ROI positioning, selection, and configuration management
 */

class ROIManager {
    constructor() {
        this.rois = this.getDefaultROIs();
        this.selectedROI = 1;
        this.stepSize = 5;
        this.adjustmentMode = 'move'; // 'move', 'increase', or 'decrease'
    }

    /**
     * Get default ROI positions
     * Scaled for 406x304 streaming resolution (proportional to 4056x3040 capture)
     * @returns {Array} - Default ROI configurations
     */
    getDefaultROIs() {
        return [
            { id: 1, x: 117, y: 89, width: 141, height: 19 },
            { id: 2, x: 117, y: 136, width: 141, height: 19 },
            { id: 3, x: 117, y: 183, width: 141, height: 19 },
            { id: 4, x: 117, y: 230, width: 141, height: 19 }
        ];
    }

    /**
     * Get all ROIs
     * @returns {Array} - Current ROI configurations
     */
    getROIs() {
        return this.rois;
    }

    /**
     * Get specific ROI by ID
     * @param {number} id - ROI ID (1-4)
     * @returns {Object} - ROI configuration
     */
    getROI(id) {
        return this.rois.find(roi => roi.id === id);
    }

    /**
     * Set selected ROI
     * @param {number} id - ROI ID to select
     */
    selectROI(id) {
        if (id >= 1 && id <= 4) {
            this.selectedROI = id;
        }
    }

    /**
     * Get currently selected ROI
     * @returns {Object} - Selected ROI configuration
     */
    getSelectedROI() {
        return this.getROI(this.selectedROI);
    }

    /**
     * Set adjustment mode
     * @param {string} mode - 'move', 'increase', or 'decrease'
     */
    setAdjustmentMode(mode) {
        if (['move', 'increase', 'decrease'].includes(mode)) {
            this.adjustmentMode = mode;
        }
    }

    /**
     * Get current adjustment mode
     * @returns {string} - Current mode
     */
    getAdjustmentMode() {
        return this.adjustmentMode;
    }

    /**
     * Move selected ROI in specified direction
     * @param {string} direction - 'up', 'down', 'left', or 'right'
     */
    moveSelectedROI(direction) {
        const roi = this.getSelectedROI();
        if (!roi) return;

        if (this.adjustmentMode === 'move') {
            // Move entire ROI
            switch (direction) {
                case 'up':
                    roi.y = Math.max(0, roi.y - this.stepSize);
                    break;
                case 'down':
                    roi.y = Math.min(304 - roi.height, roi.y + this.stepSize);
                    break;
                case 'left':
                    roi.x = Math.max(0, roi.x - this.stepSize);
                    break;
                case 'right':
                    roi.x = Math.min(406 - roi.width, roi.x + this.stepSize);
                    break;
            }
        } else if (this.adjustmentMode === 'increase') {
            // Expand ROI by moving edges outward
            switch (direction) {
                case 'up':
                    // Move top edge up (expand upward)
                    const newY = Math.max(0, roi.y - this.stepSize);
                    roi.height += (roi.y - newY);
                    roi.y = newY;
                    break;
                case 'down':
                    // Move bottom edge down (expand downward)
                    roi.height = Math.min(304 - roi.y, roi.height + this.stepSize);
                    break;
                case 'left':
                    // Move left edge left (expand leftward)
                    const newX = Math.max(0, roi.x - this.stepSize);
                    roi.width += (roi.x - newX);
                    roi.x = newX;
                    break;
                case 'right':
                    // Move right edge right (expand rightward)
                    roi.width = Math.min(406 - roi.x, roi.width + this.stepSize);
                    break;
            }
        } else if (this.adjustmentMode === 'decrease') {
            // Shrink ROI by moving edges inward
            switch (direction) {
                case 'up':
                    // Move top edge down (shrink from top)
                    const shrinkAmount = Math.min(this.stepSize, roi.height - 5);
                    roi.y += shrinkAmount;
                    roi.height -= shrinkAmount;
                    break;
                case 'down':
                    // Move bottom edge up (shrink from bottom)
                    roi.height = Math.max(5, roi.height - this.stepSize);
                    break;
                case 'left':
                    // Move left edge right (shrink from left)
                    const shrinkX = Math.min(this.stepSize, roi.width - 5);
                    roi.x += shrinkX;
                    roi.width -= shrinkX;
                    break;
                case 'right':
                    // Move right edge left (shrink from right)
                    roi.width = Math.max(5, roi.width - this.stepSize);
                    break;
            }
        }

        this.updateROIVisual(roi);
    }

    /**
     * Update ROI visual representation
     * @param {Object} roi - ROI to update
     */
    updateROIVisual(roi) {
        const rectElement = document.getElementById(`roi-${roi.id}`);
        const labelElement = document.getElementById(`label-${roi.id}`);
        
        if (rectElement) {
            rectElement.setAttribute('x', roi.x);
            rectElement.setAttribute('y', roi.y);
            rectElement.setAttribute('width', roi.width);
            rectElement.setAttribute('height', roi.height);
        }
        
        if (labelElement) {
            labelElement.setAttribute('x', roi.x - 15);
            labelElement.setAttribute('y', roi.y + roi.height / 2 + 5);
        }
    }

    /**
     * Update all ROI visuals
     */
    updateAllROIVisuals() {
        this.rois.forEach(roi => this.updateROIVisual(roi));
    }

    /**
     * Highlight selected ROI
     */
    updateROISelection() {
        for (let i = 1; i <= 4; i++) {
            const rectElement = document.getElementById(`roi-${i}`);
            const labelElement = document.getElementById(`label-${i}`);
            
            if (i === this.selectedROI) {
                rectElement.classList.add('selected');
                labelElement.classList.add('selected');
            } else {
                rectElement.classList.remove('selected');
                labelElement.classList.remove('selected');
            }
        }
    }

    /**
     * Save configuration to JSON
     * @returns {Object} - Configuration object
     */
    getConfiguration() {
        return {
            rois: this.rois.map(roi => ({...roi})),
            timestamp: new Date().toISOString()
        };
    }

    /**
     * Load configuration from object
     * @param {Object} config - Configuration object
     */
    loadConfiguration(config) {
        if (config.rois && Array.isArray(config.rois)) {
            this.rois = config.rois.map(roi => ({...roi}));
            this.updateAllROIVisuals();
        }
    }

    /**
     * Reset to default configuration
     */
    resetToDefault() {
        this.rois = this.getDefaultROIs();
        this.selectedROI = 1;
        this.updateAllROIVisuals();
    }

    /**
     * Export configuration as downloadable JSON file
     */
    exportConfiguration() {
        const config = this.getConfiguration();
        const dataStr = JSON.stringify(config, null, 2);
        const blob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const link = document.createElement('a');
        link.href = url;
        link.download = 'roi-config.json';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }

    /**
     * Save configuration to localStorage
     */
    saveToLocalStorage() {
        const config = this.getConfiguration();
        localStorage.setItem('rpi_visual_config', JSON.stringify(config));
    }

    /**
     * Load configuration from localStorage
     * @returns {boolean} - True if loaded successfully
     */
    loadFromLocalStorage() {
        try {
            const configStr = localStorage.getItem('rpi_visual_config');
            if (configStr) {
                const config = JSON.parse(configStr);
                this.loadConfiguration(config);
                return true;
            }
        } catch (error) {
            console.error('Error loading configuration:', error);
        }
        return false;
    }
}

// Export for use in other modules
window.ROIManager = ROIManager;
