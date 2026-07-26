"""Stripe checkout for GenSpark ERP (production Railway API)."""
from __future__ import annotations

import json
import os
from datetime import datetime
from decimal import Decimal

import stripe
from flask import current_app, jsonify, request
from flask_login import current_user

from app import db
from app.api import api_bp
from app.models import (
    Cart, CartItem, Component, Order, OrderItem, OrderStatusHistory,
    PendingCheckout, Payment, Transaction, VendorComponent, WebhookEvent,
)
from app.utils.rate_limit import hit as rate_limit_hit

GENERIC_ERROR = 'Something went wrong processing your payment. Please try again or contact support.'


def _stripe_configured() -> bool:
    key = (os.environ.get('STRIPE_SECRET_KEY') or '').strip()
    return bool(key) and key.startswith('sk_') and 'your_' not in key.lower()


def _stripe_currency() -> str:
    return (os.environ.get('STRIPE_CURRENCY') or 'pkr').strip().lower()


def _amount_minor(amount_major: float) -> int:
    return max(1, int(round(float(amount_major) * 100)))


def _next_order_number() -> str:
    return f'ORD-{datetime.utcnow().strftime("%Y%m%d%H%M%S%f")}'


def _price_cart_items(cart_items, lock=False):
    """Authoritative pricing + vendor-stock lookup for cart items.

    Every cart item is pinned to a specific vendor at add-to-cart time —
    validated and priced here against THAT vendor's real inventory
    (VendorComponent.quantity), the same pool COD checkout and cart-add both
    enforce. Raises ValueError on any invalid/insufficient-stock item. When
    lock=True, the vendor's stock row is locked (SELECT ... FOR UPDATE) for a
    caller about to decrement it; otherwise it's a plain read used only to
    size the Stripe charge.
    """
    items_total = 0.0
    resolved = {}
    item_names = []
    for item in cart_items:
        product_id = int(item['product_id'])
        qty = int(item['quantity'])
        vendor_id = item.get('vendor_id')
        if qty <= 0:
            raise ValueError(f'Invalid quantity for product {product_id}')
        component = Component.query.filter_by(id=product_id).first()
        if not component:
            raise ValueError(f'Component {product_id} not found')
        if not vendor_id:
            raise ValueError(f'No vendor assigned for {component.name}')
        vc_query = VendorComponent.query.filter_by(vendor_id=vendor_id, component_id=product_id)
        if lock:
            vc_query = vc_query.with_for_update()
        vendor_component = vc_query.first()
        if not vendor_component or int(vendor_component.quantity or 0) < qty:
            raise ValueError(f'Insufficient stock for {component.name}')
        unit = float(vendor_component.price) if vendor_component.price else float(component.price or 0)
        resolved[product_id] = {
            'unit_price': unit,
            'vendor_component': vendor_component,
            'component_name': component.name,
        }
        items_total += unit * qty
        item_names.append(component.name)
    return items_total, resolved, item_names


def _server_total(cart_items, shipping_fee, lock=False):
    from app.services.fees import assembly_fee_for
    items_total, resolved, item_names = _price_cart_items(cart_items, lock=lock)
    shipping_fee = max(0.0, float(shipping_fee or 0))
    assembly_fee = assembly_fee_for(item_names)
    total = round(items_total + shipping_fee + assembly_fee, 2)
    return total, resolved, shipping_fee


