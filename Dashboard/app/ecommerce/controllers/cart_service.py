"""Cart business logic for eCommerce API."""
from decimal import Decimal
from app import db
from app.models.ecommerce import EcomCart, EcomCartItem, EcomProduct, CART_STATUSES


def _recalc_total(cart: EcomCart) -> None:
    total = Decimal('0')
    for line in cart.items:
        total += Decimal(str(line.price or 0)) * int(line.quantity or 0)
    cart.total_amount = total
    db.session.add(cart)


def get_or_create_user_cart(user_id: int) -> EcomCart:
    """Return the user's current working cart (one open cart per user)."""
    cart = (
        EcomCart.query.filter_by(user_id=user_id)
        .filter(EcomCart.status.in_(list(CART_STATUSES)))
        .order_by(EcomCart.id.desc())
        .first()
    )
    if cart is None:
        cart = EcomCart(user_id=user_id, status='active', total_amount=0)
        db.session.add(cart)
        db.session.commit()
    return cart


def add_or_update_item(cart: EcomCart, product_id: int, quantity: int) -> EcomCart:
    if cart.status != 'active':
        raise ValueError('Cart can only be edited while status is active')
    if quantity <= 0:
        raise ValueError('Quantity must be positive')
    product = EcomProduct.query.get(product_id)
    if not product or not product.is_active:
        raise ValueError('Product not found')
    if product.stock is not None and product.stock >= 0 and quantity > product.stock:
        raise ValueError('Not enough stock')
    line = EcomCartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
    unit = Decimal(str(product.price or 0))
    if line:
        line.quantity = quantity
        line.price = unit
    else:
        line = EcomCartItem(cart_id=cart.id, product_id=product_id, quantity=quantity, price=unit)
        db.session.add(line)
    _recalc_total(cart)
    db.session.commit()
    return cart


def remove_item(cart: EcomCart, item_id: int) -> EcomCart:
    if cart.status != 'active':
        raise ValueError('Cart can only be edited while status is active')
    line = EcomCartItem.query.filter_by(id=item_id, cart_id=cart.id).first()
    if not line:
        raise ValueError('Item not in cart')
    db.session.delete(line)
    _recalc_total(cart)
    db.session.commit()
    return cart


def send_for_approval(cart: EcomCart) -> EcomCart:
    if cart.status != 'active':
        raise ValueError('Can only send an active cart for approval')
    if cart.items.count() == 0:
        raise ValueError('Cart is empty')
    cart.status = 'pending_approval'
    db.session.add(cart)
    db.session.commit()
    return cart


def admin_set_cart_status(cart: EcomCart, new_status: str) -> EcomCart:
    if new_status not in ('approved', 'rejected'):
        raise ValueError('Invalid admin action')
    if cart.status != 'pending_approval':
        raise ValueError('Cart is not pending approval')
    cart.status = new_status
    db.session.add(cart)
    db.session.commit()
    return cart


def reset_rejected_cart(cart: EcomCart) -> EcomCart:
    if cart.status != 'rejected':
        raise ValueError('Only a rejected cart can be reset this way')
    for line in cart.items.all():
        db.session.delete(line)
    cart.status = 'active'
    cart.total_amount = 0
    db.session.add(cart)
    db.session.commit()
    return cart


def delete_cart(cart: EcomCart) -> None:
    db.session.delete(cart)
    db.session.commit()
