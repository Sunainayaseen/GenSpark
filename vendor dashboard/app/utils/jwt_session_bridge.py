"""
Align Flask-Login session with JWT Bearer on /api/* (Vercel frontend → Railway backend).

Cart routes use current_user + session['cart_id']; they do not call jwt_required().
This bridge decodes Authorization: Bearer without relying on session cookies.
"""
from flask import current_app, request
from flask_jwt_extended import decode_token, get_jwt_identity, verify_jwt_in_request
from flask_login import current_user, login_user
from sqlalchemy import func


def extract_bearer_token():
    """Authorization header value after 'Bearer ' (or None)."""
    auth = (request.headers.get('Authorization') or '').strip()
    if not auth:
        return None
    parts = auth.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == 'bearer' and parts[1].strip():
        return parts[1].strip()
    return None


def _jwt_sub(decoded):
    if not decoded or not isinstance(decoded, dict):
        return None
    sub = decoded.get('sub')
    if sub is None:
        return None
    try:
        return int(sub)
    except (TypeError, ValueError):
        return None


def _jwt_secrets_for_decode():
    """All keys to try (Railway may only set SECRET_KEY or JWT_SECRET_KEY)."""
    keys = []
    for name in ('JWT_SECRET_KEY', 'SECRET_KEY'):
        value = current_app.config.get(name)
        if value and value not in keys:
            keys.append(value)
    return keys


def user_from_bearer_token_string(token):
    """Decode JWT string and load User — no @jwt_required or session cookies."""
    if not token:
        return None

    user_id = None
    try:
        user_id = _jwt_sub(decode_token(token))
    except Exception:
        pass

    if user_id is None:
        try:
            import jwt

            for secret in _jwt_secrets_for_decode():
                try:
                    decoded = jwt.decode(
                        token,
                        secret,
                        algorithms=['HS256'],
                        options={'verify_aud': False},
                    )
                    user_id = _jwt_sub(decoded)
                    if user_id is not None:
                        break
                except Exception:
                    continue
        except Exception:
            pass

    if user_id is None:
        return None

    from app.models import User

    user = User.query.get(user_id)
    if not user:
        return None
    if getattr(user, 'status', 'active') != 'active':
        return None
    return user


def _user_from_jwt_token(token):
    return user_from_bearer_token_string(token)


def user_from_authorization_header():
    """Manual Bearer parse from Authorization (production-safe)."""
    auth_header = (request.headers.get('Authorization') or '').strip()
    if not auth_header:
        return None
    parts = auth_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return None
    return user_from_bearer_token_string(parts[1].strip())


def resolve_change_password_user(email, current_password):
    """
    Resolve User for POST /api/change-password.
    1) Authorization: Bearer (manual header parse + JWT decode)
    2) JSON email + current_password (one-time login password)
    Never uses @login_required. Returns (user, error_dict, http_status) or (user, None, None).
    """
    user = user_from_authorization_header()

    if user is None and email and current_password:
        candidate = find_user_by_email(email)
        if not candidate:
            return None, {
                'success': False,
                'error': 'No account found for this email',
            }, 404
        if not candidate.check_password(current_password):
            return None, {
                'success': False,
                'error': 'Current password is wrong',
            }, 400
        user = candidate

    if user is None:
        return None, {
            'success': False,
            'error': (
                'Could not verify your account. Use the one-time password you used to log in '
                '(not the new password), or sign in again.'
            ),
        }, 401

    return user, None, None


def find_user_by_email(email):
    """Case-insensitive email lookup (DB may store mixed case from admin import)."""
    normalized = (email or '').strip().lower()
    if not normalized:
        return None
    from app.models import User

    return User.query.filter(func.lower(User.email) == normalized).first()


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
        user = user_from_bearer_token_string(token)
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
