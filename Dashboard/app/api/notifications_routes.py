"""
In-app notifications API (drives the React toast/bell).

  GET  /api/notifications            current user's recent notifications + unread count
  POST /api/notifications/<id>/read  mark one read
  POST /api/notifications/read-all   mark all read

Unauthenticated callers get an empty list (keeps the UI poller quiet for guests).
"""
from flask import jsonify, request
from flask_login import current_user

from app import db
from app.api import api_bp
from app.models import Notification


def _serialize(n):
    return {
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'type': n.type,
        'related_id': n.related_id,
        'is_read': bool(n.is_read),
        'created_at': n.created_at.isoformat() if n.created_at else None,
    }


@api_bp.route('/notifications', methods=['GET'])
def list_notifications():
    if not current_user.is_authenticated:
        return jsonify({'success': True, 'notifications': [], 'unread': 0, 'count': 0}), 200

    limit = request.args.get('limit', type=int) or 20
    rows = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({
        'success': True,
        'count': len(rows),
        'unread': unread,
        'notifications': [_serialize(n) for n in rows],
    }), 200


@api_bp.route('/notifications/<int:notif_id>/read', methods=['POST', 'OPTIONS'])
def mark_notification_read(notif_id):
    if request.method == 'OPTIONS':
        return '', 204
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    n = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first()
    if not n:
        return jsonify({'success': False, 'error': 'Notification not found'}), 404
    n.is_read = True
    db.session.commit()
    return jsonify({'success': True}), 200


@api_bp.route('/notifications/read-all', methods=['POST', 'OPTIONS'])
def mark_all_read():
    if request.method == 'OPTIONS':
        return '', 204
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True}), 200
