from flask import jsonify, request, session
from flask_login import current_user
from sqlalchemy import case

from app import db
from app.models import Cart, CartItem, PcBuild, Component, BuildComponent, Vendor, VendorComponent


def _get_cart_response(cart):
    items = cart.items.all()
    result_items = []
    vendor_groups = {}
    total = 0
    count = 0

    for ci in items:
        component = Component.query.get(ci.component_id) if ci.component_id else None
        if not component:
            db.session.delete(ci)
            continue

        price = float(ci.unit_price or component.price or 0)
        stock = int(component.stock or 0)
        quantity = int(ci.quantity or 0)
        subtotal = price * quantity
        vendor = Vendor.query.get(ci.vendor_id) if ci.vendor_id else None
        vendor_name = vendor.shop_name if vendor else 'Unassigned'

        line = {
            'cart_item_id': ci.id,
            'item_type': ci.item_type or 'component',
            'component_id': component.id,
            'component_name': ci.component_name or component.name,
            'category': component.category.name if component.category else None,
            'pc_build_id': ci.pc_build_id,
            'vendor_id': ci.vendor_id,
            'vendor_name': vendor_name,
            'price': price,
            'image_url': component.image_url,
            'stock': stock,
            'quantity': quantity,
            'subtotal': subtotal,
        }
        result_items.append(line)
        key = str(ci.vendor_id or 0)
        group = vendor_groups.setdefault(key, {
            'vendor_id': ci.vendor_id,
            'vendor_name': vendor_name,
            'subtotal': 0.0,
            'items': [],
        })
        group['items'].append(line)
        group['subtotal'] += subtotal

        total += subtotal
        count += quantity

    db.session.commit()

    return {
        'items': result_items,
        'vendor_groups': list(vendor_groups.values()),
        'total': total,
        'count': count,
    }


def _select_vendor_for_component(component_id, required_qty, requested_vendor_id=None):
    query = (
        VendorComponent.query
        .join(Vendor, Vendor.id == VendorComponent.vendor_id)
        .filter(VendorComponent.component_id == component_id, VendorComponent.quantity >= required_qty)
        .filter(Vendor.approval_status == 'approved')
    )
    if requested_vendor_id:
        link = query.filter(VendorComponent.vendor_id == requested_vendor_id).first()
        return link
    # MySQL does not support NULLS LAST; use CASE so NULL prices sort after real prices.
    return query.order_by(
        case((VendorComponent.price.is_(None), 1), else_=0),
        VendorComponent.price.asc(),
    ).first()


def _upsert_component_cart_item(cart_id, component_id, vendor_id, quantity, pc_build_id=None, item_type='component'):
    component = Component.query.get(component_id)
    if not component:
        return {'success': False, 'error': f'Component {component_id} not found'}, 404
    if quantity <= 0:
        return {'success': False, 'error': 'Quantity must be >= 1'}, 400

    link = _select_vendor_for_component(component_id, quantity, vendor_id)
    if not link:
        return {'success': False, 'error': f'No approved vendor with stock for component {component_id}'}, 400

    vendor_row = Vendor.query.get(link.vendor_id)

    existing = CartItem.query.filter_by(
        cart_id=cart_id,
        component_id=component_id,
        vendor_id=link.vendor_id,
    ).first()
    # Charge the price of the vendor actually selected above (cheapest in-stock
    # approved vendor), not the catalog price — these can differ, and the catalog
    # price silently overriding the vendor price was why the cart could charge more
    # than the "effective_price" shown in search/configurator estimates.
    unit_price = link.price if link.price else (component.price or 0)
    if existing:
        existing.quantity = int(existing.quantity or 0) + quantity
        existing.unit_price = unit_price
        existing.component_name = component.name
        existing.item_type = item_type
        if pc_build_id:
            existing.pc_build_id = pc_build_id
    else:
        db.session.add(CartItem(
            cart_id=cart_id,
            product_id=pc_build_id,
            item_type=item_type,
            pc_build_id=pc_build_id,
            component_id=component_id,
            component_name=component.name,
            vendor_id=link.vendor_id,
            unit_price=unit_price,
            quantity=quantity,
        ))
    return {
        'success': True,
        'vendor_id': link.vendor_id,
        'vendor_shop_name': vendor_row.shop_name if vendor_row else None,
    }, 200


