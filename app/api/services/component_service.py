"""
Component service - database operations for component catalog.
"""

from flask import current_app
from app.core.database import get_db_connection
from app.common.constants import YOLO_CLASS_NAMES


def search_catalog(query: str, category: str = '', limit: int = 20) -> list[dict]:
    """
    Search components in database by name and optional category.
    
    Args:
        query: Search term
        category: Optional category filter (CPU, GPU, RAM, etc.)
        limit: Max results
    
    Returns:
        List of component records
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        search_term = f'%{query}%'
        
        if category:
            sql = '''
                SELECT id, name, category, price, stock
                FROM components
                WHERE name LIKE %s AND category = %s
                LIMIT %s
            '''
            cursor.execute(sql, (search_term, category, limit))
        else:
            sql = '''
                SELECT id, name, category, price, stock
                FROM components
                WHERE name LIKE %s
                LIMIT %s
            '''
            cursor.execute(sql, (search_term, limit))
        
        results = cursor.fetchall()
        cursor.close()
        connection.close()
        
        return results if results else []
    except Exception as exc:
        current_app.logger.exception('search_catalog error')
        raise


def find_component_by_name(name: str, category: str = '') -> dict | None:
    """
    Find component by exact or fuzzy name match.
    
    Args:
        name: Component name to search for
        category: Optional category for more precise match
    
    Returns:
        Component record or None if not found
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Try exact match first
        if category:
            sql = 'SELECT * FROM components WHERE name = %s AND category = %s LIMIT 1'
            cursor.execute(sql, (name, category))
        else:
            sql = 'SELECT * FROM components WHERE name = %s LIMIT 1'
            cursor.execute(sql, (name,))
        
        result = cursor.fetchone()
        
        # Fallback to fuzzy match if exact not found
        if not result:
            fuzzy_name = f'%{name}%'
            if category:
                sql = 'SELECT * FROM components WHERE name LIKE %s AND category = %s LIMIT 1'
                cursor.execute(sql, (fuzzy_name, category))
            else:
                sql = 'SELECT * FROM components WHERE name LIKE %s LIMIT 1'
                cursor.execute(sql, (fuzzy_name,))
            result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        return result
    except Exception as exc:
        current_app.logger.exception('find_component_by_name error')
        raise


def get_vendors_for_component(component_id: int) -> dict | None:
    """
    Get all vendors and their pricing for a component.
    
    Returns:
        Dictionary with component details and vendors list
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get component details
        sql = 'SELECT id, name, category, price FROM components WHERE id = %s'
        cursor.execute(sql, (component_id,))
        component = cursor.fetchone()
        
        if not component:
            return None
        
        # Get vendors
        sql = '''
            SELECT v.id, v.shop_name, v.city, v.phone,
                   vc.quantity as available_quantity, vc.price as vendor_price
            FROM vendor_components vc
            JOIN vendors v ON vc.vendor_id = v.id
            WHERE vc.component_id = %s AND vc.quantity > 0
        '''
        cursor.execute(sql, (component_id,))
        vendors = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return {
            'component': component,
            'vendors': vendors,
            'count': len(vendors),
        }
    except Exception as exc:
        current_app.logger.exception('get_vendors_for_component error')
        raise
