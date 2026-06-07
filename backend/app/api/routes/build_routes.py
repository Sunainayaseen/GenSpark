"""
PC Build recommendation and creation endpoints.
Routes for AI-powered build suggestions and custom build persistence.
"""

from flask import Blueprint, request, current_app

from app.core.responses import success, error, bad_request, server_error
from app.api.controllers import build_controller

bp = Blueprint('build', __name__, url_prefix='/api')


@bp.route('/recommend-build', methods=['POST', 'OPTIONS'])
def recommend_build():
    """
    POST /api/recommend-build - Get PC build recommendation.
    
    Request body (JSON):
        {
            "message": "I need a gaming PC",
            "build_requested": true,
            "budget": "100000 PKR",
            "purpose": "Gaming",
            "detected_parts": []
        }
    
    Returns:
        Build recommendation with markdown specification
    """
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json(silent=True) or {}
        result = build_controller.get_build_recommendation(data)
        return success(data=result, message='Build recommendation generated')
    except ValueError as exc:
        return bad_request(str(exc))
    except Exception as exc:
        current_app.logger.exception('recommend_build failed')
        return server_error(str(exc))


@bp.route('/create-build', methods=['POST', 'OPTIONS'])
def create_build():
    """
    POST /api/create-build - Save custom PC build to database.
    
    Request body (JSON):
        {
            "cpu": "Intel Core i7",
            "gpu": "RTX 4070",
            "motherboard": "B760",
            "ram": "32GB DDR5",
            "storage": "1TB NVMe SSD",
            "psu": "850W Gold",
            "case": "Corsair Spec-05",
            "user_id": null,
            "name": "Gaming Build 2024"
        }
    
    Returns:
        Created build details with ID and total price
    """
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json(silent=True) or {}
        result = build_controller.create_custom_build(data)
        return success(data=result, message='Build created successfully', http_status=201)
    except ValueError as exc:
        return bad_request(str(exc))
    except Exception as exc:
        current_app.logger.exception('create_build failed')
        return server_error(str(exc))
