"""Single-vendor-per-build rule — assembly is performed by the supplying vendor, so
a PC build (CPU/GPU/Motherboard/RAM/Storage/PSU/Case) can never be split across
vendors. Covers the new vendor_coverage service, /api/cart/add-build,
/api/orders/place defense-in-depth, /api/recommend-build, and
/api/evaluate-customization.

Run from the backend/ folder:  python -m pytest
"""
from app import db
from app.models import (
    Component, ComponentCategory, Vendor, VendorComponent, User, Role,
    Cart, CartItem, Order,
)
from app.services.vendor_coverage import (
    vendor_coverage_for_components, VENDOR_CONFLICT_MESSAGE,
)


# --- seeding helpers ---------------------------------------------------------

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
    db.session.add(VendorComponent(vendor_id=vendor.id, component_id=component.id,
                                    quantity=qty, price=price))


def _customer(email='cust@test.com', password='secret123'):
    user = User(name='Cust', email=email, role_id=_role('customer').id, status='active')
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, email, password):
    resp = client.post('/auth/login', data={'email': email, 'password': password})
    assert resp.status_code in (200, 302), resp.data


def _seed_am5_mini_catalog():
    """CPU + Motherboard + RAM, all AM5/DDR5-coherent (mirrors
    test_build_recommendation.py's seeding style, trimmed to what
    evaluate-customization needs)."""
    cpu_cat = _cat('Processor', 'cpu')
    mobo_cat = _cat('Motherboard', 'motherboard')
    ram_cat = _cat('RAM', 'ram')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cpu_cat, 80_000)
    mobo = _comp('ASUS B650 Motherboard', mobo_cat, 30_000)
    ram = _comp('Corsair 16GB DDR5 RAM', ram_cat, 12_000)
    return cpu, mobo, ram, ram_cat


# --- vendor_coverage_for_components ------------------------------------------

def test_coverage_full_picks_cheapest_full_vendor(db_session):
    cpu_cat = _cat('Processor', 'cpu')
    mobo_cat = _cat('Motherboard', 'motherboard')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cpu_cat, 80_000)
    mobo = _comp('ASUS B650 Motherboard', mobo_cat, 30_000)

    cheap = _vendor('Cheap Vendor')
    pricey = _vendor('Pricey Vendor')
    partial = _vendor('Partial Vendor')
    _stock(cheap, cpu, 80_000)
    _stock(cheap, mobo, 30_000)
    _stock(pricey, cpu, 95_000)
    _stock(pricey, mobo, 35_000)
    _stock(partial, cpu, 70_000)  # no motherboard stock — partial coverage only
    db.session.commit()

    cov = vendor_coverage_for_components({cpu.id: 1, mobo.id: 1})
    assert cov['covers_all'] is True
    assert cov['best']['id'] == cheap.id
    assert cov['missing_component_ids'] == []


def test_coverage_partial_reports_missing_components(db_session):
    cpu_cat = _cat('Processor', 'cpu')
    ram_cat = _cat('RAM', 'ram')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cpu_cat, 80_000)
    ram = _comp('Corsair 16GB DDR5 RAM', ram_cat, 12_000)

    only_cpu = _vendor('Only CPU Vendor')
    _stock(only_cpu, cpu, 80_000)
    db.session.commit()

    cov = vendor_coverage_for_components({cpu.id: 1, ram.id: 1})
    assert cov['covers_all'] is False
    assert cov['missing_component_ids'] == [ram.id]


# --- POST /api/cart/add-build ------------------------------------------------