def _merge_guest_cart_into_user_cart(user_cart):
    """
    If a guest cart exists in session and user is now logged in,
    move/merge guest items into user cart.
    """
    guest_cart_id = session.get('cart_id')
    if not guest_cart_id:
        return

    if guest_cart_id == user_cart.id:
        return

    guest_cart = Cart.query.get(int(guest_cart_id))
    if not guest_cart:
        return

    # Only merge true guest carts.
    if guest_cart.user_id is not None:
        return

    guest_items = guest_cart.items.all()
    for gi in guest_items:
        existing = CartItem.query.filter_by(
            cart_id=user_cart.id,
            component_id=gi.component_id,
            vendor_id=gi.vendor_id,
        ).first()
        if existing:
            existing.quantity = int(existing.quantity or 0) + int(gi.quantity or 0)
        else:
            db.session.add(CartItem(
                cart_id=user_cart.id,
                product_id=gi.product_id,
                item_type=gi.item_type or 'component',
                pc_build_id=gi.pc_build_id,
                component_id=gi.component_id,
                component_name=gi.component_name,
                vendor_id=gi.vendor_id,
                unit_price=gi.unit_price,
                quantity=gi.quantity,
            ))

    db.session.delete(guest_cart)
    db.session.commit()


def _get_or_create_cart():
    """
    Identify current cart scope:
    - Logged in user: cart tied to user_id
    - Guest: cart id stored in session['cart_id']
    """
    if current_user.is_authenticated:
        user_cart = Cart.query.filter_by(user_id=current_user.id).first()
        if not user_cart:
            user_cart = Cart(user_id=current_user.id)
            db.session.add(user_cart)
            db.session.commit()

        _merge_guest_cart_into_user_cart(user_cart)
        session['cart_id'] = user_cart.id
        return user_cart

    cart_id = session.get('cart_id')
    if cart_id:
        cart = Cart.query.get(int(cart_id))
        if cart:
            return cart

    cart = Cart(user_id=None)
    db.session.add(cart)
    db.session.commit()
    session['cart_id'] = cart.id
    return cart


def add_to_cart():
    payload = request.get_json(silent=True) or {}
    item_type = (payload.get('item_type') or 'component').strip().lower()
    item_id = payload.get('item_id') or payload.get('component_id') or payload.get('product_id')
    quantity = payload.get('quantity', 1)
    vendor_id = payload.get('vendor_id')

    try:
        item_id = int(item_id)
        quantity = int(quantity)
        vendor_id = int(vendor_id) if vendor_id is not None else None
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Invalid item_id/quantity/vendor_id'}), 400

    if quantity <= 0:
        return jsonify({'success': False, 'error': 'Quantity must be >= 1'}), 400

    cart = _get_or_create_cart()

    assigned_vendors = []

    if item_type == 'pc_build':
        from app.services.vendor_coverage import vendor_coverage_for_components, VENDOR_CONFLICT_MESSAGE

        build = PcBuild.query.get(item_id)
        if not build or not getattr(build, 'is_active', True):
            return jsonify({'success': False, 'error': 'Build not found'}), 404
        build_components = BuildComponent.query.filter_by(pc_build_id=build.id).all()
        if not build_components:
            return jsonify({'success': False, 'error': 'Build has no components'}), 400

        # Single-vendor-per-build: assembly is performed by the supplying vendor, so
        # a predefined build can never be split across vendors. Resolve (or verify)
        # ONE vendor that stocks every part before adding anything to the cart.
        req_qty_by_component = {
            bc.component_id: int(bc.quantity or 0) * quantity for bc in build_components
        }
        coverage = vendor_coverage_for_components(req_qty_by_component)
        if not coverage['covers_all']:
            return jsonify({
                'success': False,
                'error': VENDOR_CONFLICT_MESSAGE,
                'code': 'VENDOR_CONFLICT',
                'missing_component_ids': coverage['missing_component_ids'],
            }), 409

        chosen_vendor = coverage['best']
        if vendor_id is not None:
            chosen_vendor = next(
                (v for v in coverage['vendors'] if v['id'] == vendor_id and v['full_coverage']),
                None,
            )
            if not chosen_vendor:
                return jsonify({
                    'success': False,
                    'error': 'Selected vendor no longer has every part in stock. Please pick another vendor.',
                    'code': 'VENDOR_CONFLICT',
                }), 409

        build_vendor_id = chosen_vendor['id']
        for bc in build_components:
            req_qty = int(bc.quantity or 0) * quantity
            result, status = _upsert_component_cart_item(
                cart_id=cart.id,
                component_id=bc.component_id,
                vendor_id=build_vendor_id,
                quantity=req_qty,
                pc_build_id=build.id,
                item_type='pc_build_component',
            )
            if not result.get('success'):
                db.session.rollback()
                return jsonify(result), status
            if result.get('vendor_shop_name'):
                assigned_vendors.append({
                    'component_id': bc.component_id,
                    'vendor_id': result.get('vendor_id'),
                    'shop_name': result.get('vendor_shop_name'),
                })
    else:
        result, status = _upsert_component_cart_item(
            cart_id=cart.id,
            component_id=item_id,
            vendor_id=vendor_id,
            quantity=quantity,
            item_type='component',
        )
        if not result.get('success'):
            db.session.rollback()
            return jsonify(result), status
        if result.get('vendor_shop_name'):
            assigned_vendors.append({
                'component_id': item_id,
                'vendor_id': result.get('vendor_id'),
                'shop_name': result.get('vendor_shop_name'),
            })

    db.session.commit()
    cart_data = _get_cart_response(cart)
    assigned_vendor = assigned_vendors[0] if len(assigned_vendors) == 1 else None
    payload = {
        'success': True,
        'message': 'Added to cart',
        'cart': cart_data,
        'assigned_vendors': assigned_vendors,
    }
    if assigned_vendor:
        payload['assigned_vendor'] = {
            'id': assigned_vendor['vendor_id'],
            'shop_name': assigned_vendor['shop_name'],
            'component_id': assigned_vendor.get('component_id'),
        }
    return jsonify(payload), 200


