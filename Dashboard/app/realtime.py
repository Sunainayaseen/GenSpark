"""
Socket.IO real-time layer — rooms + emit helpers.

Room scheme:
  user:<id>   one private room per logged-in user (customer / rider / admin)
  role:admin  shared room for all admins (dashboard live alerts)

Clients call emit('join', {user_id, role}) right after connecting so each
notification reaches only the intended recipient. Emit from anywhere via
emit_to_user() / emit_to_role().
"""
from flask import request
from flask_socketio import join_room, leave_room

from app import socketio


def user_room(user_id):
    return f'user:{user_id}'


def role_room(role):
    return f'role:{role}'


@socketio.on('connect')
def _on_connect():
    # Connection is open; the client will 'join' its rooms next.
    socketio.emit('connected', {'sid': request.sid}, to=request.sid)


@socketio.on('join')
def _on_join(data):
    data = data or {}
    user_id = data.get('user_id')
    role = (data.get('role') or '').strip().lower()
    if user_id is not None:
        join_room(user_room(user_id))
    if role:
        join_room(role_room(role))
    socketio.emit('joined', {'user_id': user_id, 'role': role}, to=request.sid)


@socketio.on('leave')
def _on_leave(data):
    data = data or {}
    user_id = data.get('user_id')
    role = (data.get('role') or '').strip().lower()
    if user_id is not None:
        leave_room(user_room(user_id))
    if role:
        leave_room(role_room(role))


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
