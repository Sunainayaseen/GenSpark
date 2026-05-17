"""Public URLs for emails, OAuth redirects, and API links."""
from flask import current_app

# Live Railway API (used when PREFERRED_URL is unset on cloud)
DEFAULT_PRODUCTION_API_URL = 'https://genspark-production.up.railway.app'


def get_api_base_url():
    """Backend URL for /api/* links in emails (email verification, etc.)."""
    base = (current_app.config.get('PREFERRED_URL') or '').strip()
    if not base:
        base = DEFAULT_PRODUCTION_API_URL if _is_cloud() else 'http://127.0.0.1:5000'
    return base.rstrip('/')


def get_frontend_url():
    """React app URL for OAuth redirects and portal links."""
    base = (current_app.config.get('FRONTEND_URL') or '').strip()
    if not base:
        base = get_api_base_url()
    return base.rstrip('/').split('?')[0]


def _is_cloud():
    import os
    return bool(
        os.getenv('RAILWAY_ENVIRONMENT')
        or os.getenv('RAILWAY_PROJECT_ID')
        or os.getenv('RENDER')
    )