def add_build_to_cart():
    """POST /api/cart/add-build — add a whole PC build at once, pinned to ONE vendor
    (assembly is performed by the supplying vendor, so a build can't be split).

    Each call is authoritative for the build: existing build-category cart rows not
    present in this submission (or pinned to a different vendor than the one this
    build resolves to) are replaced, so re-adding after customizing one part in
    BuildCustomizer always converges to a single, consistent vendor.

    Optional `vendor_id` in the payload pins the build to that specific vendor
    (must be one of the full-coverage vendors); omit it to auto-pick the
    cheapest full-coverage vendor, as before.
    """
    from app.services.vendor_coverage import vendor_coverage_for_components, VENDOR_CONFLICT_MESSAGE

    payload = request.get_json(silent=True) or {}
    raw_components = payload.get('components') or []

    comp_qty: dict[int, int] = {}
    for row in raw_components:
        cid = row.get('component_id') or row.get('id')
        try:
            cid = int(cid)
            qty = int(row.get('quantity') or 1)
        except (TypeError, ValueError):
            continue
        if qty > 0:
            comp_qty[cid] = comp_qty.get(cid, 0) + qty

    if not comp_qty:
        return jsonify({'success': False, 'error': 'No components provided'}), 400

    requested_vendor_id = payload.get('vendor_id')
    try:
        requested_vendor_id = int(requested_vendor_id) if requested_vendor_id is not None else None
    except (TypeError, ValueError):
        requested_vendor_id = None

    coverage = vendor_coverage_for_components(comp_qty)
    if not coverage['covers_all']:
        return jsonify({
            'success': False,
            'error': VENDOR_CONFLICT_MESSAGE,
            'code': 'VENDOR_CONFLICT',
            'missing_component_ids': coverage['missing_component_ids'],
            'best_vendor': coverage['best'],
        }), 409

    chosen_vendor = coverage['best']
    if requested_vendor_id is not None:
        chosen_vendor = next(
            (v for v in coverage['vendors'] if v['id'] == requested_vendor_id and v['full_coverage']),
            None,
        )
        if not chosen_vendor:
            return jsonify({
                'success': False,
                'error': 'Selected vendor no longer has every part in stock. Please pick another vendor.',
                'code': 'VENDOR_CONFLICT',
                'missing_component_ids': [],
                'best_vendor': coverage['best'],
            }), 409

    vendor_id = chosen_vendor['id']
    cart = _get_or_create_cart()

    from app.services.vendor_coverage import build_category_names
    build_cats = build_category_names()
    for ci in CartItem.query.filter_by(cart_id=cart.id).all():
        component = Component.query.get(ci.component_id) if ci.component_id else None
        cat_name = component.category.name if component and component.category else None
        if cat_name not in build_cats:
            continue
        if ci.component_id not in comp_qty or ci.vendor_id != vendor_id:
            db.session.delete(ci)
    db.session.flush()

    for component_id, qty in comp_qty.items():
        result, status = _upsert_component_cart_item(
            cart_id=cart.id, component_id=component_id, vendor_id=vendor_id,
            quantity=qty, item_type='pc_build_component',
        )
        if not result.get('success'):
            db.session.rollback()
            return jsonify(result), status

    db.session.commit()
    cart_data = _get_cart_response(cart)
    return jsonify({
        'success': True,
        'message': 'Build added to cart',
        'cart': cart_data,
        'vendor': {'id': vendor_id, 'shop_name': chosen_vendor['shop_name']},
    }), 200


