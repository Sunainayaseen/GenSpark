"""
GenSpark Notification Engine — provider-agnostic (WhatsApp / SMS / in-app).

Mock mode (default) "sends" by:
  1. appending a structured line to  logs/notifications.log
  2. creating an in-app Notification row (shown as a toast in the React UI)

Switching to a real provider later = ONE change: set NOTIFICATION_PROVIDER in
.env (mock | twilio | meta) and fill that provider's credentials. No call-site
changes — every trigger goes through notify()/notify_order_status()/etc.

Trigger points wired into the backend:
  * Admin marks an order  -> 'ready_to_dispatch'  (customer notified)
  * Rider marks delivery  -> 'delivered'          (customer + admin notified)
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIG — change the active provider here (or via the NOTIFICATION_PROVIDER env)
# ---------------------------------------------------------------------------
ACTIVE_PROVIDER = (os.getenv('NOTIFICATION_PROVIDER') or 'mock').strip().lower()

FRONTEND_URL = (os.getenv('FRONTEND_URL') or 'http://localhost:5173').rstrip('/')

LOG_DIR = Path(__file__).resolve().parents[2] / 'logs'   # Dashboard/logs
LOG_FILE = LOG_DIR / 'notifications.log'


# ---------------------------------------------------------------------------
# Message templates (one place to localise / reword)
# ---------------------------------------------------------------------------
TEMPLATES = {
    # --- High-priority customer events (also sent via WhatsApp) ---
    'order_success': {
        'title': 'Order placed',
        'type': 'order_update',
        'whatsapp': ('🧾 GenSpark: Order {order_code} confirmed! {items_count} item(s), '
                     'total PKR {total}. Track your build live: {track_url}'),
    },
    'out_for_delivery': {
        'title': 'Out for delivery',
        'type': 'order_update',
        'whatsapp': ('🛵 GenSpark: Your order {order_code} is OUT FOR DELIVERY! '
                     'Rider {rider_name} ({rider_phone}) is on the way. Track live: {track_url}'),
    },
    'delivery_delivered': {
        'title': 'Order delivered',
        'type': 'order_update',
        'whatsapp': ('✅ GenSpark: Your order {order_code} has been delivered. '
                     'We hope you love your build! Share your feedback: {feedback_url}'),
    },

    # --- Lower-priority events (on-site / in-app + Socket.io ONLY, no WhatsApp) ---
    'order_ready_to_dispatch': {
        'title': 'Order ready for dispatch',
        'type': 'order_update',
        'whatsapp': ('🚚 GenSpark: Your order {order_code} is packed and ready for '
                     'dispatch. A rider will pick it up shortly. Track it live: {track_url}'),
    },
    'rider_assigned': {
        'title': 'Rider assigned',
        'type': 'order_update',
        'whatsapp': ('🛵 GenSpark: A rider has been assigned to your order {order_code} '
                     'and is heading to pickup.'),
    },
    'admin_order_delivered': {
        'title': 'Delivery completed',
        'type': 'admin_alert',
        'whatsapp': ('📦 Admin alert: Order {order_code} was delivered by {rider_code}.'),
    },
}

# Balanced Flow: WhatsApp is reserved for these high-priority, customer-facing
# moments. Every OTHER event still flows to the on-site channels (in-app row +
# Socket.io toast) so an active user is never spammed on WhatsApp.
WHATSAPP_EVENTS = {'order_success', 'out_for_delivery', 'delivery_delivered'}


# ---------------------------------------------------------------------------
# Providers — all share send(); only the transport differs.
# ---------------------------------------------------------------------------
class BaseProvider:
    name = 'base'

    def send(self, to, message, *, channel='whatsapp', meta=None):  # pragma: no cover
        raise NotImplementedError


class MockProvider:
    """Simulates sending by logging — no external account required."""
    name = 'mock'

    def send(self, to, message, *, channel='whatsapp', meta=None):
        _append_log({
            'ts': datetime.utcnow().isoformat(),
            'provider': self.name,
            'channel': channel,
            'to': to or '(no phone on file)',
            'message': message,
            'meta': meta or {},
        })
        return {'success': True, 'provider': self.name, 'sid': f'mock-{int(datetime.utcnow().timestamp()*1000)}'}


class TwilioProvider(BaseProvider):
    """Stub — fill TWILIO_* in .env and `pip install twilio` to enable later."""
    name = 'twilio'

    def send(self, to, message, *, channel='whatsapp', meta=None):
        sid = os.getenv('TWILIO_ACCOUNT_SID')
        token = os.getenv('TWILIO_AUTH_TOKEN')
        from_no = os.getenv('TWILIO_WHATSAPP_FROM')
        if not (sid and token and from_no and to):
            return {'success': False, 'provider': self.name, 'error': 'Twilio not configured'}
        # from twilio.rest import Client
        # Client(sid, token).messages.create(from_=f'whatsapp:{from_no}', to=f'whatsapp:{to}', body=message)
        return {'success': False, 'provider': self.name, 'error': 'Twilio send not implemented yet'}


class MetaWhatsAppProvider(BaseProvider):
    """Stub — fill WHATSAPP_* in .env to enable Meta Cloud API later."""
    name = 'meta'

    def send(self, to, message, *, channel='whatsapp', meta=None):
        token = os.getenv('WHATSAPP_API_KEY')
        phone_id = os.getenv('WHATSAPP_PHONE_ID')
        if not (token and phone_id and to):
            return {'success': False, 'provider': self.name, 'error': 'Meta WhatsApp not configured'}
        # POST https://graph.facebook.com/v19.0/{phone_id}/messages
        return {'success': False, 'provider': self.name, 'error': 'Meta send not implemented yet'}


_PROVIDERS = {
    'mock': MockProvider,
    'twilio': TwilioProvider,
    'meta': MetaWhatsAppProvider,
}


def get_provider():
    return _PROVIDERS.get(ACTIVE_PROVIDER, MockProvider)()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _append_log(entry: dict):
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception as exc:  # logging must never break a request
        print('notification log write failed:', exc)


def _save_in_app(user_id, title, message, ntype, related_id):
    """Persist an in-app Notification row (drives the React toast/bell). Returns its id."""
    if not user_id:
        return None
    try:
        from app import db
        from app.models import Notification
        row = Notification(
            user_id=user_id, title=title, message=message,
            type=ntype, related_id=related_id,
        )
        db.session.add(row)
        db.session.commit()
        return row.id
    except Exception as exc:
        try:
            from app import db
            db.session.rollback()
        except Exception:
            pass
        print('in-app notification save failed:', exc)
        return None


def _emit_realtime(user_id, payload):
    """Push the notification to the user's Socket.IO room (no-op if unavailable)."""
    try:
        from app.realtime import emit_to_user
        emit_to_user(user_id, payload)
    except Exception as exc:
        print('realtime emit skipped:', exc)


