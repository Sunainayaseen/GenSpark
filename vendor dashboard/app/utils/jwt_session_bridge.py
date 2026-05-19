"""
Align Flask-Login session with JWT Bearer on /api/* (Vercel frontend → Railway backend).

Cart routes use current_user + session['cart_id']; they do not call jwt_required().
This bridge decodes Authorization: Bearer without relying on session cookies.
"""
from flask import request
from flask_jwt_extended import decode_token, get_jwt_identity, verify_jwt_in_request
from flask_login import current_user, login_user


def extract_bearer_token():
    """Authorization header value after 'Bearer ' (or None)."""
    auth = (request.headers.get('Authorization') or '').strip()
    if not auth:
        return None
    parts = auth.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == 'bearer' and parts[1].strip():
        return parts[1].strip()
    return None


def _user_from_jwt_token(token):
    """Decode JWT and load User — does not use @jwt_required or session cookies."""
    if not token:
        return None
    try:
        decoded = decode_token(token)
    except Exception:
        return None
    sub = decoded.get('sub')
    if sub is None:
        return None
    from app.models import User

    user = User.query.get(int(sub))
    if not user:
        return None
    if getattr(user, 'status', 'active') != 'active':
        return None
    return user


def sync_flask_login_from_jwt():
    """Attach Flask-Login session from Bearer token when cookies are unavailable."""
    if current_user.is_authenticated:
        return
    user = resolve_api_user()
    if user:
        login_user(user, remember=False)


def resolve_api_user():
    """
    Resolve User from Bearer JWT and/or Flask-Login session.
    Safe for cross-origin (Vercel → Railway) without @login_required.
    """
    token = extract_bearer_token()
    if token:
        user = _user_from_jwt_token(token)
        if user:
            return user

    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id is not None:
            from app.models import User

            user = User.query.get(int(user_id))
            if user:
                return user
    except Exception:
        pass

    if current_user.is_authenticated:
        from app.models import User

        return User.query.get(current_user.id)
    return None
