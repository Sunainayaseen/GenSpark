"""
Detection controller - handles YOLO image processing.
"""

from flask import current_app
from app.api.services import detection_service


def detect_components_from_request(request) -> list[dict]:
    """
    Detect components from image in HTTP request.
    
    Supports:
    - Multipart form with 'image' file
    - JSON body with 'image' base64 string
    
    Returns:
        List of detections with confidence and bounding boxes
    """
    try:
        detections = detection_service.process_image_from_request(request)
        return detections
    except Exception as exc:
        current_app.logger.exception('detect_components_from_request error')
        raise


def get_model_status() -> dict:
    """Get YOLO model status and file information."""
    try:
        return detection_service.get_model_info()
    except Exception as exc:
        current_app.logger.exception('get_model_status error')
        raise