def _customer_phone(order):
    """Best-effort phone for the customer (User has none; shipping text may)."""
    if not order:
        return None
    import re
    blob = order.shipping_address or ''
    m = re.search(r'(\+?\d[\d\s\-]{8,14}\d)', blob)
    return m.group(1).strip() if m else None


def notify(event, *, user_id=None, phone=None, related_id=None, context=None, channel='whatsapp'):
    """
    Core entry point. Renders the template, sends via the active provider,
    logs, and stores an in-app notification. Never raises.
    """
    tpl = TEMPLATES.get(event)
    if not tpl:
        return {'success': False, 'error': f'Unknown event: {event}'}
    ctx = dict(context or {})
    try:
        message = tpl[channel].format(**ctx)
    except Exception:
        message = tpl.get('whatsapp', '').format_map(_Safe(ctx))
    title = tpl['title']
    ntype = tpl.get('type', 'order_update')

    # Balanced Flow gate: only high-priority events leave the building (WhatsApp).
    # Everything else stays on-site (in-app + Socket.io) so users aren't spammed.
    result = {'success': True, 'provider': 'on-site'}
    if channel == 'whatsapp' and event in WHATSAPP_EVENTS:
        if phone:
            try:
                result = get_provider().send(phone, message, channel=channel,
                                             meta={'event': event, **ctx})
            except Exception as exc:
                _append_log({'ts': datetime.utcnow().isoformat(), 'event': event,
                             'error': str(exc), 'message': message})
        else:
            _append_log({'ts': datetime.utcnow().isoformat(), 'event': event,
                         'channel': channel, 'to': '(no phone on file)',
                         'note': 'whatsapp skipped — no customer phone', 'message': message})

    # Channel: in-app persistence (drives bell/history)
    nid = _save_in_app(user_id, title, message, ntype, related_id)

    # Channel: real-time push (Socket.IO) → instant toast on the client
    _emit_realtime(user_id, {
        'id': nid,
        'title': title,
        'message': message,
        'type': ntype,
        'related_id': related_id,
        'created_at': datetime.utcnow().isoformat(),
    })

    return {'success': True, 'event': event, 'provider': result.get('provider', ACTIVE_PROVIDER),
            'delivered': bool(result.get('success')), 'message': message}


class _Safe(dict):
    def __missing__(self, key):
        return '{' + key + '}'


# ---------------------------------------------------------------------------
# Convenience triggers used by the backend
# ---------------------------------------------------------------------------
def _track_url(order_id):
    return f'{FRONTEND_URL}/track/{order_id}' if order_id else f'{FRONTEND_URL}/my-orders'


