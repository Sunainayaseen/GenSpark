"""
Component controller - handles component catalog operations.
"""

from flask import current_app
from app.api.services import component_service


def search_components(query: str, category: str = '', limit: int = 20) -> dict:
    """
    Search for components in catalog.
    
    Args:
        query: Search term
        category: Optional category filter
        limit: Max results
    
    Returns:
        Dictionary with components list and total count
    """
    try:
        if not query and not category:
            return {'components': [], 'count': 0}
        
        results = component_service.search_catalog(query, category, limit)
        return {
            'components': results,
            'count': len(results),
            'query': query,
            'category': category,
        }
    except Exception as exc:
        current_app.logger.exception('search_components error')
        raise


def resolve_component(name: str, category: str = '') -> dict | None:
    """Resolve a component name to database record."""
    try:
        return component_service.find_component_by_name(name, category)
    except Exception as exc:
        current_app.logger.exception('resolve_component error')
        raise


def get_vendors_for_component(component_id: int) -> dict | None:
    """Get all vendors selling a specific component."""
    try:
        return component_service.get_vendors_for_component(component_id)
    except Exception as exc:
        current_app.logger.exception('get_vendors_for_component error')
        raise
