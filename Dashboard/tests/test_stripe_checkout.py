"""Coverage for the Stripe webhook — the durable, server-authoritative half of
checkout (app/api/stripe_checkout.py). complete_checkout() shares the same
_create_order_from_pending() path exercised here via the webhook, so these
tests cover both callers of the highest-value, previously-untested code path
in the payment flow.

Run from the Dashboard/ folder:  python -m pytest
"""
import json

import stripe

from app import db
from app.models import (
    Component, ComponentCategory, Vendor, VendorComponent, User, Role,
    Order, PendingCheckout, WebhookEvent,
)


def _cat(name, slug):
    c = ComponentCategory(name=name, slug=slug)
    db.session.add(c)
    db.session.flush()
    return c


def _comp(name, category, price, stock=10):
    c = Component(name=name, category_id=category.id, price=price, stock=stock)
    db.session.add(c)
    db.session.flush()
    return c


def _role(name):
    role = Role.query.filter_by(name=name).first()
    if not role:
        role = Role(name=name)
        db.session.add(role)
        db.session.flush()
    return role


def _vendor(shop_name='Vendor A'):
    user = User(name=shop_name, email=f'{shop_name.lower().replace(" ", "")}@vendor.test',
                role_id=_role('vendor').id, status='active')
    user.set_password('vendor123')
    db.session.add(user)
    db.session.flush()
    vendor = Vendor(user_id=user.id, shop_name=shop_name, approval_status='approved')
    db.session.add(vendor)
    db.session.flush()
    return vendor


def _stock(vendor, component, price, qty=10):
    vc = VendorComponent(vendor_id=vendor.id, component_id=component.id, quantity=qty, price=price)
    db.session.add(vc)
    db.session.flush()
    return vc


def _customer(email='cust@test.com', password='secret123'):
    user = User(name='Cust', email=email, role_id=_role('customer').id, status='active')
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _pending_checkout(user, vendor, component, qty=2, payment_intent_id='pi_test_123'):
    items = [{'product_id': component.id, 'quantity': qty, 'vendor_id': vendor.id}]
    pc = PendingCheckout(
        payment_intent_id=payment_intent_id,
        user_id=user.id,
        items_json=json.dumps(items),
        shipping_address='Test St',
        shipping_fee=0,
        total_amount=0,
        status='created',
    )
    db.session.add(pc)
    db.session.commit()
    return pc


def _configure_stripe(monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_dummy')
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec_dummy')


def _fake_event(event_id, event_type, obj):
    return {'id': event_id, 'type': event_type, 'data': {'object': obj}}


def test_webhook_503_when_stripe_not_configured(client, db_session):
    resp = client.post('/api/webhooks/stripe', data=b'{}', headers={'Stripe-Signature': 't=1,v1=x'})
    assert resp.status_code == 503


def test_webhook_503_when_webhook_secret_missing(client, db_session, monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_dummy')
    resp = client.post('/api/webhooks/stripe', data=b'{}', headers={'Stripe-Signature': 't=1,v1=x'})
    assert resp.status_code == 503


def test_webhook_rejects_invalid_signature(client, db_session, monkeypatch):
    _configure_stripe(monkeypatch)

    def _raise(*a, **kw):
        raise stripe.error.SignatureVerificationError('bad signature', sig_header='t=1,v1=x')

    monkeypatch.setattr(stripe.Webhook, 'construct_event', _raise)
    resp = client.post('/api/webhooks/stripe', data=b'{}', headers={'Stripe-Signature': 't=1,v1=x'})
    assert resp.status_code == 400


def test_webhook_payment_intent_succeeded_creates_order_and_decrements_stock(client, db_session, monkeypatch):
    _configure_stripe(monkeypatch)

    cat = _cat('Processor', 'cpu')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cat, 80_000)
    vendor = _vendor()
    vc = _stock(vendor, cpu, 80_000, qty=5)
    user = _customer()
    _pending_checkout(user, vendor, cpu, qty=2, payment_intent_id='pi_test_success')

    event = _fake_event(
        'evt_1', 'payment_intent.succeeded',
        {'id': 'pi_test_success', 'amount_received': 160_000 * 100},
    )
    monkeypatch.setattr(stripe.Webhook, 'construct_event', lambda *a, **kw: event)

    resp = client.post('/api/webhooks/stripe', data=b'{}', headers={'Stripe-Signature': 't=1,v1=x'})
    assert resp.status_code == 200, resp.get_json()

    order = Order.query.filter_by(stripe_txn_id='pi_test_success').first()
    assert order is not None
    assert order.status == 'pending'

    db.session.refresh(vc)
    assert vc.quantity == 3  # 5 - 2, reserved by the webhook-driven order creation

    assert WebhookEvent.query.filter_by(event_id='evt_1').first() is not None


def test_webhook_duplicate_event_id_is_idempotent(client, db_session, monkeypatch):
    _configure_stripe(monkeypatch)

    cat = _cat('Processor', 'cpu')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cat, 80_000)
    vendor = _vendor()
    vc = _stock(vendor, cpu, 80_000, qty=5)
    user = _customer()
    _pending_checkout(user, vendor, cpu, qty=2, payment_intent_id='pi_test_dup')

    event = _fake_event(
        'evt_dup', 'payment_intent.succeeded',
        {'id': 'pi_test_dup', 'amount_received': 160_000 * 100},
    )
    monkeypatch.setattr(stripe.Webhook, 'construct_event', lambda *a, **kw: event)

    first = client.post('/api/webhooks/stripe', data=b'{}', headers={'Stripe-Signature': 't=1,v1=x'})
    assert first.status_code == 200
    assert first.get_json().get('duplicate') is not True

    second = client.post('/api/webhooks/stripe', data=b'{}', headers={'Stripe-Signature': 't=1,v1=x'})
    assert second.status_code == 200
    assert second.get_json()['duplicate'] is True

    # Stripe redelivering the same event must not create a second order or
    # decrement stock twice.
    assert Order.query.filter_by(stripe_txn_id='pi_test_dup').count() == 1
    db.session.refresh(vc)
    assert vc.quantity == 3


def test_webhook_payment_failed_marks_pending_checkout_failed(client, db_session, monkeypatch):
    _configure_stripe(monkeypatch)

    cat = _cat('Processor', 'cpu')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cat, 80_000)
    vendor = _vendor()
    _stock(vendor, cpu, 80_000, qty=5)
    user = _customer()
    pending = _pending_checkout(user, vendor, cpu, qty=2, payment_intent_id='pi_test_failed')

    event = _fake_event('evt_failed', 'payment_intent.payment_failed', {'id': 'pi_test_failed'})
    monkeypatch.setattr(stripe.Webhook, 'construct_event', lambda *a, **kw: event)

    resp = client.post('/api/webhooks/stripe', data=b'{}', headers={'Stripe-Signature': 't=1,v1=x'})
    assert resp.status_code == 200

    db.session.refresh(pending)
    assert pending.status == 'failed'
    assert Order.query.filter_by(stripe_txn_id='pi_test_failed').first() is None