def _feedback_url(order_id):
    return f'{FRONTEND_URL}/track/{order_id}' if order_id else f'{FRONTEND_URL}/my-orders'


def _items_count(order):
    try:
        return order.items.count()
    except Exception:
        return len(order.items or [])


def notify_order_placed(order):
    """High-priority: order confirmed → WhatsApp summary + on-site toast."""
    if not order:
        return None
    ctx = {
        'order_code': order.order_number or f'#{order.id}',
        'items_count': _items_count(order),
        'total': f'{float(order.total_amount or 0):,.0f}',
        'track_url': _track_url(order.id),
    }
    return notify('order_success', user_id=order.user_id, phone=_customer_phone(order),
                  related_id=order.id, context=ctx)


def notify_out_for_delivery(delivery):
    """High-priority: rider picked up & en route → WhatsApp with rider contact + tracking."""
    if not delivery:
        return None
    from app.models import Order, Rider

    order = Order.query.get(delivery.order_id) if delivery.order_id else None
    rider = Rider.query.get(delivery.rider_id)
    order_code = (order.order_number if order else None) or delivery.order_code or f'D{delivery.id}'
    rider_name = (rider.user.name if rider and rider.user else 'Your rider')
    rider_phone = (rider.phone if rider and rider.phone else 'N/A')
    ctx = {
        'order_code': order_code,
        'rider_name': rider_name,
        'rider_phone': rider_phone,
        'track_url': _track_url(order.id if order else delivery.id),
    }
    return notify('out_for_delivery',
                  user_id=(order.user_id if order else None),
                  phone=(_customer_phone(order) if order else None),
                  related_id=(order.id if order else delivery.id), context=ctx)


def notify_order_ready_to_dispatch(order):
    if not order:
        return None
    ctx = {'order_code': order.order_number or f'#{order.id}', 'track_url': _track_url(order.id)}
    return notify('order_ready_to_dispatch', user_id=order.user_id, phone=_customer_phone(order),
                  related_id=order.id, context=ctx)


# Friendly per-status messages for the generic status-change notification.
_STATUS_NOTIFY = {
    'approved':          ('Order approved', '✅ Your order {code} has been approved and sent to our vendor(s) for assembly.'),
    'processing':        ('Order processing', '🔧 Your order {code} is now being processed by the vendor.'),
    'assembly':          ('Build in assembly', '🛠️ Your PC for order {code} is being assembled.'),
    'qa':                ('Quality check', '🔎 Your order {code} is going through our quality checks.'),
    'ready_to_dispatch': ('Ready for dispatch', '🚚 Your order {code} is packed and ready — a rider will pick it up shortly.'),
    'shipped':           ('Order dispatched', '📦 Your order {code} has been dispatched and is on its way.'),
    'rejected':          ('Order not approved', '⚠️ Your order {code} could not be approved. Please contact support for help.'),
    'completed':         ('Order completed', '🎉 Your order {code} is complete. Thank you for choosing GenSpark!'),
    'delivered':         ('Order delivered', '✅ Your order {code} has been delivered. We hope you love your build!'),
}


def notify_order_status(order, status=None):
    """On-site (in-app bell + Socket.IO toast) notification for ANY order status
    change, so the customer always sees live progress. WhatsApp stays reserved
    for the high-priority Balanced-Flow events (placed / out-for-delivery / delivered)."""
    if not order:
        return None
    status = (status or order.status or '').lower()
    tpl = _STATUS_NOTIFY.get(status)
    if not tpl:
        return None
    code = order.order_number or f'#{order.id}'
    title, message = tpl[0], tpl[1].format(code=code)
    nid = _save_in_app(order.user_id, title, message, 'order_update', order.id)
    _emit_realtime(order.user_id, {
        'id': nid, 'title': title, 'message': message,
        'type': 'order_update', 'related_id': order.id,
        'created_at': datetime.utcnow().isoformat(),
    })
    return {'success': True, 'status': status}


def notify_vendor_order_assigned(vendor_order):
    """On-site notification to the VENDOR's user when an order is assigned to them.

    The customer already gets 'approved'/'processing' updates; this is the missing
    vendor-facing trigger so the vendor learns a new order is waiting to be accepted.
    Resolves the vendor's login user via Vendor.user_id and drops an in-app row +
    Socket.IO toast (same channels as the customer status notifications)."""
    if not vendor_order:
        return None
    from app.models import Vendor, Order

    vendor = Vendor.query.get(vendor_order.vendor_id)
    if not vendor or not vendor.user_id:
        return None
    parent = Order.query.get(vendor_order.order_id) if vendor_order.order_id else None
    order_code = (parent.order_number if parent else None) or f'#{vendor_order.order_id}'
    try:
        items_count = vendor_order.items.count()
    except Exception:
        items_count = 0
    title = 'New order assigned'
    message = (f'📦 New order {order_code} has been assigned to you — {items_count} item(s), '
               f'PKR {float(vendor_order.total_amount or 0):,.0f}. Open Orders to accept and start assembly.')
    nid = _save_in_app(vendor.user_id, title, message, 'order_update', vendor_order.order_id)
    _emit_realtime(vendor.user_id, {
        'id': nid, 'title': title, 'message': message,
        'type': 'order_update', 'related_id': vendor_order.order_id,
        'created_at': datetime.utcnow().isoformat(),
    })
    return {'success': True, 'vendor_id': vendor.id, 'notification_id': nid}


