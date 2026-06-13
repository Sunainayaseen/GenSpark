"""Order placement and admin status updates for eCommerce API."""
import random
import string
from datetime import datetime
from decimal import Decimal
from app import db
from app.models.ecommerce import EcomCart, EcomOrder, EcomOrderItem, ORDER_STATUSES


def _next_order_number() -> str:
    suffix = ''.join(random.choices(string.digits, k=6))
    return f'ECM-{datetime.utcnow().strftime("%Y%m%d")}-{suffix}'


def place_order_from_cart(
    user_id: int,
    cart: EcomCart,
    payment_method: str,
    name: str,
    phone: str,
    address: str,
    city: str,
) -> EcomOrder:
    if cart.user_id != user_id:
        raise ValueError('Cart does not belong to this user')
    if cart.status != 'approved':
        raise ValueError('Cart must be approved by admin before checkout')
    if not cart.items.count():
        raise ValueError('Cart is empty')
    name = (name or '').strip()
    phone = (phone or '').strip()
    address = (address or '').strip()
    city = (city or '').strip()
    if not all([name, phone, address, city]):
        raise ValueError('Name, phone, address, and city are required')

    total = Decimal('0')
    for line in cart.items.all():
        total += Decimal(str(line.price or 0)) * int(line.quantity or 0)

    order = EcomOrder(
        user_id=user_id,
        order_number=_next_order_number(),
        total_amount=total,
        payment_method=(payment_method or 'cod').strip().lower()[:32],
        status='pending',
        name=name,
        phone=phone,
        address=address,
        city=city,
    )
    db.session.add(order)
    db.session.flush()
    for line in cart.items.all():
        db.session.add(
            EcomOrderItem(
                order_id=order.id,
                product_id=line.product_id,
                quantity=line.quantity,
                price=line.price,
            )
        )
    # Remove cart; next GET /cart creates a new empty active cart
    db.session.delete(cart)
    db.session.commit()
    return EcomOrder.query.get(order.id)


def update_order_status(order: EcomOrder, new_status: str) -> EcomOrder:
    s = (new_status or '').strip().lower()
    if s not in ORDER_STATUSES:
        raise ValueError('Invalid order status')
    order.status = s
    db.session.add(order)
    db.session.commit()
    return order


def cart_to_dict(cart: EcomCart) -> dict:
    lines = []
    for it in cart.items.all():
        p = it.product
        lines.append(
            {
                'id': it.id,
                'product_id': it.product_id,
                'name': p.name if p else '—',
                'quantity': it.quantity,
                'unit_price': float(it.price or 0),
                'line_total': float((Decimal(str(it.price or 0)) * it.quantity).quantize(Decimal('0.01'))),
            }
        )
    return {
        'id': cart.id,
        'user_id': cart.user_id,
        'status': cart.status,
        'status_label': _cart_status_label(cart.status),
        'total_amount': float(cart.total_amount or 0),
        'items': lines,
        'can_edit': cart.status == 'active',
        'can_checkout': cart.status == 'approved' and bool(lines),
    }


def _cart_status_label(s: str) -> str:
    m = {
        'active': 'active',
        'pending_approval': 'Waiting for admin approval',
        'approved': 'Approved — you can checkout',
        'rejected': 'Rejected by admin',
    }
    return m.get(s, s or '—')


def order_to_dict(order: EcomOrder) -> dict:
    d = {
        'id': order.id,
        'order_number': order.order_number,
        'user_id': order.user_id,
        'total_amount': float(order.total_amount or 0),
        'payment_method': order.payment_method,
        'status': order.status,
        'name': order.name,
        'phone': order.phone,
        'address': order.address,
        'city': order.city,
        'created_at': order.created_at.isoformat() if order.created_at else None,
        'items': [],
    }
    for it in order.items.all():
        p = it.product
        d['items'].append(
            {
                'id': it.id,
                'product_id': it.product_id,
                'name': p.name if p else '—',
                'quantity': it.quantity,
                'unit_price': float(it.price or 0),
                'line_total': float((Decimal(str(it.price or 0)) * it.quantity).quantize(Decimal('0.01'))),
            }
        )
    return d
