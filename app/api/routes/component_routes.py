"""
Component catalog endpoints.
Search, browse, and manage PC components.
"""

from flask import Blueprint, request, current_app

from app.core.responses import success, error, bad_request, not_found, server_error
from app.api.controllers import component_controller

bp = Blueprint('component', __name__, url_prefix='/api')


@bp.route('/components/search', methods=['GET'])
def search_components():
    """
    GET /api/components/search - Search for components.
    
    Query parameters:
        q: Search query (component name, model, etc.)
        category: Filter by category (CPU, GPU, RAM, etc.)
        limit: Max results (default 20)
    
    Returns:
        List of matching components with prices and availability
    """
    try:
        query = request.args.get('q', '').strip()
        category = request.args.get('category', '').strip()
        limit = int(request.args.get('limit', '20'))
        
        result = component_controller.search_components(query, category, limit)
        return success(data=result, message='Search completed')
    except ValueError as exc:
        return bad_request(str(exc))
    except Exception as exc:
        current_app.logger.exception('search_components failed')
        return server_error(str(exc))


@bp.route('/components/<int:component_id>/vendors', methods=['GET'])
def get_component_vendors(component_id):
    """
    GET /api/components/<id>/vendors - Get vendors selling a component.
    
    Returns:
        List of vendors with stock and pricing for the component
    """
    try:
        result = component_controller.get_vendors_for_component(component_id)
        if not result:
            return not_found(f'Component {component_id} not found')
        return success(data=result, message='Vendors retrieved')
    except Exception as exc:
        current_app.logger.exception('get_component_vendors failed')
        return server_error(str(exc))


@bp.route('/components/resolve', methods=['POST'])
def resolve_component():
    """
    POST /api/components/resolve - Resolve component name to database record.
    
    Request body:
        {
            "name": "RTX 4070",
            "category": "GPU"
        }
    
    Returns:
        Component details if found
    """
    try:
        data = request.get_json(silent=True) or {}
        name = data.get('name', '').strip()
        category = data.get('category', '').strip()
        
        if not name:
            return bad_request('Component name required')
        
        result = component_controller.resolve_component(name, category)
        if not result:
            return not_found(f'Component "{name}" not found in catalog')
        
        return success(data=result, message='Component resolved')
    except Exception as exc:
        current_app.logger.exception('resolve_component failed')
        return server_error(str(exc))
