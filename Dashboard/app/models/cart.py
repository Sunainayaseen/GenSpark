from datetime import datetime

from app import db


class Cart(db.Model):
    __tablename__ = 'cart'

    id = db.Column(db.Integer, primary_key=True)
    # user_id nullable so guest carts are supported via session (cart_id stored in session).
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship(
        'CartItem',
        backref='cart',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )


class CartItem(db.Model):
    __tablename__ = 'cart_items'

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('cart.id', ondelete='CASCADE'), nullable=False, index=True)
    # Backward compatibility: old field that pointed to pc_builds.id.
    product_id = db.Column(db.Integer, db.ForeignKey('pc_builds.id', ondelete='CASCADE'), nullable=True, index=True)
    # New multi-vendor cart fields.
    item_type = db.Column(db.String(30), nullable=False, default='component')  # component | pc_build_component
    pc_build_id = db.Column(db.Integer, db.ForeignKey('pc_builds.id', ondelete='SET NULL'), nullable=True, index=True)
    component_id = db.Column(db.Integer, db.ForeignKey('components.id', ondelete='CASCADE'), nullable=True, index=True)
    component_name = db.Column(db.String(150))
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True, index=True)
    unit_price = db.Column(db.Numeric(12, 2), default=0)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('cart_id', 'component_id', 'vendor_id', name='uq_cart_component_vendor'),
    )