def test_add_build_to_cart_pins_one_vendor(client, db_session):
    cpu_cat = _cat('Processor', 'cpu')
    mobo_cat = _cat('Motherboard', 'motherboard')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cpu_cat, 80_000)
    mobo = _comp('ASUS B650 Motherboard', mobo_cat, 30_000)
    vendor = _vendor('OneStop Vendor')
    _stock(vendor, cpu, 80_000)
    _stock(vendor, mobo, 30_000)
    db.session.commit()

    resp = client.post('/api/cart/add-build', json={'components': [
        {'component_id': cpu.id, 'quantity': 1},
        {'component_id': mobo.id, 'quantity': 1},
    ]})
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body['vendor']['id'] == vendor.id
    items = body['cart']['items']
    assert len(items) == 2
    assert {it['vendor_id'] for it in items} == {vendor.id}


def test_add_build_to_cart_rejects_no_covering_vendor(client, db_session):
    cpu_cat = _cat('Processor', 'cpu')
    mobo_cat = _cat('Motherboard', 'motherboard')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cpu_cat, 80_000)
    mobo = _comp('ASUS B650 Motherboard', mobo_cat, 30_000)
    vendor_a = _vendor('Vendor A')
    vendor_b = _vendor('Vendor B')
    _stock(vendor_a, cpu, 80_000)   # only stocks the CPU
    _stock(vendor_b, mobo, 30_000)  # only stocks the motherboard
    db.session.commit()

    resp = client.post('/api/cart/add-build', json={'components': [
        {'component_id': cpu.id, 'quantity': 1},
        {'component_id': mobo.id, 'quantity': 1},
    ]})
    assert resp.status_code == 409
    assert resp.get_json()['error'] == VENDOR_CONFLICT_MESSAGE

    cart_resp = client.get('/api/cart')
    assert cart_resp.get_json()['cart']['items'] == []


# --- POST /api/cart/build-coverage (read-only eligible-vendor picker) --------

def test_build_coverage_returns_only_full_coverage_vendors(client, db_session):
    cpu_cat = _cat('Processor', 'cpu')
    mobo_cat = _cat('Motherboard', 'motherboard')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cpu_cat, 80_000)
    mobo = _comp('ASUS B650 Motherboard', mobo_cat, 30_000)

    cheap = _vendor('Cheap Vendor')
    pricey = _vendor('Pricey Vendor')
    partial = _vendor('Partial Vendor')
    _stock(cheap, cpu, 80_000)
    _stock(cheap, mobo, 30_000)
    _stock(pricey, cpu, 95_000)
    _stock(pricey, mobo, 35_000)
    _stock(partial, cpu, 70_000)  # no motherboard stock — partial coverage only
    db.session.commit()

    resp = client.post('/api/cart/build-coverage', json={'components': [
        {'component_id': cpu.id, 'quantity': 1},
        {'component_id': mobo.id, 'quantity': 1},
    ]})
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body['covers_all'] is True
    vendor_ids = [v['id'] for v in body['vendors']]
    assert partial.id not in vendor_ids
    assert set(vendor_ids) == {cheap.id, pricey.id}
    # Sorted cheapest-first.
    assert vendor_ids[0] == cheap.id
    assert 'city' in body['vendors'][0] and 'phone' in body['vendors'][0]


def test_build_coverage_reports_missing_when_no_vendor_covers_all(client, db_session):
    cpu_cat = _cat('Processor', 'cpu')
    mobo_cat = _cat('Motherboard', 'motherboard')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cpu_cat, 80_000)
    mobo = _comp('ASUS B650 Motherboard', mobo_cat, 30_000)
    vendor_a = _vendor('Vendor A')
    vendor_b = _vendor('Vendor B')
    _stock(vendor_a, cpu, 80_000)
    _stock(vendor_b, mobo, 30_000)
    db.session.commit()

    resp = client.post('/api/cart/build-coverage', json={'components': [
        {'component_id': cpu.id, 'quantity': 1},
        {'component_id': mobo.id, 'quantity': 1},
    ]})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['covers_all'] is False
    assert body['vendors'] == []
    # Reports the gap vs. the closest partial vendor (each of vendor_a/vendor_b
    # covers exactly one part), not the union of every component in the build.
    assert set(body['missing_component_ids']).issubset({cpu.id, mobo.id})
    assert len(body['missing_component_ids']) == 1


