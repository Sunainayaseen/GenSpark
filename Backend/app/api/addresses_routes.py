"""
Saved delivery addresses API (one User -> many Addresses).

  GET    /api/addresses           list current user's addresses
  POST   /api/addresses           create a new address
  PUT    /api/addresses/<id>      update an address
  DELETE /api/addresses/<id>      delete an address
  POST   /api/addresses/<id>/default   mark an address as the default

All routes require an authenticated user (Bearer JWT or session).
"""
from flask import jsonify, request
from flask_login import current_user

from app import db
from app.api import api_bp
from app.models import Address

_FIELDS = ('label', 'full_name', 'phone', 'line1', 'city', 'postal_code')


def _auth_guard():
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'error': 'Please sign in.'}), 401
    return None


def _clear_other_defaults(user_id, keep_id=None):
    q = Address.query.filter_by(user_id=user_id, is_default=True)
    if keep_id:
        q = q.filter(Address.id != keep_id)
    q.update({'is_default': False})


@api_bp.route('/addresses', methods=['GET'])
def list_addresses():
    if not current_user.is_authenticated:
        return jsonify({'success': True, 'addresses': []}), 200
    rows = (
        Address.query.filter_by(user_id=current_user.id)
        .order_by(Address.is_default.desc(), Address.id.desc())
        .all()
    )
    return jsonify({'success': True, 'addresses': [a.to_dict() for a in rows]}), 200


@api_bp.route('/addresses', methods=['POST', 'OPTIONS'])
def create_address():
    if request.method == 'OPTIONS':
        return ('', 204)
    guard = _auth_guard()
    if guard:
        return guard
    data = request.get_json(silent=True) or {}
    line1 = (data.get('line1') or '').strip()
    if not line1:
        return jsonify({'success': False, 'error': 'Address (line 1) is required.'}), 400

    make_default = bool(data.get('is_default')) or (
        Address.query.filter_by(user_id=current_user.id).count() == 0
    )
    if make_default:
        _clear_other_defaults(current_user.id)

    addr = Address(user_id=current_user.id, is_default=make_default)
    for f in _FIELDS:
        setattr(addr, f, (str(data.get(f)).strip() if data.get(f) is not None else None))
    addr.line1 = line1
    db.session.add(addr)
    db.session.commit()
    return jsonify({'success': True, 'address': addr.to_dict()}), 201


@api_bp.route('/addresses/<int:addr_id>', methods=['PUT', 'OPTIONS'])
def update_address(addr_id):
    if request.method == 'OPTIONS':
        return ('', 204)
    guard = _auth_guard()
    if guard:
        return guard
    addr = Address.query.filter_by(id=addr_id, user_id=current_user.id).first()
    if not addr:
        return jsonify({'success': False, 'error': 'Address not found.'}), 404
    data = request.get_json(silent=True) or {}
    for f in _FIELDS:
        if f in data:
            setattr(addr, f, (str(data.get(f)).strip() if data.get(f) is not None else None))
    if not (addr.line1 or '').strip():
        return jsonify({'success': False, 'error': 'Address (line 1) is required.'}), 400
    if bool(data.get('is_default')):
        _clear_other_defaults(current_user.id, keep_id=addr.id)
        addr.is_default = True
    db.session.commit()
    return jsonify({'success': True, 'address': addr.to_dict()}), 200


@api_bp.route('/addresses/<int:addr_id>', methods=['DELETE', 'OPTIONS'])
def delete_address(addr_id):
    if request.method == 'OPTIONS':
        return ('', 204)
    guard = _auth_guard()
    if guard:
        return guard
    addr = Address.query.filter_by(id=addr_id, user_id=current_user.id).first()
    if not addr:
        return jsonify({'success': False, 'error': 'Address not found.'}), 404
    was_default = addr.is_default
    db.session.delete(addr)
    db.session.commit()
    # Promote another address to default if we removed the default one.
    if was_default:
        nxt = Address.query.filter_by(user_id=current_user.id).order_by(Address.id.desc()).first()
        if nxt:
            nxt.is_default = True
            db.session.commit()
    return jsonify({'success': True}), 200


@api_bp.route('/addresses/<int:addr_id>/default', methods=['POST', 'OPTIONS'])
def set_default_address(addr_id):
    if request.method == 'OPTIONS':
        return ('', 204)
    guard = _auth_guard()
    if guard:
        return guard
    addr = Address.query.filter_by(id=addr_id, user_id=current_user.id).first()
    if not addr:
        return jsonify({'success': False, 'error': 'Address not found.'}), 404
    _clear_other_defaults(current_user.id, keep_id=addr.id)
    addr.is_default = True
    db.session.commit()
    return jsonify({'success': True, 'address': addr.to_dict()}), 200
