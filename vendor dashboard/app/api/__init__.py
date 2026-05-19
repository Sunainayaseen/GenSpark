from flask import Blueprint, request

api_bp = Blueprint('api', __name__)


@api_bp.before_request
def _api_sync_jwt_to_session():
    """Let Bearer JWT satisfy Flask-Login on API routes (production cross-origin cart)."""
    if request.method == 'OPTIONS':
        return None
    # change-password uses email + OTP only — no session/JWT bridge
    if request.endpoint == 'api.api_change_password':
        return None
    from app.utils.jwt_session_bridge import sync_flask_login_from_jwt

    sync_flask_login_from_jwt()
    return None


from app.api import routes  # noqa: E402
