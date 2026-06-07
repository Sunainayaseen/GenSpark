"""
Standardized JSON response formatting for all API endpoints.
Ensures consistent response structure across the entire backend.
"""

from flask import jsonify


def success(data=None, message="Success", http_status=200, **extra):
    """
    Standard success response format.
    
    Args:
        data: Response payload (dict, list, or any serializable data)
        message: Human-readable message
        http_status: HTTP status code
        **extra: Additional fields to include in response
    
    Returns:
        Tuple of (response_dict, http_status)
    """
    response = {
        'success': True,
        'message': message,
        'data': data,
    }
    response.update(extra)
    return jsonify(response), http_status


def error(message, http_status=400, error_code=None, **extra):
    """
    Standard error response format.
    
    Args:
        message: Error description
        http_status: HTTP status code (400, 404, 500, etc.)
        error_code: Machine-readable error identifier (optional)
        **extra: Additional error context
    
    Returns:
        Tuple of (response_dict, http_status)
    """
    response = {
        'success': False,
        'message': message,
    }
    if error_code:
        response['error_code'] = error_code
    response.update(extra)
    return jsonify(response), http_status


def created(data=None, message="Created", **extra):
    """Success response with 201 Created status."""
    return success(data, message, 201, **extra)


def not_found(message="Resource not found", **extra):
    """Error response with 404 Not Found status."""
    return error(message, 404, error_code="NOT_FOUND", **extra)


def bad_request(message="Bad request", **extra):
    """Error response with 400 Bad Request status."""
    return error(message, 400, error_code="BAD_REQUEST", **extra)


def unauthorized(message="Unauthorized", **extra):
    """Error response with 401 Unauthorized status."""
    return error(message, 401, error_code="UNAUTHORIZED", **extra)


def forbidden(message="Forbidden", **extra):
    """Error response with 403 Forbidden status."""
    return error(message, 403, error_code="FORBIDDEN", **extra)


def server_error(message="Server error", **extra):
    """Error response with 500 Internal Server Error status."""
    return error(message, 500, error_code="SERVER_ERROR", **extra)
