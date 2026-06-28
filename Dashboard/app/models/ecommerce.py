# eCommerce (shop) — separate from legacy PC-component cart/orders
from datetime import datetime
from app import db

CART_STATUSES = ('active', 'pending_approval', 'approved', 'rejected')
ORDER_STATUSES = ('pending', 'processing', 'shipped', 'delivered', 'cancelled')


class EcomProduct(db.Model):
    __tablename__ = 'ecom_products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    sku = db.Column(db.String(80), unique=True, index=True, nullable=True)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    stock = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def price_f(self) -> float:
        return float(self.price or 0)


class EcomCart(db.Model):
    __tablename__ = 'ecom_carts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    status = db.Column(db.String(32), default='active', nullable=False)  # CART_STATUSES
    total_amount = db.Column(db.Numeric(12, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('ecom_carts', lazy='dynamic'))
    items = db.relationship('EcomCartItem', backref='cart', lazy='dynamic', cascade='all, delete-orphan')


class EcomCartItem(db.Model):
    __tablename__ = 'ecom_cart_items'
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('ecom_carts.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('ecom_products.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Numeric(12, 2), nullable=False)  # line snapshot
    product = db.relationship('EcomProduct')


class EcomOrder(db.Model):
    __tablename__ = 'ecom_orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    order_number = db.Column(db.String(32), unique=True, index=True)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    payment_method = db.Column(db.String(32), default='cod')
    status = db.Column(db.String(32), default='pending', nullable=False)  # ORDER_STATUSES
    # Shipping snapshot
    name = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    address = db.Column(db.Text)
    city = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('ecom_orders', lazy='dynamic'))
    items = db.relationship('EcomOrderItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')


class EcomOrderItem(db.Model):
    __tablename__ = 'ecom_order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('ecom_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('ecom_products.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    product = db.relationship('EcomProduct')