@api_bp.route('/create-payment-intent', methods=['POST', 'OPTIONS'])
def create_payment_intent():
    if request.method == 'OPTIONS':
        return '', 204
    if not current_user.is_authenticated:
        return jsonify({'error': 'Login required'}), 401
    if not _stripe_configured():
        return jsonify({'error': 'Stripe is not configured (STRIPE_SECRET_KEY)'}), 503

    # Best-effort in-process limiter: caps how many PaymentIntents one account
    # (and one IP, as a second layer) can mint per minute — the standard guard
    # against using this endpoint for Stripe card-testing/carding abuse.
    if not rate_limit_hit(f'create-pi:user:{current_user.id}', 10, 60):
        return jsonify({'error': 'Too many payment attempts. Please wait a moment and try again.'}), 429
    if not rate_limit_hit(f'create-pi:ip:{request.remote_addr}', 30, 60):
        return jsonify({'error': 'Too many payment attempts. Please wait a moment and try again.'}), 429

    data = request.get_json(silent=True) or {}
    cart_items = data.get('items') or []
    if not cart_items:
        return jsonify({'error': 'Cart is empty'}), 400
    shipping_address = (data.get('shipping_address') or '').strip() or 'Pakistan'
    try:
        shipping_fee = float(data.get('shipping_fee') or 0)
    except (TypeError, ValueError):
        shipping_fee = 0.0

    try:
        # Unlocked pricing pass, just to size the charge — the authoritative,
        # stock-locking pass happens at finalize time (webhook or complete-checkout).
        server_total, _resolved, shipping_fee = _server_total(
            cart_items, shipping_fee, lock=False,
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    try:
        stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')
        intent = stripe.PaymentIntent.create(
            amount=_amount_minor(server_total),
            currency=_stripe_currency(),
            automatic_payment_methods={'enabled': True},
            metadata={'user_id': str(current_user.id)},
        )

        pending = PendingCheckout(
            payment_intent_id=intent['id'],
            user_id=current_user.id,
            items_json=json.dumps(cart_items),
            shipping_address=shipping_address,
            shipping_fee=Decimal(str(round(shipping_fee, 2))),
            total_amount=Decimal(str(server_total)),
            status='created',
        )
        db.session.add(pending)
        db.session.commit()
    except stripe.error.StripeError as exc:
        current_app.logger.warning('Stripe PaymentIntent creation failed: %s', exc)
        return jsonify({'error': 'Could not start payment. Please try again.'}), 502
    except Exception:
        db.session.rollback()
        current_app.logger.exception('create_payment_intent failed')
        return jsonify({'error': GENERIC_ERROR}), 500

    return jsonify({'clientSecret': intent['client_secret']}), 200


def _create_order_from_pending(pending: PendingCheckout, charged_minor: int):
    """Authoritative order creation: locks stock rows, recomputes the total
    from the DB, verifies the captured amount covers it, then writes the
    Order/OrderItem/Payment rows. Shared by the client-driven completion call
    and the payment_intent.succeeded webhook so both paths behave identically
    and neither can create a second order for the same PaymentIntent."""
    cart_items = json.loads(pending.items_json)
    server_total, resolved, shipping_fee = _server_total(
        cart_items, float(pending.shipping_fee or 0), lock=True,
    )
    if charged_minor + 1 < _amount_minor(server_total):
        raise ValueError('Paid amount does not match the order total')

    order = Order(
        user_id=pending.user_id,
        order_number=_next_order_number(),
        total_amount=Decimal(str(server_total)),
        shipping_fee=Decimal(str(round(shipping_fee, 2))),
        status='pending',
        shipping_address=pending.shipping_address or 'Pakistan',
        notes=f'payment_method=stripe;stripe_pi={pending.payment_intent_id}',
    )
    if hasattr(Order, 'payment_status'):
        order.payment_status = 'Paid'
    if hasattr(Order, 'stripe_txn_id'):
        order.stripe_txn_id = pending.payment_intent_id

    db.session.add(order)
    db.session.flush()

    for item in cart_items:
        product_id = int(item['product_id'])
        qty = int(item['quantity'])
        info = resolved[product_id]
        unit_price = Decimal(str(info['unit_price']))
        vendor_component = info['vendor_component']
        vendor_component.quantity = int(vendor_component.quantity or 0) - qty
        db.session.add(OrderItem(
            order_id=order.id,
            item_type='component',
            item_id=product_id,
            component_name=info['component_name'],
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
        transaction_id=pending.payment_intent_id,
    ))

    cart = Cart.query.filter_by(user_id=pending.user_id).first()
    if cart:
        CartItem.query.filter_by(cart_id=cart.id).delete()

    pending.status = 'finalized'
    pending.order_id = order.id

    db.session.commit()

    try:
        from app.services.notification_service import notify_order_placed, notify_admin_new_order
        notify_order_placed(order)
        notify_admin_new_order(order)
    except Exception:
        current_app.logger.warning('notify order-placed (stripe) skipped', exc_info=True)

    return order


@api_bp.route('/order/complete-checkout', methods=['POST', 'OPTIONS'])
def complete_checkout():
    if request.method == 'OPTIONS':
        return '', 204
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Login required'}), 401
    if not _stripe_configured():
        return jsonify({'success': False, 'message': 'Stripe is not configured'}), 503

    data = request.get_json(silent=True) or {}
    payment_intent_id = (data.get('payment_intent_id') or '').strip()
    if not payment_intent_id:
        return jsonify({'success': False, 'message': 'payment_intent_id required'}), 400

    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')
    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
    except stripe.error.StripeError:
        current_app.logger.warning('complete_checkout: PaymentIntent retrieve failed', exc_info=True)
        return jsonify({'success': False, 'message': 'Could not verify payment. Please try again.'}), 502

    intent_status = getattr(intent, 'status', None)
    if intent_status != 'succeeded':
        return jsonify({
            'success': False,
            'message': f'Payment not completed (status={intent_status})',
        }), 400

    # Idempotent: a repeat call (retry, double-click, or a race with the
    # webhook) for an already-recorded PaymentIntent just returns that order.
    existing = Order.query.filter_by(stripe_txn_id=payment_intent_id).first()
    if existing:
        return jsonify({
            'success': True,
            'message': 'Order already recorded',
            'order_id': existing.id,
            'order_number': existing.order_number,
        }), 200

    pending = PendingCheckout.query.filter_by(payment_intent_id=payment_intent_id).first()
    if not pending or pending.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'No matching checkout session for this payment.'}), 404

    try:
        charged_minor = int(getattr(intent, 'amount_received', None) or getattr(intent, 'amount', None) or 0)
        order = _create_order_from_pending(pending, charged_minor)
        return jsonify({
            'success': True,
            'message': 'Transaction complete!',
            'order_id': order.id,
            'order_number': order.order_number,
        }), 200
    except Exception as exc:
        db.session.rollback()
        # A duplicate-key race with the webhook finalizing the same intent
        # concurrently is not a real failure — the order exists either way.
        existing = Order.query.filter_by(stripe_txn_id=payment_intent_id).first()
        if existing:
            return jsonify({
                'success': True,
                'message': 'Order already recorded',
                'order_id': existing.id,
                'order_number': existing.order_number,
            }), 200
        current_app.logger.warning('complete_checkout failed: %s', exc, exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Transaction failed, safely rolled back. Contact support with your payment receipt.',
        }), 500


