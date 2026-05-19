"""
Align Flask-Login session with JWT Bearer on /api/* (Vercel frontend → Railway backend).

Cart routes use current_user + session['cart_id']; they do not call jwt_required().
This bridge lets the existing login flow (JWT in Authorization header) activate the
same session cart logic without changing cart_controller business rules.
"""
from flask_login import current_user, login_user
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request


def sync_flask_login_from_jwt():
    if current_user.is_authenticated:
        return
    verify_jwt_in_request(optional=True)
    user_id = get_jwt_identity()
    if user_id is None:
        return
    from app.models import User

    user = User.query.get(int(user_id))
    if not user:
        return
    if getattr(user, 'status', 'active') != 'active':
        return
    login_user(user, remember=False)
