"""Inventory reservation/restoration lifecycle across /api/orders/place,
/api/orders/<id>/admin-approve, /api/orders/<id>/admin-reject, and
/api/vendor/orders/<id>/status — closes the TOCTOU stock race (stock is now
reserved at placement, not only checked-then-decremented-later-at-approval)
and the permanent-stock-leak bug (rejection now gives stock back).

Run from the backend/ folder:  python -m pytest
"""
from app import db
from app.models import (
    Component, ComponentCategory, Vendor, VendorComponent, User, Role,
    Cart, CartItem, Order, VendorOrder,
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


def _vendor(shop_name, approval_status='approved'):
    user = User(name=shop_name, email=f'{shop_name.lower().replace(" ", "")}@vendor.test',
                role_id=_role('vendor').id, status='active')
    user.set_password('vendor123')
    db.session.add(user)
    db.session.flush()
    vendor = Vendor(user_id=user.id, shop_name=shop_name, approval_status=approval_status)
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


def _admin(email='admin@test.com', password='admin12345'):
    user = User(name='Admin', email=email, role_id=_role('admin').id, status='active')
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, email, password):
    resp = client.post('/auth/login', data={'email': email, 'password': password})
    assert resp.status_code in (200, 302), resp.data


def _place_single_item_order(client, vendor, component, qty=1):
    user = _customer()
    cart = Cart(user_id=user.id)
    db.session.add(cart)
    db.session.flush()
    db.session.add(CartItem(cart_id=cart.id, item_type='component', component_id=component.id,
                             component_name=component.name, vendor_id=vendor.id,
                             unit_price=float(component.price), quantity=qty))
    db.session.commit()
    _login(client, user.email, 'secret123')
    resp = client.post('/api/orders/place', json={'shipping_address': 'Test St'})
    return resp


def test_stock_is_reserved_at_placement_not_at_approval(client, db_session):
    """The whole point of the fix: quantity drops the moment the order is
    placed, not only later when an admin approves it."""
    cat = _cat('Processor', 'cpu')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cat, 80_000)
    vendor = _vendor('Vendor A')
    vc = _stock(vendor, cpu, 80_000, qty=5)

    resp = _place_single_item_order(client, vendor, cpu, qty=2)
    assert resp.status_code == 201, resp.get_json()

    db.session.refresh(vc)
    assert vc.quantity == 3  # 5 - 2, decremented immediately at placement


def test_concurrent_placements_cannot_both_succeed_for_last_units(client, db_session):
    """Two different customers order the same last unit — the second must be
    rejected with INSUFFICIENT_STOCK once the first has reserved it, instead
    of both passing a check-only read and colliding later at approval."""
    cat = _cat('Processor', 'cpu')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cat, 80_000)
    vendor = _vendor('Vendor A')
    _stock(vendor, cpu, 80_000, qty=1)

    user1 = _customer(email='cust1@test.com')
    cart1 = Cart(user_id=user1.id)
    db.session.add(cart1)
    db.session.flush()
    db.session.add(CartItem(cart_id=cart1.id, item_type='component', component_id=cpu.id,
                             component_name=cpu.name, vendor_id=vendor.id,
                             unit_price=float(cpu.price), quantity=1))
    db.session.commit()

    user2 = _customer(email='cust2@test.com')
    cart2 = Cart(user_id=user2.id)
    db.session.add(cart2)
    db.session.flush()
    db.session.add(CartItem(cart_id=cart2.id, item_type='component', component_id=cpu.id,
                             component_name=cpu.name, vendor_id=vendor.id,
                             unit_price=float(cpu.price), quantity=1))
    db.session.commit()

    _login(client, 'cust1@test.com', 'secret123')
    resp1 = client.post('/api/orders/place', json={'shipping_address': 'Test St'})
    assert resp1.status_code == 201, resp1.get_json()

    client.get('/auth/logout')
    _login(client, 'cust2@test.com', 'secret123')
    resp2 = client.post('/api/orders/place', json={'shipping_address': 'Test St'})
    assert resp2.status_code == 409
    assert resp2.get_json()['code'] == 'INSUFFICIENT_STOCK'


def test_admin_reject_restores_stock(client, db_session):
    """Admin rejecting a pending order (before any vendor split) must give
    the reserved stock back — previously this leaked it permanently."""
    cat = _cat('Processor', 'cpu')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cat, 80_000)
    vendor = _vendor('Vendor A')
    vc = _stock(vendor, cpu, 80_000, qty=5)

    resp = _place_single_item_order(client, vendor, cpu, qty=2)
    order_id = resp.get_json()['order']['id']
    db.session.refresh(vc)
    assert vc.quantity == 3

    client.get('/auth/logout')
    _admin()
    _login(client, 'admin@test.com', 'admin12345')
    reject_resp = client.post(f'/api/orders/{order_id}/admin-reject', json={'reason': 'test'})
    assert reject_resp.status_code == 200, reject_resp.get_json()

    db.session.refresh(vc)
    assert vc.quantity == 5  # fully restored


def test_admin_approve_does_not_double_decrement_stock(client, db_session):
    """Approval creates the vendor order but must not touch VendorComponent
    again — the units were already reserved at placement."""
    cat = _cat('Processor', 'cpu')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cat, 80_000)
    vendor = _vendor('Vendor A')
    vc = _stock(vendor, cpu, 80_000, qty=5)

    resp = _place_single_item_order(client, vendor, cpu, qty=2)
    order_id = resp.get_json()['order']['id']
    db.session.refresh(vc)
    assert vc.quantity == 3

    client.get('/auth/logout')
    _admin()
    _login(client, 'admin@test.com', 'admin12345')
    approve_resp = client.post(f'/api/orders/{order_id}/admin-approve')
    assert approve_resp.status_code == 200, approve_resp.get_json()

    db.session.refresh(vc)
    assert vc.quantity == 3  # unchanged by approval — still just the placement reservation


def test_vendor_rejection_after_approval_restores_stock(client, db_session):
    """A vendor rejecting an order after admin-approve must give the reserved
    stock back — previously this was a permanent leak."""
    cat = _cat('Processor', 'cpu')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cat, 80_000)
    vendor = _vendor('Vendor A')
    vc = _stock(vendor, cpu, 80_000, qty=5)

    resp = _place_single_item_order(client, vendor, cpu, qty=2)
    order_id = resp.get_json()['order']['id']

    client.get('/auth/logout')
    _admin()
    _login(client, 'admin@test.com', 'admin12345')
    approve_resp = client.post(f'/api/orders/{order_id}/admin-approve')
    assert approve_resp.status_code == 200, approve_resp.get_json()
    vendor_order_id = approve_resp.get_json()['vendor_orders'][0]['vendor_order_id']

    db.session.refresh(vc)
    assert vc.quantity == 3

    client.get('/auth/logout')
    _login(client, _vendor_email(vendor), 'vendor123')
    reject_resp = client.post(
        f'/api/vendor/orders/{vendor_order_id}/status',
        json={'status': 'rejected', 'rejection_reason': 'out of stock in shop'},
    )
    assert reject_resp.status_code == 200, reject_resp.get_json()

    db.session.refresh(vc)
    assert vc.quantity == 5  # fully restored


def _vendor_email(vendor):
    return User.query.get(vendor.user_id).email
