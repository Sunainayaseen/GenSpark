"""
Detection service - YOLO image processing for component detection.
"""

from flask import current_app
from pathlib import Path
from app.common.constants import YOLO_CLASS_NAMES


def process_image_from_request(request) -> list[dict]:
    """
    Process image from HTTP request and run YOLO detection.
    
    Supports:
    - Multipart file upload (key: 'image')
    - JSON body with base64 image (key: 'image')
    
    Returns:
        List of detections with class, confidence, and bounding box
    """
    try:
        # TODO: Extract image from request
        # TODO: Run YOLO model
        # TODO: Format detections
        return []
    except Exception as exc:
        current_app.logger.exception('process_image_from_request error')
        raise


def get_model_info() -> dict:
    """
    Get information about YOLO model (path, loaded status, class names).
    
    Returns:
        Dictionary with model metadata
    """
    try:
        model_path = Path(__file__).parent.parent.parent.parent / 'best.pt'
        
        return {
            'model_path': str(model_path),
            'exists': model_path.is_file(),
            'classes': YOLO_CLASS_NAMES,
            'model_name': 'YOLOv8 Component Detector',
        }
    except Exception as exc:
        current_app.logger.exception('get_model_info error')
        raise
