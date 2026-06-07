"""Auth routes for local backend (same contract as vendor dashboard /api/login)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from flask import jsonify, request

JWT_SECRET = os.getenv('JWT_SECRET_KEY') or os.getenv('SECRET_KEY', 'genspark-dev-session-key')
JWT_EXPIRES_HOURS = int(os.getenv('JWT_EXPIRES_HOURS', '168'))


def _parse_json() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(
            password.encode('utf-8'),
            password_hash.encode('utf-8'),
        )
    except ValueError:
        return False


def _create_jwt(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(user_id),
        'role': role,
        'iat': now,
        'exp': now + timedelta(hours=JWT_EXPIRES_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


def register_auth_routes(app, get_db_connection, json_error, json_ok):
    """Attach POST /api/login (and OPTIONS) to the Flask app."""

    @app.route('/api/login', methods=['POST', 'OPTIONS'])
    def api_login():
        if request.method == 'OPTIONS':
            return '', 204

        data = _parse_json()
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        if not email or not password:
            return json_error('Email and password required', 400)

        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT u.id, u.name, u.email, u.password_hash, u.status,
                       u.must_change_password, r.name AS role_name
                FROM users u
                LEFT JOIN roles r ON r.id = u.role_id
                WHERE LOWER(u.email) = %s
                LIMIT 1
                """,
                (email,),
            )
            user = cursor.fetchone()
            if not user or not _verify_password(password, user.get('password_hash') or ''):
                return jsonify({'success': False, 'error': 'Invalid email or password'}), 401

            status = (user.get('status') or 'active').lower()
            if status != 'active':
                msg = 'Account blocked'
                if status == 'pending_email':
                    msg = 'Please verify your email before logging in.'
                return jsonify({'success': False, 'error': msg}), 403

            role_name = user.get('role_name') or 'customer'
            token = _create_jwt(int(user['id']), role_name)

            return jsonify({
                'success': True,
                'message': 'Logged in',
                'token': token,
                'user': {
                    'id': int(user['id']),
                    'name': user.get('name') or '',
                    'email': user.get('email') or email,
                    'role': role_name,
                    'must_change_password': bool(user.get('must_change_password')),
                },
            }), 200
        except Exception as exc:
            app.logger.exception('api_login failed')
            return json_error(f'Login failed: {exc}', 500)
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
