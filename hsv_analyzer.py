#!/usr/bin/env python3
"""
HSV-based Color Analysis for Test Strip Bands
Uses OpenCV to count pixels within HSV threshold ranges for each ROI
"""

import cv2
import numpy as np
from pathlib import Path


class HSVAnalyzer:
    """
    Analyzes test strip images using HSV color space thresholding
    Counts pixels within specified HSV ranges for each ROI
    """
    
    # ============================================
    # HSV THRESHOLD CONFIGURATION
    # ============================================
    # Adjust these values to match your test strip colors
    # HSV ranges: H(0-179), S(0-255), V(0-255)
    
    # Example: For detecting colored bands (red, blue, purple, etc.)
    # You can define multiple color ranges or use a single general range
    
    # General range for bright colored bands (default)
    HSV_LOWER = np.array([0, 50, 50])      # [H_min, S_min, V_min]
    HSV_UPPER = np.array([179, 255, 255])  # [H_max, S_max, V_max]
    
    # Alternative examples (uncomment and adjust as needed):
    
    # For RED colored bands:
    # HSV_LOWER = np.array([0, 100, 100])
    # HSV_UPPER = np.array([10, 255, 255])
    
    # For BLUE colored bands:
    # HSV_LOWER = np.array([100, 100, 100])
    # HSV_UPPER = np.array([130, 255, 255])
    
    # For PURPLE colored bands:
    # HSV_LOWER = np.array([130, 50, 50])
    # HSV_UPPER = np.array([160, 255, 255])
    
    # For YELLOW colored bands:
    # HSV_LOWER = np.array([20, 100, 100])
    # HSV_UPPER = np.array([30, 255, 255])
    
    # For detecting ANY saturated color (broad range):
    # HSV_LOWER = np.array([0, 80, 80])
    # HSV_UPPER = np.array([179, 255, 255])
    
    # ============================================
    
    def __init__(self, hsv_lower=None, hsv_upper=None):
        """
        Initialize analyzer with custom HSV thresholds
        
        Args:
            hsv_lower: Lower HSV bound as numpy array [H, S, V] or None for default
            hsv_upper: Upper HSV bound as numpy array [H, S, V] or None for default
        """
        self.hsv_lower = hsv_lower if hsv_lower is not None else self.HSV_LOWER
        self.hsv_upper = hsv_upper if hsv_upper is not None else self.HSV_UPPER
        
    def analyze_image(self, image_path, rois):
        """
        Analyze image and return pixel counts for each ROI
        
        Args:
            image_path: Path to image file
            rois: List of ROI dictionaries with keys: x, y, width, height
        
        Returns:
            List of pixel counts for each ROI [count1, count2, count3, count4]
        """
        # Load image
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        # Convert to HSV color space
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Create mask based on HSV thresholds
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        
        # Analyze each ROI
        results = []
        for roi in rois:
            count = self._count_pixels_in_roi(mask, roi)
            results.append(count)
        
        return results
    
    def analyze_image_array(self, img_array, rois):
        """
        Analyze image from numpy array and return pixel counts for each ROI
        
        Args:
            img_array: Image as numpy array (BGR format)
            rois: List of ROI dictionaries with keys: x, y, width, height
        
        Returns:
            List of pixel counts for each ROI [count1, count2, count3, count4]
        """
        if img_array is None:
            raise ValueError("Image array is None")
        
        # Convert to HSV color space
        hsv = cv2.cvtColor(img_array, cv2.COLOR_BGR2HSV)
        
        # Create mask based on HSV thresholds
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        
        # Analyze each ROI
        results = []
        for roi in rois:
            count = self._count_pixels_in_roi(mask, roi)
            results.append(count)
        
        return results
    
    def _count_pixels_in_roi(self, mask, roi):
        """
        Count white pixels (matched color) in ROI region
        
        Args:
            mask: Binary mask image (white = matched color, black = no match)
            roi: Dictionary with keys: x, y, width, height
        
        Returns:
            int: Number of pixels matching the HSV threshold in this ROI
        """
        x = int(roi['x'])
        y = int(roi['y'])
        w = int(roi['width'])
        h = int(roi['height'])
        
        # Extract ROI from mask
        roi_mask = mask[y:y+h, x:x+w]
        
        # Count white pixels (value 255)
        pixel_count = cv2.countNonZero(roi_mask)
        
        return pixel_count
    
    def analyze_3_captures(self, image_paths, rois):
        """
        Analyze 3 images and return averaged results
        
        Args:
            image_paths: List of 3 image paths
            rois: List of ROI dictionaries
        
        Returns:
            List of averaged pixel counts for each ROI
        """
        all_results = []
        
        for img_path in image_paths:
            results = self.analyze_image(img_path, rois)
            all_results.append(results)
        
        # Average the results
        num_rois = len(all_results[0])
        averaged = []
        
        for i in range(num_rois):
            sum_count = sum(result[i] for result in all_results)
            avg_count = round(sum_count / len(all_results))
            averaged.append(avg_count)
        
        return averaged
    
    def get_threshold_info(self):
        """
        Get current HSV threshold configuration
        
        Returns:
            Dictionary with threshold information
        """
        return {
            'hsv_lower': self.hsv_lower.tolist(),
            'hsv_upper': self.hsv_upper.tolist(),
            'description': 'HSV thresholds for color detection'
        }
    
    def save_debug_image(self, image_path, rois, output_path):
        """
        Save a debug image showing the mask and ROIs (useful for calibration)
        
        Args:
            image_path: Path to input image
            rois: List of ROI dictionaries
            output_path: Path to save debug image
        """
        # Load image
        img = cv2.imread(str(image_path))
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Create mask
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        
        # Convert mask to 3-channel for visualization
        mask_colored = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        
        # Draw ROIs on both original and mask
        for i, roi in enumerate(rois):
            x, y, w, h = int(roi['x']), int(roi['y']), int(roi['width']), int(roi['height'])
            
            # Draw rectangle
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.rectangle(mask_colored, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            # Add label
            cv2.putText(img, f'ROI {i+1}', (x, y-5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.putText(mask_colored, f'ROI {i+1}', (x, y-5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Combine images side by side
        combined = np.hstack([img, mask_colored])
        
        # Save
        cv2.imwrite(str(output_path), combined)
        print(f"Debug image saved to: {output_path}")


# Quick test function
if __name__ == '__main__':
    """
    Test the analyzer with a sample image
    Run: python3 hsv_analyzer.py
    """
    
    # Example ROIs (adjust to match your setup)
    test_rois = [
        {'x': 125, 'y': 95, 'width': 150, 'height': 20},
        {'x': 125, 'y': 145, 'width': 150, 'height': 20},
        {'x': 125, 'y': 195, 'width': 150, 'height': 20},
        {'x': 125, 'y': 245, 'width': 150, 'height': 20}
    ]
    
    # Test with a sample image
    test_image = Path('static/test_images/test_20251006_155017_279.png')
    
    if test_image.exists():
        analyzer = HSVAnalyzer()
        
        print("HSV Analyzer Test")
        print("=" * 50)
        print(f"HSV Lower: {analyzer.hsv_lower}")
        print(f"HSV Upper: {analyzer.hsv_upper}")
        print("=" * 50)
        
        results = analyzer.analyze_image(test_image, test_rois)
        
        print("\nResults:")
        for i, count in enumerate(results):
            print(f"  ROI {i+1}: {count} pixels")
        
        # Save debug image
        debug_path = Path('debug_hsv_analysis.png')
        analyzer.save_debug_image(test_image, test_rois, debug_path)
        
    else:
        print(f"Test image not found: {test_image}")
        print("Place a test image in the static/test_images/ directory to test")
