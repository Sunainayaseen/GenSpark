# Payment
from datetime import datetime
from app import db


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    payment_status = db.Column(db.String(30), default='pending')  # pending, completed, failed, refunded
    payment_method = db.Column(db.String(50))
    transaction_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)


class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'))
    amount = db.Column(db.Numeric(12, 2))
    type = db.Column(db.String(30))  # earning, refund
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WebhookEvent(db.Model):
    """Processed Stripe webhook event ids — prevents double-processing when
    Stripe retries a delivery (network blip, slow response, etc.)."""
    __tablename__ = 'webhook_events'
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(20), nullable=False, default='stripe')
    event_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    event_type = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
