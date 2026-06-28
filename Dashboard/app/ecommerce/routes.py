# JSON API — eCommerce shop (Cart → Admin approval → Checkout → Order)
from flask import Blueprint, jsonify, request
from flask_login import current_user

from app import db
from app.models.ecommerce import EcomCart, EcomOrder, EcomOrderItem, EcomProduct
from app.ecommerce.controllers import cart_service, order_service

ecom_bp = Blueprint('ecom', __name__)


def _json_error(msg, code=400):
    return jsonify({'success': False, 'error': msg}), code


def _require_user():
    if not current_user.is_authenticated:
        return None, _json_error('Login required', 401)
    return current_user, None


def _require_admin():
    u, err = _require_user()
    if err:
        return None, err
    if not u.is_admin:  # is_admin is a @property, not a method
        return None, _json_error('Admin access required', 403)
    return u, None


# ---------- products + seed ----------

@ecom_bp.route('/products', methods=['GET'])
def list_products():
    if EcomProduct.query.count() == 0:
        for name, price, stock in [
            ('Starter Widget', 19.99, 100),
            ('Pro Kit', 49.50, 50),
            ('Bundle Pack', 99.00, 25),
        ]:
            db.session.add(
                EcomProduct(name=name, sku=None, price=price, stock=stock, is_active=True)
            )
        db.session.commit()
    rows = EcomProduct.query.filter_by(is_active=True).order_by(EcomProduct.id.asc()).all()
    return jsonify({
        'success': True,
        'products': [
            {
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'price': float(p.price or 0),
                'stock': p.stock,
                'sku': p.sku,
            }
            for p in rows
        ],
    })


# ---------- user cart ----------

@ecom_bp.route('/cart', methods=['GET'])
def get_cart():
    u, err = _require_user()
    if err:
        return err
    cart = cart_service.get_or_create_user_cart(u.id)
    return jsonify({'success': True, 'cart': order_service.cart_to_dict(cart)})


@ecom_bp.route('/cart/items', methods=['POST'])
def add_cart_item():
    u, err = _require_user()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    product_id = int(body.get('product_id') or 0)
    quantity = int(body.get('quantity', 1))
    try:
        cart = cart_service.get_or_create_user_cart(u.id)
        cart = cart_service.add_or_update_item(cart, product_id, quantity)
        return jsonify({'success': True, 'cart': order_service.cart_to_dict(cart)})
    except ValueError as e:
        return _json_error(str(e))


@ecom_bp.route('/cart/items/<int:item_id>', methods=['DELETE'])
def delete_cart_item(item_id):
    u, err = _require_user()
    if err:
        return err
    try:
        cart = cart_service.get_or_create_user_cart(u.id)
        cart = cart_service.remove_item(cart, item_id)
        return jsonify({'success': True, 'cart': order_service.cart_to_dict(cart)})
    except ValueError as e:
        return _json_error(str(e))


@ecom_bp.route('/cart/<int:cart_id>/send-for-approval', methods=['PUT'])
def send_for_approval(cart_id):
    u, err = _require_user()
    if err:
        return err
    cart = EcomCart.query.get(cart_id)
    if not cart or cart.user_id != u.id:
        return _json_error('Cart not found', 404)
    try:
        cart = cart_service.send_for_approval(cart)
        return jsonify({'success': True, 'cart': order_service.cart_to_dict(cart)})
    except ValueError as e:
        return _json_error(str(e))


@ecom_bp.route('/cart/<int:cart_id>/reset', methods=['POST'])
def reset_rejected(cart_id):
    """After admin rejects, let user clear and shop again."""
    u, err = _require_user()
    if err:
        return err
    cart = EcomCart.query.get(cart_id)
    if not cart or cart.user_id != u.id:
        return _json_error('Cart not found', 404)
    try:
        cart = cart_service.reset_rejected_cart(cart)
        return jsonify({'success': True, 'cart': order_service.cart_to_dict(cart)})
    except ValueError as e:
        return _json_error(str(e))


# ---------- checkout / orders (user) ----------

