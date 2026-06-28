"""Security-hardening tests for the audit fixes H3 (signup role allowlist) and
H2 (password-reset gate).

Run from the Dashboard/ folder:  python -m pytest
"""
import pytest

from app import db
from app.models import User, Role


def _seed_roles():
    for name in ('admin', 'vendor', 'customer', 'rider'):
        if not Role.query.filter_by(name=name).first():
            db.session.add(Role(name=name))
    db.session.commit()


def _make_user(email, password, must_change, role='customer'):
    _seed_roles()
    r = Role.query.filter_by(name=role).first()
    u = User(name='U', email=email, role_id=r.id, status='active',
             must_change_password=must_change)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return u


# --- H3: self-service signup may only create customer/vendor ----------------

@pytest.mark.parametrize('requested_role', ['admin', 'rider', 'superuser'])
def test_signup_rejects_privileged_roles(client, db_session, requested_role):
    """H3 — a privileged/unknown role in the signup form is forced to customer."""
    _seed_roles()
    email = f'{requested_role}@test.com'
    client.post('/auth/signup', data={
        'name': 'Mallory', 'email': email,
        'password': 'secret123', 'role': requested_role,
    })
    user = User.query.filter_by(email=email).first()
    assert user is not None, 'signup should still create the account'
    assert user.role_ref.name == 'customer'
    assert user.is_admin is False and user.is_rider is False


def test_signup_allows_vendor(client, db_session):
    """H3 — vendor is a permitted self-service role (still admin-approved later)."""
    _seed_roles()
    client.post('/auth/signup', data={
        'name': 'Shop', 'email': 'v@test.com',
        'password': 'secret123', 'role': 'vendor',
    })
    user = User.query.filter_by(email='v@test.com').first()
    assert user is not None and user.role_ref.name == 'vendor'


# --- H2: unauthenticated password reset only for forced first-login ---------

def test_reset_blocked_for_established_account(client, db_session):
    """H2 — an anonymous caller cannot change an established account's password."""
    _make_user('est@test.com', 'oldpass1', must_change=False)
    resp = client.post('/api/force-update-password', json={
        'email': 'est@test.com',
        'current_password': 'oldpass1',
        'new_password': 'newpass1',
    })
    assert resp.status_code == 403
    user = User.query.filter_by(email='est@test.com').first()
    assert user.check_password('oldpass1'), 'password must be unchanged'


def test_reset_allowed_for_forced_first_login(client, db_session):
    """H2 — the legitimate forced first-login reset (must_change_password) works."""
    _make_user('new@test.com', 'otp12345', must_change=True)
    resp = client.post('/api/force-update-password', json={
        'email': 'new@test.com',
        'current_password': 'otp12345',
        'new_password': 'chosen123',
    })
    assert resp.status_code == 200
    user = User.query.filter_by(email='new@test.com').first()
    assert user.check_password('chosen123')
    assert user.must_change_password is False
