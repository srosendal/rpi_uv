/**
 * Image Analyzer Module
 * Handles ROI intensity calculations from images
 */

class ImageAnalyzer {
    constructor() {
        this.canvas = document.createElement('canvas');
        this.ctx = this.canvas.getContext('2d');
    }

    /**
     * Calculate average intensity within a ROI
     * @param {HTMLImageElement} img - The image to analyze
     * @param {Object} roi - ROI definition {x, y, width, height}
     * @returns {number} - Average intensity value (0-255)
     */
    calculateROIIntensity(img, roi) {
        // Set canvas size to image size
        this.canvas.width = img.width;
        this.canvas.height = img.height;
        
        // Draw image to canvas
        this.ctx.drawImage(img, 0, 0);
        
        // Get pixel data from ROI region
        try {
            const imageData = this.ctx.getImageData(roi.x, roi.y, roi.width, roi.height);
            const data = imageData.data;
            
            let totalIntensity = 0;
            let pixelCount = 0;
            
            // Calculate average grayscale value
            // Iterate through pixels (RGBA format, 4 values per pixel)
            for (let i = 0; i < data.length; i += 4) {
                const r = data[i];
                const g = data[i + 1];
                const b = data[i + 2];
                // Calculate grayscale using luminosity method
                const gray = 0.299 * r + 0.587 * g + 0.114 * b;
                totalIntensity += gray;
                pixelCount++;
            }
            
            const avgIntensity = pixelCount > 0 ? totalIntensity / pixelCount : 0;
            return Math.round(avgIntensity);
        } catch (error) {
            console.error('Error analyzing ROI:', error);
            return 0;
        }
    }

    /**
     * Analyze all ROIs in an image
     * @param {HTMLImageElement} img - The image to analyze
     * @param {Array} rois - Array of ROI definitions
     * @returns {Array} - Array of intensity values
     */
    analyzeAllROIs(img, rois) {
        const results = [];
        for (let i = 0; i < rois.length; i++) {
            const intensity = this.calculateROIIntensity(img, rois[i]);
            results.push(intensity);
        }
        return results;
    }

    /**
     * Perform 3-capture average analysis
     * @param {HTMLImageElement} img - The image to analyze (same for all 3 captures in simulation)
     * @param {Array} rois - Array of ROI definitions
     * @param {Function} progressCallback - Called for each capture (optional)
     * @returns {Promise<Array>} - Array of averaged intensity values
     */
    async analyze3Captures(img, rois, progressCallback = null) {
        const captures = [];
        
        // Simulate 3 captures
        for (let i = 0; i < 3; i++) {
            if (progressCallback) {
                progressCallback(i + 1);
            }
            
            // Simulate capture delay
            await new Promise(resolve => setTimeout(resolve, 200));
            
            // Analyze current image
            const results = this.analyzeAllROIs(img, rois);
            captures.push(results);
        }
        
        // Calculate average across 3 captures
        const avgResults = [];
        for (let roiIdx = 0; roiIdx < rois.length; roiIdx++) {
            let sum = 0;
            for (let captureIdx = 0; captureIdx < 3; captureIdx++) {
                sum += captures[captureIdx][roiIdx];
            }
            avgResults.push(Math.round(sum / 3));
        }
        
        return avgResults;
    }
}

// Export for use in other modules
window.ImageAnalyzer = ImageAnalyzer;