@api_bp.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """Server-authoritative sync of Stripe payment state — independent of any
    client ever calling back. This is what actually makes the checkout
    durable: a customer whose browser dies right after Stripe confirms the
    charge still gets their order created here."""
    if not _stripe_configured():
        return jsonify({'error': 'Stripe is not configured'}), 503
    webhook_secret = (os.environ.get('STRIPE_WEBHOOK_SECRET') or '').strip()
    if not webhook_secret:
        current_app.logger.error('STRIPE_WEBHOOK_SECRET is not set; refusing unverifiable webhook')
        return jsonify({'error': 'Webhook not configured'}), 503

    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        current_app.logger.warning('Stripe webhook signature verification failed')
        return jsonify({'error': 'Invalid signature'}), 400

    event_id = event['id']
    event_type = event['type']

    # Idempotency: Stripe redelivers on any non-2xx / timeout, so the same
    # event id can arrive more than once. Record it before doing any writes;
    # the unique index on event_id turns a race between two deliveries into a
    # harmless IntegrityError on the loser.
    if WebhookEvent.query.filter_by(event_id=event_id).first():
        return jsonify({'received': True, 'duplicate': True}), 200

    try:
        obj = event['data']['object']

        if event_type == 'payment_intent.succeeded':
            payment_intent_id = obj['id']
            if not Order.query.filter_by(stripe_txn_id=payment_intent_id).first():
                pending = PendingCheckout.query.filter_by(payment_intent_id=payment_intent_id).first()
                if pending and pending.status != 'finalized':
                    charged_minor = int(obj.get('amount_received') or obj.get('amount') or 0)
                    _create_order_from_pending(pending, charged_minor)
                elif not pending:
                    current_app.logger.warning(
                        'payment_intent.succeeded for unknown intent %s (no PendingCheckout row)',
                        payment_intent_id,
                    )

        elif event_type in ('payment_intent.failed', 'payment_intent.payment_failed'):
            payment_intent_id = obj['id']
            pending = PendingCheckout.query.filter_by(payment_intent_id=payment_intent_id).first()
            if pending and pending.status == 'created':
                pending.status = 'failed'
                db.session.commit()

        elif event_type == 'charge.refunded':
            payment_intent_id = obj.get('payment_intent')
            order = Order.query.filter_by(stripe_txn_id=payment_intent_id).first() if payment_intent_id else None
            if order:
                payment = Payment.query.filter_by(order_id=order.id, payment_method='stripe').order_by(Payment.id.desc()).first()
                if payment:
                    payment.payment_status = 'refunded'
                if hasattr(order, 'payment_status'):
                    order.payment_status = 'Refunded'
                refunded_amount = Decimal(str((obj.get('amount_refunded') or 0) / 100.0))
                db.session.add(Transaction(
                    payment_id=payment.id if payment else None,
                    amount=refunded_amount,
                    type='refund',
                ))
                db.session.add(OrderStatusHistory(
                    order_id=order.id,
                    status=order.status,
                    notes=f'Stripe refund processed: {refunded_amount} recorded via webhook',
                ))
                db.session.commit()
            else:
                current_app.logger.warning('charge.refunded for unknown payment_intent %s', payment_intent_id)

        elif event_type == 'charge.dispute.created':
            payment_intent_id = obj.get('payment_intent')
            order = Order.query.filter_by(stripe_txn_id=payment_intent_id).first() if payment_intent_id else None
            if order:
                db.session.add(OrderStatusHistory(
                    order_id=order.id,
                    status=order.status,
                    notes='Stripe dispute opened on this payment — admin review required.',
                ))
                db.session.commit()
            current_app.logger.warning(
                'Stripe dispute created for payment_intent %s (order_id=%s)',
                payment_intent_id, order.id if order else None,
            )

        db.session.add(WebhookEvent(event_id=event_id, event_type=event_type))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Stripe webhook handling failed for event %s (%s)', event_id, event_type)
        # Non-2xx tells Stripe to retry delivery; we have not recorded the
        # event id, so the retry will reattempt the same handling.
        return jsonify({'error': 'Webhook handling failed'}), 500

    return jsonify({'received': True}), 200