@ecom_bp.route('/orders', methods=['POST'])
def create_order():
    u, err = _require_user()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    cart = cart_service.get_or_create_user_cart(u.id)
    try:
        order = order_service.place_order_from_cart(
            u.id,
            cart,
            body.get('payment_method') or 'cod',
            body.get('name') or '',
            body.get('phone') or '',
            body.get('address') or '',
            body.get('city') or '',
        )
        return jsonify(
            {
                'success': True,
                'order': order_service.order_to_dict(order),
            }
        ), 201
    except ValueError as e:
        return _json_error(str(e))


@ecom_bp.route('/my-orders', methods=['GET'])
def my_orders():
    u, err = _require_user()
    if err:
        return err
    q = EcomOrder.query.filter_by(user_id=u.id).order_by(EcomOrder.id.desc())
    return jsonify({
        'success': True,
        'orders': [order_service.order_to_dict(o) for o in q.all()],
    })


@ecom_bp.route('/orders/<int:order_id>', methods=['GET'])
def get_user_order(order_id):
    u, err = _require_user()
    if err:
        return err
    o = EcomOrder.query.get_or_404(order_id)
    if o.user_id != u.id:
        if not getattr(u, 'is_admin', False):  # is_admin is a @property, not a method
            return _json_error('Access denied', 403)
    return jsonify({'success': True, 'order': order_service.order_to_dict(o)})


# ---------- admin: carts ----------

@ecom_bp.route('/admin/carts', methods=['GET'])
def admin_carts_list():
    _, err = _require_admin()
    if err:
        return err
    status = (request.args.get('status') or 'pending_approval').strip()
    if status not in ('pending_approval', 'active', 'approved', 'rejected', 'all'):
        status = 'pending_approval'
    q = EcomCart.query
    if status != 'all':
        q = q.filter_by(status=status)
    carts = q.order_by(EcomCart.id.desc()).limit(200).all()
    out = []
    for c in carts:
        d = order_service.cart_to_dict(c)
        d['user_email'] = c.user.email if c.user else None
        d['user_name'] = c.user.name if c.user else None
        out.append(d)
    return jsonify({'success': True, 'carts': out, 'count': len(out)})


@ecom_bp.route('/admin/carts/<int:cart_id>/approve', methods=['POST'])
def admin_approve_cart(cart_id):
    _, err = _require_admin()
    if err:
        return err
    cart = EcomCart.query.get_or_404(cart_id)
    try:
        cart = cart_service.admin_set_cart_status(cart, 'approved')
        return jsonify({'success': True, 'cart': order_service.cart_to_dict(cart)})
    except ValueError as e:
        return _json_error(str(e))


@ecom_bp.route('/admin/carts/<int:cart_id>/reject', methods=['POST'])
def admin_reject_cart(cart_id):
    _, err = _require_admin()
    if err:
        return err
    cart = EcomCart.query.get_or_404(cart_id)
    try:
        cart = cart_service.admin_set_cart_status(cart, 'rejected')
        return jsonify({'success': True, 'cart': order_service.cart_to_dict(cart)})
    except ValueError as e:
        return _json_error(str(e))


# ---------- admin: orders ----------

@ecom_bp.route('/admin/orders', methods=['GET'])
def admin_orders_list():
    _, err = _require_admin()
    if err:
        return err
    rows = EcomOrder.query.order_by(EcomOrder.id.desc()).limit(200).all()
    return jsonify(
        {
            'success': True,
            'orders': [order_service.order_to_dict(o) for o in rows],
        }
    )


@ecom_bp.route('/admin/orders/<int:order_id>/status', methods=['PATCH', 'PUT'])
def admin_update_order_status(order_id):
    _, err = _require_admin()
    if err:
        return err
    order = EcomOrder.query.get_or_404(order_id)
    body = request.get_json(silent=True) or {}
    new_s = (body.get('status') or '').strip().lower()
    if not new_s:
        return _json_error('status is required', 400)
    try:
        o = order_service.update_order_status(order, new_s)
        return jsonify({'success': True, 'order': order_service.order_to_dict(o)})
    except ValueError as e:
        return _json_error(str(e))
