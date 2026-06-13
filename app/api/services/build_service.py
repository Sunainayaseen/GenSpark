"""
Build service - contains business logic for PC build recommendations.
"""

from flask import current_app
from app.core.database import get_db_connection


def generate_recommendation(payload: dict) -> dict:
    """
    Generate a PC build recommendation.
    
    This is a placeholder that will call:
    - configurator.advanced_pc_configurator() for deterministic builds
    - OpenAI API if configured
    
    Returns:
        Dictionary with markdown, model_id, source, and parts
    """
    try:
        # TODO: Call existing configurator logic
        # For now, return structure
        return {
            'markdown': '# PC Build Recommendation\n...',
            'model_id': 'genspark-rules-v1',
            'source': 'rules',
            'parts': {},
        }
    except Exception as exc:
        current_app.logger.exception('generate_recommendation error')
        raise


def persist_build(data: dict) -> dict:
    """
    Save custom PC build to database.
    
    Args:
        data: Build component names and metadata
    
    Returns:
        Build ID, total price, and matched products
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # TODO: Implement build persistence
        # This will match components and save to custom_builds table
        
        cursor.close()
        connection.close()
        
        return {
            'build_id': 1,
            'total_price': 0,
            'matched_products': {},
        }
    except Exception as exc:
        current_app.logger.exception('persist_build error')
        raise