# --- POST /api/cart/add-build with an explicit vendor_id ---------------------

def test_add_build_to_cart_honors_explicit_vendor_choice(client, db_session):
    cpu_cat = _cat('Processor', 'cpu')
    mobo_cat = _cat('Motherboard', 'motherboard')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cpu_cat, 80_000)
    mobo = _comp('ASUS B650 Motherboard', mobo_cat, 30_000)
    cheap = _vendor('Cheap Vendor')
    pricey = _vendor('Pricey Vendor')
    _stock(cheap, cpu, 80_000)
    _stock(cheap, mobo, 30_000)
    _stock(pricey, cpu, 95_000)
    _stock(pricey, mobo, 35_000)
    db.session.commit()

    # User explicitly picks the pricier (non-default) vendor — must be honored,
    # not silently overridden by the cheapest-vendor auto-pick.
    resp = client.post('/api/cart/add-build', json={
        'components': [
            {'component_id': cpu.id, 'quantity': 1},
            {'component_id': mobo.id, 'quantity': 1},
        ],
        'vendor_id': pricey.id,
    })
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body['vendor']['id'] == pricey.id
    items = body['cart']['items']
    assert {it['vendor_id'] for it in items} == {pricey.id}


def test_add_build_to_cart_rejects_vendor_without_full_coverage(client, db_session):
    cpu_cat = _cat('Processor', 'cpu')
    mobo_cat = _cat('Motherboard', 'motherboard')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cpu_cat, 80_000)
    mobo = _comp('ASUS B650 Motherboard', mobo_cat, 30_000)
    full = _vendor('Full Vendor')
    partial = _vendor('Partial Vendor')
    _stock(full, cpu, 80_000)
    _stock(full, mobo, 30_000)
    _stock(partial, cpu, 70_000)  # no motherboard stock
    db.session.commit()

    resp = client.post('/api/cart/add-build', json={
        'components': [
            {'component_id': cpu.id, 'quantity': 1},
            {'component_id': mobo.id, 'quantity': 1},
        ],
        'vendor_id': partial.id,
    })
    assert resp.status_code == 409
    assert resp.get_json()['code'] == 'VENDOR_CONFLICT'

    cart_resp = client.get('/api/cart')
    assert cart_resp.get_json()['cart']['items'] == []


# --- POST /api/orders/place defense-in-depth ---------------------------------

def test_place_order_rejects_mixed_vendor_build(client, db_session):
    cpu_cat = _cat('Processor', 'cpu')
    mobo_cat = _cat('Motherboard', 'motherboard')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cpu_cat, 80_000)
    mobo = _comp('ASUS B650 Motherboard', mobo_cat, 30_000)
    vendor_a = _vendor('Vendor A')
    vendor_b = _vendor('Vendor B')
    _stock(vendor_a, cpu, 80_000)
    _stock(vendor_b, mobo, 30_000)

    user = _customer()
    cart = Cart(user_id=user.id)
    db.session.add(cart)
    db.session.flush()
    db.session.add(CartItem(cart_id=cart.id, item_type='component', component_id=cpu.id,
                             component_name=cpu.name, vendor_id=vendor_a.id,
                             unit_price=80_000, quantity=1))
    db.session.add(CartItem(cart_id=cart.id, item_type='component', component_id=mobo.id,
                             component_name=mobo.name, vendor_id=vendor_b.id,
                             unit_price=30_000, quantity=1))
    db.session.commit()

    _login(client, 'cust@test.com', 'secret123')
    resp = client.post('/api/orders/place', json={'shipping_address': 'Test St'})
    assert resp.status_code == 400
    assert resp.get_json()['error'] == VENDOR_CONFLICT_MESSAGE
    assert Order.query.count() == 0


