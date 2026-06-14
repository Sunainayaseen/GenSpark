"""
Health check and status endpoints.
No database access - used to verify Flask is running.
"""

from flask import Blueprint, make_response

bp = Blueprint('health', __name__, url_prefix='/api')


@bp.route('/health', methods=['GET'])
def health_check():
    """GET /api/health - Minimal health check (no DB)."""
    response = make_response('OK', 200)
    response.headers['Content-Type'] = 'text/plain; charset=utf-8'
    return response


@bp.route('/ping', methods=['GET', 'POST'])
def ping():
    """GET/POST /api/ping - Echo endpoint for connectivity testing."""
    from app.core.responses import success
    return success(message='pong', http_status=200)
