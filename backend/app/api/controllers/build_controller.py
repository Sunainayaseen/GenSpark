"""
Build controller - handles PC build business logic.
Bridges routes and services layer.
"""

from flask import current_app
from app.api.services import build_service
from app.api.services import component_service


def get_build_recommendation(payload: dict) -> dict:
    """
    Get PC build recommendation based on user input.
    
    Args:
        payload: User request with message, budget, purpose, etc.
    
    Returns:
        Dictionary with recommendation markdown and metadata
    """
    try:
        recommendation = build_service.generate_recommendation(payload)
        return {
            'markdown': recommendation.get('markdown'),
            'model_id': recommendation.get('model_id'),
            'source': recommendation.get('source'),
            'parts': recommendation.get('parts'),
        }
    except Exception as exc:
        current_app.logger.exception('get_build_recommendation error')
        raise


def create_custom_build(data: dict) -> dict:
    """
    Create and save a custom PC build.
    
    Args:
        data: Build component names and metadata
    
    Returns:
        Dictionary with build_id, total_price, and matched products
    """
    try:
        # Validate required parts
        required_parts = ['cpu', 'ram', 'storage']
        for part in required_parts:
            if not data.get(part, '').strip():
                raise ValueError(f'Required part missing: {part}')
        
        # Save to database
        result = build_service.persist_build(data)
        return result
    except Exception as exc:
        current_app.logger.exception('create_custom_build error')
        raise