def notify_admins(title, message, *, ntype='admin_alert', related_id=None):
    """Broadcast an on-site notification (in-app bell + Socket.IO toast) to EVERY
    admin user. Used for events that need admin action/awareness — new orders to
    approve, vendor completion proofs to verify, rider pickup requests, and new
    vendor registrations. Never raises."""
    try:
        from app.models import User, Role
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            return {'success': False, 'reason': 'no_admin_role'}
        sent = 0
        for admin in User.query.filter_by(role_id=admin_role.id).all():
            nid = _save_in_app(admin.id, title, message, ntype, related_id)
            _emit_realtime(admin.id, {
                'id': nid, 'title': title, 'message': message,
                'type': ntype, 'related_id': related_id,
                'created_at': datetime.utcnow().isoformat(),
            })
            sent += 1
        return {'success': True, 'admins_notified': sent}
    except Exception as exc:
        print('notify_admins skipped:', exc)
        return {'success': False, 'error': str(exc)}


def notify_admin_new_order(order):
    """A customer placed an order → admins must review & approve it."""
    if not order:
        return None
    code = order.order_number or f'#{order.id}'
    return notify_admins(
        'New order to approve',
        f'🧾 New order {code} placed — PKR {float(order.total_amount or 0):,.0f}. '
        f'Open Orders to review and approve.',
        related_id=order.id,
    )


def notify_admin_vendor_proof(vendor_order):
    """A vendor marked their order completed & uploaded a proof image → admins
    must verify the proof before the order can be dispatched."""
    if not vendor_order:
        return None
    from app.models import Vendor, Order
    vendor = Vendor.query.get(vendor_order.vendor_id)
    shop = vendor.shop_name if vendor else 'A vendor'
    parent = Order.query.get(vendor_order.order_id) if vendor_order.order_id else None
    code = (parent.order_number if parent else None) or f'#{vendor_order.order_id}'
    return notify_admins(
        'Completion proof to verify',
        f'📸 {shop} submitted a completion proof for order {code}. '
        f'Open the order to verify and release it for dispatch.',
        related_id=vendor_order.order_id,
    )


def notify_admin_rider_pickup_request(delivery):
    """A rider requested pickup → admins must approve it before transit."""
    if not delivery:
        return None
    from app.models import Rider
    rider = Rider.query.get(delivery.rider_id) if delivery.rider_id else None
    rider_code = (rider.display_code if rider else None) or f'RDR-{delivery.rider_id}'
    return notify_admins(
        'Rider pickup request',
        f'🛵 {rider_code} requested pickup for {delivery.order_code}. '
        f'Open Rider Approvals to approve.',
        related_id=delivery.order_id,
    )


def notify_admin_new_vendor(vendor):
    """A new vendor registered → admins must review & approve the account."""
    if not vendor:
        return None
    return notify_admins(
        'New vendor pending approval',
        f'🏪 New vendor "{vendor.shop_name}" registered and is awaiting approval. '
        f'Open Vendors to review.',
        related_id=vendor.id,
    )


def notify_delivery_delivered(delivery):
    """delivery: DeliveryAssignment. Notifies the customer + all admins."""
    if not delivery:
        return None
    from app.models import Order, User, Rider, Role

    order = Order.query.get(delivery.order_id) if delivery.order_id else None
    order_code = (order.order_number if order else None) or delivery.order_code or f'D{delivery.id}'

    # Customer
    if order:
        notify('delivery_delivered', user_id=order.user_id, phone=_customer_phone(order),
               related_id=order.id,
               context={'order_code': order_code, 'feedback_url': _feedback_url(order.id)})

    # Admins
    rider = Rider.query.get(delivery.rider_id)
    rider_code = rider.display_code if rider else f'RDR-{delivery.rider_id:04d}'
    admin_role = Role.query.filter_by(name='admin').first()
    if admin_role:
        for admin in User.query.filter_by(role_id=admin_role.id).all():
            notify('admin_order_delivered', user_id=admin.id,
                   related_id=order.id if order else delivery.id,
                   context={'order_code': order_code, 'rider_code': rider_code})
    return {'success': True}
