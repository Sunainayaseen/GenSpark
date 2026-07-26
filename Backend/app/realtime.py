"""
Socket.IO real-time layer — rooms + emit helpers.

Room scheme:
  user:<id>   one private room per logged-in user (customer / rider / admin)
  role:admin  shared room for all admins (dashboard live alerts)

Clients authenticate by passing {token} in the socket.io-client `auth` option
at connect time. Room membership is resolved server-side from that JWT —
never trusted from client-supplied user_id/role — so one user can't join
another user's room or the shared admin room. Emit from anywhere via
emit_to_user() / emit_to_role().
"""
from flask import request
from flask_socketio import join_room

from app import socketio


def user_room(user_id):
    return f'user:{user_id}'


def role_room(role):
    return f'role:{role}'


@socketio.on('connect')
def _on_connect(auth=None):
    from app.utils.jwt_session_bridge import user_from_bearer_token_string

    token = (auth or {}).get('token') if isinstance(auth, dict) else None
    user = user_from_bearer_token_string(token) if token else None
    if not user:
        return False  # reject the connection — no valid/verifiable token

    join_room(user_room(user.id))
    role_name = user.role_ref.name if user.role_ref else None
    if role_name:
        join_room(role_room(role_name.lower()))
    socketio.emit('connected', {'sid': request.sid}, to=request.sid)


# ---------------------------------------------------------------------------
# Server-side emit helpers (used by the notification engine)
# ---------------------------------------------------------------------------
def emit_to_user(user_id, payload, event='notification'):
    if user_id is None:
        return
    socketio.emit(event, payload, to=user_room(user_id))


def emit_to_role(role, payload, event='notification'):
    if not role:
        return
    socketio.emit(event, payload, to=role_room(role))
