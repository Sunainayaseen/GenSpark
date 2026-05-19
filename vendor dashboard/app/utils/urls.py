"""Public URLs for emails, OAuth redirects, and API links."""
import os
from urllib.parse import urlparse

from flask import current_app

# Railway Flask API — used for /api/verify-email and other backend links in email
DEFAULT_PRODUCTION_API_URL = 'https://genspark-production.up.railway.app'
LOCAL_API_URL = 'http://127.0.0.1:5000'

# Email verification links MUST use this host in production (never Vercel SPA).
PRODUCTION_VERIFY_EMAIL_API_BASE = DEFAULT_PRODUCTION_API_URL

# Host fragments that must never be used as the API base (frontend / Vite)
_FRONTEND_HOST_MARKERS = (
    'vercel.app',
    'localhost:5173',
    '127.0.0.1:5173',
    'localhost:4173',
    '127.0.0.1:4173',
    'localhost:3000',
    '127.0.0.1:3000',
)


def _is_cloud():
    return bool(
        os.getenv('RAILWAY_ENVIRONMENT')
        or os.getenv('RAILWAY_PROJECT_ID')
        or os.getenv('RAILWAY_SERVICE_NAME')
        or os.getenv('RENDER')
        or os.getenv('PORT')
    )


def _is_production_deploy():
    """True on Railway/production — verification links must use Railway API base."""
    if os.getenv('FLASK_ENV', '').strip().lower() == 'production':
        return True
    return _is_cloud()


def _is_frontend_origin(url: str) -> bool:
    """True if URL points at the React app, not the Flask API."""
    raw = (url or '').strip().lower()
    if not raw:
        return False
    try:
        host = urlparse(raw if '://' in raw else f'https://{raw}').netloc.lower()
    except Exception:
        host = raw
    return any(marker in host for marker in _FRONTEND_HOST_MARKERS)


def _explicit_backend_url():
    """Env vars that must refer to Flask/Railway only (not Vercel)."""
    for key in ('API_BASE_URL', 'BACKEND_URL', 'RAILWAY_PUBLIC_URL'):
        value = (os.getenv(key) or '').strip().rstrip('/')
        if value and not _is_frontend_origin(value):
            return value
    domain = (os.getenv('RAILWAY_PUBLIC_DOMAIN') or '').strip()
    if domain and 'vercel' not in domain.lower():
        return f'https://{domain}'.rstrip('/')
    return ''


def get_api_base_url():
    """
    Backend origin for /api/* links in emails (verification, etc.).
    Never uses the Vercel frontend URL even if PREFERRED_URL is misconfigured.
    """
    if _is_production_deploy():
        return DEFAULT_PRODUCTION_API_URL

    explicit = _explicit_backend_url()
    if explicit:
        return explicit

    preferred = (current_app.config.get('PREFERRED_URL') or '').strip().rstrip('/')
    if preferred and _is_frontend_origin(preferred):
        try:
            current_app.logger.warning(
                'PREFERRED_URL is a frontend host (%s); using local API URL for email/API links.',
                preferred,
            )
        except RuntimeError:
            pass
        preferred = ''

    if not preferred:
        preferred = LOCAL_API_URL

    return preferred.rstrip('/')


def build_verify_email_url(token: str) -> str:
    """
    Absolute URL for GET /api/verify-email — always Flask on Railway in production.

    Production/Railway: hardcoded PRODUCTION_VERIFY_EMAIL_API_BASE (never Vercel, never PREFERRED_URL).
    Local dev: http://127.0.0.1:5000 (or VERIFY_EMAIL_API_BASE if set and not a frontend host).
    """
    if not token:
        raise ValueError('token required for verify-email URL')

    if _is_production_deploy():
        base = PRODUCTION_VERIFY_EMAIL_API_BASE
    else:
        override = (os.getenv('VERIFY_EMAIL_API_BASE') or '').strip().rstrip('/')
        if override and not _is_frontend_origin(override):
            base = override
        else:
            base = LOCAL_API_URL

    url = f'{base.rstrip("/")}/api/verify-email?token={token}'
    if _is_frontend_origin(url):
        if _is_production_deploy():
            url = f'{PRODUCTION_VERIFY_EMAIL_API_BASE.rstrip("/")}/api/verify-email?token={token}'
        else:
            raise ValueError('verify-email URL must not use the frontend host')
    return url


def get_frontend_url():
    """React app URL for OAuth redirects and portal links."""
    base = (current_app.config.get('FRONTEND_URL') or '').strip()
    if not base:
        if _is_cloud():
            return 'https://genspark-frontend.vercel.app'
        return 'http://127.0.0.1:5173'
    return base.rstrip('/').split('?')[0]


def build_api_url(path: str) -> str:
    """Absolute API URL, e.g. build_api_url('/verify-email?token=abc')."""
    base = get_api_base_url()
    p = path if path.startswith('/') else f'/{path}'
    if p.startswith('/api/'):
        return f'{base}{p}'
    return f'{base}/api{p}'