def test_place_order_allows_single_vendor_build_with_other_vendor_accessory(client, db_session):
    cpu_cat = _cat('Processor', 'cpu')
    mobo_cat = _cat('Motherboard', 'motherboard')
    mouse_cat = _cat('Mouse', 'mouse')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cpu_cat, 80_000)
    mobo = _comp('ASUS B650 Motherboard', mobo_cat, 30_000)
    mouse = _comp('Logitech G102 Mouse', mouse_cat, 3_000)
    build_vendor = _vendor('Build Vendor')
    accessory_vendor = _vendor('Accessory Vendor')
    _stock(build_vendor, cpu, 80_000)
    _stock(build_vendor, mobo, 30_000)
    _stock(accessory_vendor, mouse, 3_000)

    user = _customer()
    cart = Cart(user_id=user.id)
    db.session.add(cart)
    db.session.flush()
    db.session.add(CartItem(cart_id=cart.id, item_type='component', component_id=cpu.id,
                             component_name=cpu.name, vendor_id=build_vendor.id,
                             unit_price=80_000, quantity=1))
    db.session.add(CartItem(cart_id=cart.id, item_type='component', component_id=mobo.id,
                             component_name=mobo.name, vendor_id=build_vendor.id,
                             unit_price=30_000, quantity=1))
    db.session.add(CartItem(cart_id=cart.id, item_type='component', component_id=mouse.id,
                             component_name=mouse.name, vendor_id=accessory_vendor.id,
                             unit_price=3_000, quantity=1))
    db.session.commit()

    _login(client, 'cust@test.com', 'secret123')
    resp = client.post('/api/orders/place', json={'shipping_address': 'Test St'})
    assert resp.status_code == 201, resp.get_json()
    assert Order.query.count() == 1
    order = Order.query.first()
    assert order.items.count() == 3
    # Master order records the single build vendor (not the accessory vendor),
    # matching the "Build vendor" shown at checkout.
    assert order.vendor_id == build_vendor.id


# --- /api/recommend-build -----------------------------------------------------

def test_recommend_build_includes_vendor(client, db_session):
    cpu, mobo, ram, _ = _seed_am5_mini_catalog()
    vendor = _vendor('Full Coverage Vendor')
    _stock(vendor, cpu, 80_000)
    _stock(vendor, mobo, 30_000)
    _stock(vendor, ram, 12_000)
    db.session.commit()

    resp = client.post('/api/recommend-build', json={'purpose': 'Gaming', 'budget': '500000'})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get('vendor_conflict') is False
    assert body.get('vendor', {}).get('id') == vendor.id


# --- /api/evaluate-customization ---------------------------------------------