def get_build_vendor_options():
    """POST /api/cart/build-coverage — read-only: which vendors can fully supply this
    set of components. Lets the frontend show an eligible-vendor picker before
    committing via /api/cart/add-build (mirrors the same single-vendor rule, but
    without mutating the cart).
    """
    from app.services.vendor_coverage import vendor_coverage_for_components

    payload = request.get_json(silent=True) or {}
    raw_components = payload.get('components') or []

    comp_qty: dict[int, int] = {}
    for row in raw_components:
        cid = row.get('component_id') or row.get('id')
        try:
            cid = int(cid)
            qty = int(row.get('quantity') or 1)
        except (TypeError, ValueError):
            continue
        if qty > 0:
            comp_qty[cid] = comp_qty.get(cid, 0) + qty

    if not comp_qty:
        return jsonify({'success': False, 'error': 'No components provided'}), 400

    coverage = vendor_coverage_for_components(comp_qty)
    eligible = [v for v in coverage['vendors'] if v['full_coverage']]
    eligible.sort(key=lambda v: v['total_price'])

    return jsonify({
        'success': True,
        'covers_all': coverage['covers_all'],
        'vendors': eligible,
        'missing_component_ids': coverage['missing_component_ids'],
    }), 200


def get_cart():
    cart = _get_or_create_cart()
    cart_data = _get_cart_response(cart)
    return jsonify({'success': True, 'cart': cart_data}), 200


def update_cart():
    payload = request.get_json(silent=True) or {}
    cart_item_id = payload.get('cart_item_id')
    quantity = payload.get('quantity')

    try:
        cart_item_id = int(cart_item_id)
        quantity = int(quantity)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Invalid cart_item_id/quantity'}), 400

    cart = _get_or_create_cart()

    cart_item = CartItem.query.get(cart_item_id)
    if not cart_item or cart_item.cart_id != cart.id:
        return jsonify({'success': False, 'error': 'Cart item not found'}), 404

    if quantity <= 0:
        db.session.delete(cart_item)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Item removed', 'cart': _get_cart_response(cart)}), 200

    component = Component.query.get(cart_item.component_id) if cart_item.component_id else None
    if not component:
        return jsonify({'success': False, 'error': 'Component not found'}), 404

    # Validate against the pinned vendor's real stock (VendorComponent), not the
    # legacy catalog-wide Component.stock — this cart line is only ever fulfilled
    # by the vendor it was assigned to at add-to-cart time.
    vendor_stock = (
        VendorComponent.query
        .filter_by(vendor_id=cart_item.vendor_id, component_id=cart_item.component_id)
        .first()
        if cart_item.vendor_id else None
    )
    stock = int(vendor_stock.quantity or 0) if vendor_stock else 0
    if stock <= 0:
        return jsonify({'success': False, 'error': 'Out of stock', 'max_quantity': 0}), 400

    if quantity > stock:
        return jsonify({'success': False, 'error': 'Out of stock limit', 'max_quantity': stock}), 400

    cart_item.quantity = quantity
    db.session.commit()
    return jsonify({'success': True, 'message': 'Cart updated', 'cart': _get_cart_response(cart)}), 200


def remove_item():
    payload = request.get_json(silent=True) or {}
    cart_item_id = payload.get('cart_item_id')

    try:
        cart_item_id = int(cart_item_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Invalid cart_item_id'}), 400

    cart = _get_or_create_cart()
    cart_item = CartItem.query.get(cart_item_id)
    if not cart_item or cart_item.cart_id != cart.id:
        return jsonify({'success': False, 'error': 'Cart item not found'}), 404

    db.session.delete(cart_item)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Item removed', 'cart': _get_cart_response(cart)}), 200


def clear_cart():
    cart = _get_or_create_cart()
    CartItem.query.filter_by(cart_id=cart.id).delete()
    db.session.commit()
    return jsonify({'success': True, 'message': 'Cart cleared', 'cart': _get_cart_response(cart)}), 200

