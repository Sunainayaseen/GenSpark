# Order Management
from datetime import datetime
from app import db

ORDER_STATUSES = [
    'pending', 'approved', 'processing', 'completed', 'rejected',
    # After vendor completion + admin proof approval — vendor may dispatch.
    'ready_to_dispatch',
    # Backward-compatible legacy statuses used by older dashboard modules.
    'accepted', 'assembly', 'qa', 'shipped', 'delivered', 'admin-review',
]
VENDOR_ORDER_STATUSES = ['assigned', 'accepted', 'assembling', 'completed', 'rejected']


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    order_number = db.Column(db.String(50), unique=True)
    total_amount = db.Column(db.Numeric(12, 2), default=0)
    # Flat shipping charged at checkout (same rule as React Checkout: PKR 2000 when cart has items).
    shipping_fee = db.Column(db.Numeric(12, 2), default=0)
    status = db.Column(db.String(30), default='pending')
    shipping_address = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')
    status_history = db.relationship('OrderStatusHistory', backref='order', lazy='dynamic')
    payments = db.relationship('Payment', backref='order', lazy='dynamic')
    shipments = db.relationship('Shipment', backref='order', lazy='dynamic')
    assembly_trackings = db.relationship('AssemblyTracking', backref='order', lazy='dynamic')
    qa_checks = db.relationship('QaCheck', backref='order', lazy='dynamic')
    vendor_orders = db.relationship('VendorOrder', backref='order', lazy='dynamic', cascade='all, delete-orphan')


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    item_type = db.Column(db.String(30))  # pc_build, custom_build, component
    item_id = db.Column(db.Integer)  # pc_build_id or custom_build_id or component_id
    component_name = db.Column(db.String(150))
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True, index=True)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Numeric(12, 2))
    total_price = db.Column(db.Numeric(12, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class OrderStatusHistory(db.Model):
    __tablename__ = 'order_status_history'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    status = db.Column(db.String(30))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class VendorOrder(db.Model):
    __tablename__ = 'vendor_orders'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, index=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False, index=True)
    status = db.Column(db.String(30), default='assigned')
    total_amount = db.Column(db.Numeric(12, 2), default=0)
    proof_image_url = db.Column(db.String(255))
    # When vendor uploads a completion proof, admin must approve before master order can finish.
    # Default True = no proof pending (backward compatible).
    proof_approved = db.Column(db.Boolean, default=True, nullable=False)
    rejection_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    items = db.relationship('VendorOrderItem', backref='vendor_order', lazy='dynamic', cascade='all, delete-orphan')


class VendorOrderItem(db.Model):
    __tablename__ = 'vendor_order_items'

    id = db.Column(db.Integer, primary_key=True)
    vendor_order_id = db.Column(db.Integer, db.ForeignKey('vendor_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    component_id = db.Column(db.Integer, db.ForeignKey('components.id'), nullable=False, index=True)
    component_name = db.Column(db.String(150))
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(12, 2), default=0)
    total_price = db.Column(db.Numeric(12, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def sync_master_order_status_from_vendor_orders(order_id):
    """
    Update master Order.status from VendorOrder rows.
    Master stays 'processing' while any vendor line has an uploaded proof pending admin approval.
    """
    parent = Order.query.get(order_id)
    if not parent:
        return
    vos = VendorOrder.query.filter_by(order_id=parent.id).all()
    if not vos:
        return
    statuses = [v.status for v in vos]
    if not all(s == 'completed' for s in statuses):
        if any(s in ('accepted', 'assembling', 'completed') for s in statuses):
            parent.status = 'processing'
        return
    pending_proof = any(
        bool(v.proof_image_url) and not bool(v.proof_approved)
        for v in vos
    )
    if pending_proof:
        parent.status = 'processing'
    else:
        # All vendor lines done and proofs OK (or no proof required) → ready for vendor shipment / dispatch
        parent.status = 'ready_to_dispatch'