def test_evaluate_customization_blocks_vendor_only_swap(client, db_session):
    cpu, mobo, ram, ram_cat = _seed_am5_mini_catalog()
    other_ram = _comp('Kingston 16GB DDR5 RAM', ram_cat, 13_000)

    vendor_a = _vendor('Vendor A')
    vendor_b = _vendor('Vendor B')
    _stock(vendor_a, cpu, 80_000)
    _stock(vendor_a, mobo, 30_000)
    _stock(vendor_a, ram, 12_000)
    _stock(vendor_b, other_ram, 13_000)  # hardware-compatible, but a different vendor
    db.session.commit()

    build = {'cpu': cpu.id, 'motherboard': mobo.id, 'ram': ram.id}
    resp = client.post('/api/evaluate-customization', json={
        'purpose': 'Gaming', 'budget': '500000', 'build': build,
        'change': {'slot': 'ram', 'component_id': other_ram.id},
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['level'] == 'incompatible'
    assert VENDOR_CONFLICT_MESSAGE in body['explanation']


def test_evaluate_customization_blocks_swap_covered_only_by_a_different_vendor(client, db_session):
    """Regression: a swap must be validated against the vendor ALREADY locked to
    the rest of the build, not by re-deriving whichever vendor happens to fully
    cover the post-swap combination. Vendor B stocks everything (including the new
    RAM) and would look "fully compatible" if the check re-picked a best vendor
    from scratch — but the cart is locked to Vendor A, which doesn't stock the new
    RAM, so this must still be blocked as a vendor conflict. This is what made the
    /api/build-options dropdown show a candidate as incompatible (✗) while
    /api/evaluate-customization said "Fully Compatible" for the same pick."""
    cpu, mobo, ram, ram_cat = _seed_am5_mini_catalog()
    other_ram = _comp('Kingston 16GB DDR5 RAM', ram_cat, 13_000)

    vendor_a = _vendor('Vendor A')
    vendor_b = _vendor('Vendor B')
    _stock(vendor_a, cpu, 80_000)
    _stock(vendor_a, mobo, 30_000)
    _stock(vendor_a, ram, 12_000)
    # Vendor B fully covers the ORIGINAL build too, plus the new RAM — a vendor that
    # covers the whole post-swap combination exists, but it isn't the locked vendor.
    _stock(vendor_b, cpu, 82_000)
    _stock(vendor_b, mobo, 31_000)
    _stock(vendor_b, other_ram, 13_000)
    db.session.commit()

    build = {'cpu': cpu.id, 'motherboard': mobo.id, 'ram': ram.id}
    resp = client.post('/api/evaluate-customization', json={
        'purpose': 'Gaming', 'budget': '500000', 'build': build,
        'change': {'slot': 'ram', 'component_id': other_ram.id},
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['level'] == 'incompatible'
    assert VENDOR_CONFLICT_MESSAGE in body['explanation']


# --- POST /api/cart (item_type=pc_build) — predefined-build single-vendor rule -----

def test_add_pc_build_to_cart_pins_one_vendor_even_without_explicit_choice(client, db_session):
    """Regression: add_to_cart's 'pc_build' branch used to resolve each component's
    vendor independently (cheapest per-part), so a predefined build could ship split
    across vendors. It must now pin the whole build to one full-coverage vendor,
    exactly like /api/cart/add-build."""
    from app.models import PcBuild, BuildComponent

    cpu_cat = _cat('Processor', 'cpu')
    mobo_cat = _cat('Motherboard', 'motherboard')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cpu_cat, 80_000)
    mobo = _comp('ASUS B650 Motherboard', mobo_cat, 30_000)

    cheap = _vendor('Cheap Vendor')     # stocks both, cheaper CPU
    other = _vendor('Other Vendor')     # stocks both too, but pricier
    _stock(cheap, cpu, 80_000)
    _stock(cheap, mobo, 30_000)
    _stock(other, cpu, 95_000)
    _stock(other, mobo, 35_000)
    # A third vendor that ONLY has the cheapest CPU price — if the old per-component
    # logic were still in place, this vendor would win the CPU line and split the build.
    cpu_only = _vendor('CPU Only Vendor')
    _stock(cpu_only, cpu, 70_000)
    db.session.commit()

    build = PcBuild(name='Test Predefined Build', build_type='gaming', total_price=0)
    db.session.add(build)
    db.session.flush()
    db.session.add(BuildComponent(pc_build_id=build.id, component_id=cpu.id, quantity=1))
    db.session.add(BuildComponent(pc_build_id=build.id, component_id=mobo.id, quantity=1))
    db.session.commit()

    resp = client.post('/api/add-to-cart', json={'item_type': 'pc_build', 'item_id': build.id, 'quantity': 1})
    assert resp.status_code == 200, resp.get_json()
    items = resp.get_json()['cart']['items']
    assert len(items) == 2
    # Every line must resolve to the SAME vendor — never split.
    assert len({it['vendor_id'] for it in items}) == 1
    assert {it['vendor_id'] for it in items} == {cheap.id}


def test_add_pc_build_to_cart_rejects_when_no_vendor_covers_all(client, db_session):
    from app.models import PcBuild, BuildComponent

    cpu_cat = _cat('Processor', 'cpu')
    mobo_cat = _cat('Motherboard', 'motherboard')
    cpu = _comp('AMD Ryzen 7 7700 Processor', cpu_cat, 80_000)
    mobo = _comp('ASUS B650 Motherboard', mobo_cat, 30_000)
    vendor_a = _vendor('Vendor A')
    vendor_b = _vendor('Vendor B')
    _stock(vendor_a, cpu, 80_000)   # only stocks the CPU
    _stock(vendor_b, mobo, 30_000)  # only stocks the motherboard
    db.session.commit()

    build = PcBuild(name='Unshippable Build', build_type='gaming', total_price=0)
    db.session.add(build)
    db.session.flush()
    db.session.add(BuildComponent(pc_build_id=build.id, component_id=cpu.id, quantity=1))
    db.session.add(BuildComponent(pc_build_id=build.id, component_id=mobo.id, quantity=1))
    db.session.commit()

    resp = client.post('/api/add-to-cart', json={'item_type': 'pc_build', 'item_id': build.id, 'quantity': 1})
    assert resp.status_code == 409
    assert resp.get_json()['code'] == 'VENDOR_CONFLICT'

    cart_resp = client.get('/api/cart')
    assert cart_resp.get_json()['cart']['items'] == []


# --- Admin build_add/build_edit compatibility + vendor-coverage gate ---------------

def test_validate_build_components_flags_incompatible_and_uncovered_builds(db_session):
    """Regression: admin PcBuild creation used to allow saving any component
    combination with zero compatibility or vendor-coverage checks (how the real
    'Gaming - Budget Build' shipped with a 450W PSU under a 550W load). The admin
    routes now call this helper before commit."""
    from app.admin.routes import _validate_build_components

    cpu_cat = _cat('Processor', 'cpu')
    gpu_cat = _cat('GPU', 'gpu')
    psu_cat = _cat('PSU', 'psu')
    cpu = _comp('AMD Ryzen 5 5600G 6-Core Processor', cpu_cat, 30_000)
    gpu = _comp('NVIDIA GeForce RTX 4060 8GB', gpu_cat, 60_000)
    undersized_psu = _comp('Cooler Master MWE 450W 80+ Bronze', psu_cat, 8_000)
    vendor = _vendor('Solo Vendor')
    _stock(vendor, cpu, 30_000)
    _stock(vendor, gpu, 60_000)
    _stock(vendor, undersized_psu, 8_000)
    db.session.commit()

    by_slot = {'Processor': cpu, 'GPU': gpu, 'PSU': undersized_psu}
    qty = {cpu.id: 1, gpu.id: 1, undersized_psu.id: 1}
    errors = _validate_build_components(by_slot, qty)
    assert errors, 'undersized PSU must be flagged as a compatibility failure'
    assert any('Compatibility' in e for e in errors)

    # Same CPU/GPU but no vendor stocks all three -> flagged as a coverage failure.
    other_vendor = _vendor('Partial Vendor')
    _stock(other_vendor, cpu, 30_000)
    _stock(other_vendor, gpu, 60_000)
    db.session.commit()
    proper_psu = _comp('Cooler Master MWE 650W 80+ Gold', psu_cat, 12_000)
    by_slot2 = {'Processor': cpu, 'GPU': gpu, 'PSU': proper_psu}
    qty2 = {cpu.id: 1, gpu.id: 1, proper_psu.id: 1}
    errors2 = _validate_build_components(by_slot2, qty2)
    assert errors2, 'no vendor stocks the 650W PSU -> must be flagged as unshippable'
    assert any('single vendor' in e for e in errors2)

    # A fully compatible, fully-covered build passes clean.
    _stock(vendor, proper_psu, 12_000)
    db.session.commit()
    by_slot3 = {'Processor': cpu, 'GPU': gpu, 'PSU': proper_psu}
    assert _validate_build_components(by_slot3, qty2) == []
