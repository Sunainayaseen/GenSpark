"""
Component detection endpoints.
Uses YOLO to detect PC components from images.
"""

from flask import Blueprint, request, current_app

from app.core.responses import success, error, bad_request, server_error
from app.api.controllers import detection_controller

bp = Blueprint('detect', __name__, url_prefix='/api')


@bp.route('/detect/component', methods=['POST'])
def detect_component():
    """
    POST /api/detect/component - Detect components in an image.
    
    Request: multipart form data with 'image' file or JSON with base64 image
    
    Returns:
        List of detected components with confidence scores and bounding boxes
    """
    try:
        result = detection_controller.detect_components_from_request(request)
        return success(data=result, message='Detection completed')
    except ValueError as exc:
        return bad_request(str(exc))
    except Exception as exc:
        current_app.logger.exception('detect_component failed')
        return server_error(str(exc))


@bp.route('/detect/model', methods=['GET'])
def get_model_info():
    """GET /api/detect/model - Get YOLO model information and status."""
    try:
        result = detection_controller.get_model_status()
        return success(data=result, message='Model info retrieved')
    except Exception as exc:
        current_app.logger.exception('get_model_info failed')
        return server_error(str(exc))
