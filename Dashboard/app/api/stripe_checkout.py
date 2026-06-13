"""Stripe checkout for GenSpark ERP (production Railway API)."""
from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal

import stripe
from flask import jsonify, request
from flask_login import current_user

from app import db
from app.api import api_bp
from app.models import Cart, CartItem, Component, Order, OrderItem, OrderStatusHistory, Payment


def _stripe_configured() -> bool:
    key = (os.environ.get('STRIPE_SECRET_KEY') or '').strip()
    return bool(key) and key.startswith('sk_') and 'your_' not in key.lower()


def _stripe_currency() -> str:
    return (os.environ.get('STRIPE_CURRENCY') or 'pkr').strip().lower()


def _amount_minor(amount_major: float) -> int:
    return max(1, int(round(float(amount_major) * 100)))


def _next_order_number() -> str:
    return f'ORD-{datetime.utcnow().strftime("%Y%m%d%H%M%S%f")}'


@api_bp.route('/create-payment-intent', methods=['POST', 'OPTIONS'])
def create_payment_intent():
    if request.method == 'OPTIONS':
        return '', 204
    if not _stripe_configured():
        return jsonify({'error': 'Stripe is not configured (STRIPE_SECRET_KEY)'}), 503
    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get('amount') or 0)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid amount'}), 400
    if amount <= 0:
        return jsonify({'error': 'amount must be greater than zero'}), 400
    stripe.api_key = os.environ['STRIPE_SECRET_KEY']
    intent = stripe.PaymentIntent.create(
        amount=_amount_minor(amount),
        currency=_stripe_currency(),
        automatic_payment_methods={'enabled': True},
    )
    return jsonify({'clientSecret': intent['client_secret']}), 200


@api_bp.route('/order/complete-checkout', methods=['POST', 'OPTIONS'])
def complete_checkout():
    if request.method == 'OPTIONS':
        return '', 204
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Login required'}), 401
    if not _stripe_configured():
        return jsonify({'success': False, 'message': 'Stripe is not configured'}), 503

    data = request.get_json(silent=True) or {}
    cart_items = data.get('items') or []
    payment_intent_id = (data.get('payment_intent_id') or '').strip()
    try:
        total_amount = float(data.get('total_amount') or 0)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid total_amount'}), 400
    shipping_address = (data.get('shipping_address') or '').strip() or 'Pakistan'
    try:
        shipping_fee = float(data.get('shipping_fee') or 0)
    except (TypeError, ValueError):
        shipping_fee = 0.0

    if not payment_intent_id:
        return jsonify({'success': False, 'message': 'payment_intent_id required'}), 400
    if not cart_items:
        return jsonify({'success': False, 'message': 'Cart is empty'}), 400

    stripe.api_key = os.environ['STRIPE_SECRET_KEY']
    intent = stripe.PaymentIntent.retrieve(payment_intent_id)
    if intent.get('status') != 'succeeded':
        return jsonify({
            'success': False,
            'message': f'Payment not completed (status={intent.get("status")})',
        }), 400

    existing = Order.query.filter_by(stripe_txn_id=payment_intent_id).first()
    if existing:
        return jsonify({
            'success': True,
            'message': 'Order already recorded',
            'order_id': existing.id,
            'order_number': existing.order_number,
        }), 200

    try:
        server_items_total = 0.0
        price_by_id = {}
        for item in cart_items:
            product_id = int(item['product_id'])
            qty = int(item['quantity'])
            if qty <= 0:
                raise ValueError(f'Invalid quantity for product {product_id}')
            component = (
                Component.query.filter_by(id=product_id)
                .with_for_update()
                .first()
            )
            if not component:
                raise ValueError(f'Component {product_id} not found')
            if int(component.stock or 0) < qty:
                raise ValueError(f'Insufficient stock for {component.name}')
            unit = float(component.price or 0)
            price_by_id[product_id] = unit
            server_items_total += unit * qty

        # Server-authoritative total: never trust client-sent prices. The amount
        # Stripe actually captured must cover the total we compute from the DB,
        # otherwise a tampered client could pay less than the order is worth.
        shipping_fee = max(0.0, shipping_fee)
        server_total = round(server_items_total + shipping_fee, 2)
        charged_minor = int(intent.get('amount_received') or intent.get('amount') or 0)
        if charged_minor + 1 < _amount_minor(server_total):
            raise ValueError('Paid amount does not match the order total')

        order = Order(
            user_id=current_user.id,
            order_number=_next_order_number(),
            total_amount=Decimal(str(server_total)),
            shipping_fee=Decimal(str(round(shipping_fee, 2))),
            status='pending',
            shipping_address=shipping_address,
            notes=f'payment_method=stripe;stripe_pi={payment_intent_id}',
        )
        if hasattr(Order, 'payment_status'):
            order.payment_status = 'Paid'
        if hasattr(Order, 'stripe_txn_id'):
            order.stripe_txn_id = payment_intent_id

        db.session.add(order)
        db.session.flush()

        for item in cart_items:
            product_id = int(item['product_id'])
            qty = int(item['quantity'])
            unit_price = Decimal(str(price_by_id.get(product_id, 0)))
            component = Component.query.get(product_id)
            component.stock = int(component.stock or 0) - qty
            db.session.add(OrderItem(
                order_id=order.id,
                item_type='component',
                item_id=product_id,
                component_name=component.name,
                vendor_id=item.get('vendor_id'),
                quantity=qty,
                unit_price=unit_price,
                total_price=unit_price * qty,
            ))

        db.session.add(OrderStatusHistory(
            order_id=order.id,
            status='pending',
            notes='Stripe payment received — awaiting admin approval',
        ))
        db.session.add(Payment(
            order_id=order.id,
            amount=Decimal(str(server_total)),
            payment_status='completed',
            payment_method='stripe',
            transaction_id=payment_intent_id,
        ))

        cart = Cart.query.filter_by(user_id=current_user.id).first()
        if cart:
            CartItem.query.filter_by(cart_id=cart.id).delete()

        db.session.commit()

        # High-priority WhatsApp + on-site: paid order confirmed (Order Success).
        try:
            from app.services.notification_service import notify_order_placed
            notify_order_placed(order)
        except Exception as _e:
            print('notify order-placed (stripe) skipped:', _e)

        return jsonify({
            'success': True,
            'message': 'Transaction complete!',
            'order_id': order.id,
            'order_number': order.order_number,
        }), 200
    except Exception as exc:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Transaction failed, safely rolled back.',
            'error': str(exc),
        }), 500
