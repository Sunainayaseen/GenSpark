# Vendor Panel Routes - GenSpark
import os
from types import SimpleNamespace
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user, logout_user
from functools import wraps
from werkzeug.utils import secure_filename
from app.vendor import vendor_bp
from app import db
from app.models import (
    User, Vendor, Component, ComponentCategory, ComponentBrand, VendorComponent,
    PcBuild, Order, OrderItem, AssemblyTracking, Shipment, Payment,
    VendorOrder, VendorOrderItem,
    VendorDocument, VendorRating, Transaction
)
from app.models.order import sync_master_order_status_from_vendor_orders
from sqlalchemy import func, text


_ALLOWED_PROOF_EXTS = {'.png', '.jpg', '.jpeg', '.webp'}


def _save_proof_image(file_storage):
    """Save uploaded proof image under static/uploads/proofs and return public URL path."""
    if not file_storage or not getattr(file_storage, 'filename', ''):
        return None

    filename = secure_filename(file_storage.filename)
    _, ext = os.path.splitext(filename.lower())
    if ext not in _ALLOWED_PROOF_EXTS:
        raise ValueError('Only PNG/JPG/WEBP images are allowed.')

    # Store inside app static so it can be served via url_for('static', ...)
    proofs_dir = os.path.join(vendor_bp.root_path, '..', 'static', 'uploads', 'proofs')
    proofs_dir = os.path.abspath(proofs_dir)
    os.makedirs(proofs_dir, exist_ok=True)

    # Make filename unique to avoid collisions
    from datetime import datetime
    stamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    final_name = f'proof_{stamp}{ext}'
    abs_path = os.path.join(proofs_dir, final_name)
    file_storage.save(abs_path)

    return url_for('static', filename=f'uploads/proofs/{final_name}')


def _get_brands_for_dropdown():
    """Load brands for dropdowns: try ORM first, then raw SQL (brand_id, brand_name)."""
    try:
        return ComponentBrand.query.order_by(ComponentBrand.name).all()
    except Exception:
        try:
            rows = db.session.execute(text("SELECT brand_id, brand_name FROM brands")).fetchall()
            return [SimpleNamespace(id=r[0], name=r[1]) for r in rows]
        except Exception:
            return []


def vendor_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login.', 'danger')
            return redirect(url_for('auth.login'))
        if not current_user.is_vendor:
            # Prevent admin/customer session from auto-redirecting back to admin pages.
            # Force a fresh login so vendor can sign in explicitly.
            logout_user()
            flash('Please login with a vendor account.', 'warning')
            return redirect(url_for('auth.login'))
        vendor = Vendor.query.filter_by(user_id=current_user.id).first()
        if not vendor:
            flash('Vendor profile not found. Complete registration.', 'warning')
            return redirect(url_for('vendor.profile'))
        if vendor.approval_status != 'approved':
            flash('Your vendor account is not approved yet.', 'warning')
            return redirect(url_for('vendor.dashboard'))
        return f(*args, **kwargs)
    return decorated


def get_vendor():
    return Vendor.query.filter_by(user_id=current_user.id).first()


@vendor_bp.context_processor
def inject_vendor_notifications():
    """Feed the vendor navbar bell with the logged-in user's recent notifications
    (e.g. 'New order assigned'). Injected into every vendor-portal template."""
    from app.models import Notification
    if not current_user.is_authenticated:
        return {'vendor_notifications': [], 'vendor_unread_count': 0}
    try:
        rows = (Notification.query
                .filter_by(user_id=current_user.id)
                .order_by(Notification.created_at.desc())
                .limit(8).all())
        unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    except Exception:
        rows, unread = [], 0
    return {'vendor_notifications': rows, 'vendor_unread_count': unread}


@vendor_bp.route('/notifications/read-all')
@login_required
def notifications_read_all():
    """Mark all of the logged-in vendor user's notifications as read, then go back."""
    from app.models import Notification
    if current_user.is_authenticated:
        Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
        db.session.commit()
    return redirect(request.referrer or url_for('vendor.dashboard'))


@vendor_bp.route('/')
@vendor_bp.route('/dashboard')
@vendor_required
def dashboard():
    vendor = get_vendor()
    if not vendor:
        return redirect(url_for('vendor.profile'))
    if vendor.approval_status != 'approved':
        return render_template('vendor/dashboard.html', vendor=vendor, approved=False)
    # Orders are multi-vendor (per line item) → count this vendor's VendorOrder rows,
    # not the master Order (whose vendor_id is NULL for multi-vendor orders).
    vo_q = VendorOrder.query.filter_by(vendor_id=vendor.id)
    total_orders = vo_q.count()
    pending_orders = vo_q.filter(VendorOrder.status == 'assigned').count()
    assembly_orders = vo_q.filter(VendorOrder.status.in_(['accepted', 'assembling'])).count()
    completed_orders = vo_q.filter(VendorOrder.status == 'completed').count()
    # Earnings = value of this vendor's completed orders.
    earnings = db.session.query(func.coalesce(func.sum(VendorOrder.total_amount), 0)).filter(
        VendorOrder.vendor_id == vendor.id, VendorOrder.status == 'completed'
    ).scalar() or 0
    return render_template('vendor/dashboard.html',
        vendor=vendor, approved=True,
        total_orders=total_orders, pending_orders=pending_orders,
        assembly_orders=assembly_orders, completed_orders=completed_orders,
        earnings=earnings
    )


# ---------- Vendor Profile (Registration) ----------
@vendor_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    vendor = get_vendor()
    if request.method == 'POST':
        shop_name = request.form.get('shop_name', '').strip()
        city = request.form.get('city', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()
        if not shop_name:
            flash('Shop name is required.', 'danger')
            return render_template('vendor/profile.html', vendor=vendor)
        if vendor:
            vendor.shop_name = shop_name
            vendor.city = city
            vendor.address = address
            vendor.phone = phone
            flash('Profile updated.', 'success')
            is_new = False
        else:
            vendor = Vendor(user_id=current_user.id, shop_name=shop_name, city=city, address=address, phone=phone)
            db.session.add(vendor)
            flash('Vendor profile created. Waiting for admin approval.', 'success')
            is_new = True
        db.session.commit()
        # New vendor registration → tell admins there's an account to approve.
        if is_new:
            try:
                from app.services.notification_service import notify_admin_new_vendor
                notify_admin_new_vendor(vendor)
            except Exception as _e:
                print('notify admin new-vendor skipped:', _e)
        return redirect(url_for('vendor.dashboard'))
    return render_template('vendor/profile.html', vendor=vendor)


@vendor_bp.route('/account/delete', methods=['GET', 'POST'])
@login_required
def account_delete():
    vendor = get_vendor()
    if not vendor:
        flash('No vendor profile to delete.', 'warning')
        return redirect(url_for('vendor.dashboard'))
    if request.method == 'POST':
        confirm = request.form.get('confirm') == 'yes'
        if not confirm:
            flash('Account was not deleted. Please check the box to confirm.', 'warning')
            return redirect(url_for('vendor.account_delete'))
        vendor_id = vendor.id
        user_id = current_user.id
        # Unlink orders and transactions from this vendor
        Order.query.filter_by(vendor_id=vendor_id).update({'vendor_id': None})
        Transaction.query.filter_by(vendor_id=vendor_id).update({'vendor_id': None})
        # Delete vendor-related records
        VendorComponent.query.filter_by(vendor_id=vendor_id).delete()
        VendorDocument.query.filter_by(vendor_id=vendor_id).delete()
        VendorRating.query.filter_by(vendor_id=vendor_id).delete()
        db.session.delete(vendor)
        user = User.query.get(user_id)
        if user:
            db.session.delete(user)
        db.session.commit()
        logout_user()
        flash('Your vendor account has been deleted. You can sign up again anytime.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('vendor/account_delete_confirm.html', vendor=vendor)


# ---------- Inventory (Vendor's components) ----------
@vendor_bp.route('/inventory')
@login_required
@vendor_required
def inventory():
    vendor = get_vendor()
    brand_id = request.args.get('brand_id', type=int)
    items = VendorComponent.query.filter_by(vendor_id=vendor.id).all()
    if brand_id is not None:
        items = [i for i in items if i.component and i.component.brand_id == brand_id]
    brands = _get_brands_for_dropdown()
    return render_template('vendor/inventory.html', vendor=vendor, items=items, brands=brands, selected_brand_id=brand_id)


@vendor_bp.route('/inventory/add', methods=['GET', 'POST'])
@login_required
@vendor_required
def inventory_add():
    vendor = get_vendor()
    brand_id = request.args.get('brand_id', type=int) if request.method == 'GET' else None
    query = Component.query.order_by(Component.name)
    if brand_id is not None:
        query = query.filter(Component.brand_id == brand_id)
    components = query.all()
    brands = _get_brands_for_dropdown()
    if request.method == 'POST':
        component_id = request.form.get('component_id', type=int)
        quantity = request.form.get('quantity', type=int) or 0
        price = request.form.get('price', type=float)
        if component_id and quantity >= 0:
            existing = VendorComponent.query.filter_by(vendor_id=vendor.id, component_id=component_id).first()
            if existing:
                existing.quantity = quantity
                if price is not None:
                    existing.price = price
            else:
                vc = VendorComponent(vendor_id=vendor.id, component_id=component_id, quantity=quantity, price=price)
                db.session.add(vc)
            db.session.commit()
            flash('Inventory updated.', 'success')
            return redirect(url_for('vendor.inventory'))
    return render_template('vendor/inventory_form.html', vendor=vendor, components=components, brands=brands, selected_brand_id=brand_id, item=None)


# ---------- Orders ----------
@vendor_bp.route('/orders')
@login_required
@vendor_required
def orders_list():
    vendor = get_vendor()
    vendor_orders = VendorOrder.query.filter_by(vendor_id=vendor.id).order_by(VendorOrder.created_at.desc()).all()
    my_orders = []
    for vo in vendor_orders:
        master = Order.query.get(vo.order_id)
        customer = master.customer if master else None
        my_orders.append(SimpleNamespace(
            id=vo.id,
            order_number=(master.order_number if master else f'ORD-{vo.order_id}') + f' / VO-{vo.id}',
            customer=customer,
            total_amount=vo.total_amount,
            status=vo.status,
            created_at=vo.created_at,
        ))
    return render_template('vendor/orders_list.html', vendor=vendor, orders=my_orders, available_orders=[])


@vendor_bp.route('/orders/<int:order_id>/accept', methods=['POST'])
@login_required
@vendor_required
def order_accept(order_id):
    vendor = get_vendor()
    order = VendorOrder.query.filter_by(id=order_id, vendor_id=vendor.id).first_or_404()
    if order.status != 'assigned':
        flash('Vendor order is not available for acceptance.', 'warning')
        return redirect(url_for('vendor.orders_list'))
    order.status = 'accepted'
    db.session.commit()
    flash('Order accepted.', 'success')
    return redirect(url_for('vendor.orders_list'))


@vendor_bp.route('/orders/<int:order_id>')
@login_required
@vendor_required
def order_detail(order_id):
    vendor = get_vendor()
    v_order = VendorOrder.query.filter_by(id=order_id, vendor_id=vendor.id).first_or_404()
    master = Order.query.get(v_order.order_id)
    customer = master.customer if master else None
    items = []
    for item in v_order.items.all():
        items.append(SimpleNamespace(
            item_type='component',
            item_id=item.component_id,
            component_name=item.component_name,
            quantity=item.quantity,
            total_price=item.total_price,
        ))
    order_view = SimpleNamespace(
        id=v_order.id,
        order_number=(master.order_number if master else f'ORD-{v_order.order_id}') + f' / VO-{v_order.id}',
        customer=customer,
        total_amount=v_order.total_amount,
        status=v_order.status,
        shipping_address=master.shipping_address if master else None,
        items=items,
        proof_image_url=v_order.proof_image_url,
        proof_approved=v_order.proof_approved,
    )
    return render_template('vendor/order_detail.html', vendor=vendor, order=order_view)


@vendor_bp.route('/orders/<int:order_id>/status', methods=['POST'])
@login_required
@vendor_required
def vendor_order_status_update(order_id):
    vendor = get_vendor()
    v_order = VendorOrder.query.filter_by(id=order_id, vendor_id=vendor.id).first_or_404()
    status = (request.form.get('status') or '').strip().lower()
    proof_image_url = (request.form.get('proof_image_url') or '').strip() or None
    proof_file = request.files.get('proof_image')
    if status not in ('accepted', 'assembling', 'completed', 'rejected'):
        flash('Invalid vendor order status.', 'warning')
        return redirect(url_for('vendor.order_detail', order_id=order_id))

    # Admin policy: a vendor must send a completion proof photo before completing.
    if status == 'completed':
        has_new_proof = bool(proof_file and getattr(proof_file, 'filename', ''))
        has_existing_proof = bool(v_order.proof_image_url) or bool(proof_image_url)
        if not has_new_proof and not has_existing_proof:
            flash('Please upload a completion proof image before marking this order as completed.', 'warning')
            return redirect(url_for('vendor.order_detail', order_id=order_id))

    v_order.status = status
    proof_just_submitted = False
    if proof_file and getattr(proof_file, 'filename', ''):
        try:
            v_order.proof_image_url = _save_proof_image(proof_file)
            v_order.proof_approved = False
            proof_just_submitted = True
        except ValueError as e:
            flash(str(e), 'warning')
            return redirect(url_for('vendor.order_detail', order_id=order_id))
    elif proof_image_url:
        v_order.proof_image_url = proof_image_url
        v_order.proof_approved = False
        proof_just_submitted = True
    if status == 'rejected':
        v_order.rejection_reason = (request.form.get('rejection_reason') or '').strip() or None

    parent = Order.query.get(v_order.order_id)
    if parent:
        sync_master_order_status_from_vendor_orders(parent.id)

    db.session.commit()

    # Notify admins when a completion proof is submitted — they must verify it
    # before the order can be released for dispatch.
    if status == 'completed' and proof_just_submitted:
        try:
            from app.services.notification_service import notify_admin_vendor_proof
            notify_admin_vendor_proof(v_order)
        except Exception as _e:
            print('notify admin vendor-proof skipped:', _e)

    flash('Vendor order status updated.', 'success')
    return redirect(url_for('vendor.order_detail', order_id=order_id))


# ---------- Assembly ----------
@vendor_bp.route('/assembly')
@login_required
@vendor_required
def assembly_list():
    vendor = get_vendor()
    orders = Order.query.filter_by(vendor_id=vendor.id).filter(
        Order.status.in_(['accepted', 'assembly'])
    ).order_by(Order.updated_at.desc()).all()
    return render_template('vendor/assembly_list.html', vendor=vendor, orders=orders)


@vendor_bp.route('/assembly/order/<int:order_id>/update', methods=['GET', 'POST'])
@login_required
@vendor_required
def assembly_update(order_id):
    vendor = get_vendor()
    order = Order.query.filter_by(id=order_id, vendor_id=vendor.id).first_or_404()
    tracking = AssemblyTracking.query.filter_by(order_id=order.id).order_by(AssemblyTracking.created_at.desc()).first()
    if request.method == 'POST':
        stage = request.form.get('stage', 'in_assembly')
        notes = request.form.get('progress_notes', '')
        if not tracking:
            tracking = AssemblyTracking(order_id=order.id, stage=stage, progress_notes=notes)
            db.session.add(tracking)
        else:
            tracking.stage = stage
            tracking.progress_notes = notes
        if stage == 'completed':
            order.status = 'qa'
        else:
            order.status = 'assembly'
        db.session.commit()
        flash('Assembly status updated.', 'success')
        return redirect(url_for('vendor.assembly_list'))
    return render_template('vendor/assembly_update.html', vendor=vendor, order=order, tracking=tracking)


# ---------- Shipment ----------
@vendor_bp.route('/shipment')
@login_required
@vendor_required
def shipment_list():
    vendor = get_vendor()
    # Shipments for orders this vendor is linked to (legacy single-vendor OR multi-vendor VendorOrder rows)
    vo_order_ids = {r[0] for r in db.session.query(VendorOrder.order_id).filter_by(vendor_id=vendor.id).distinct()}
    legacy_order_ids = {r[0] for r in db.session.query(Order.id).filter_by(vendor_id=vendor.id).all()}
    ship_order_ids = vo_order_ids | legacy_order_ids
    shipment_rows = []
    if ship_order_ids:
        shipments = Shipment.query.filter(Shipment.order_id.in_(ship_order_ids)).order_by(Shipment.created_at.desc()).all()
    else:
        shipments = []
    # Resolve vendor order id for "View order" links (route expects VendorOrder.id, not master Order.id)
    for s in shipments:
        vo = VendorOrder.query.filter_by(order_id=s.order_id, vendor_id=vendor.id).first()
        shipment_rows.append(SimpleNamespace(shipment=s, vendor_order_id=vo.id if vo else s.order_id))
    # Ready to ship: QA flow (single-vendor) OR admin-approved multi-vendor (ready_to_dispatch)
    qa_orders = Order.query.filter_by(vendor_id=vendor.id, status='qa').all()
    mv_ready = Order.query.filter(
        Order.status == 'ready_to_dispatch',
        Order.id.in_(db.session.query(VendorOrder.order_id).filter_by(vendor_id=vendor.id)),
    ).all()
    seen = set()
    orders_ready = []
    for o in qa_orders + mv_ready:
        if o.id not in seen:
            seen.add(o.id)
            orders_ready.append(o)
    return render_template(
        'vendor/shipment_list.html',
        vendor=vendor,
        shipment_rows=shipment_rows,
        orders_ready=orders_ready,
    )


@vendor_bp.route('/shipment/order/<int:order_id>/ship', methods=['GET', 'POST'])
@login_required
@vendor_required
def shipment_create(order_id):
    vendor = get_vendor()
    order = Order.query.get_or_404(order_id)
    if order.vendor_id == vendor.id:
        vendor_has_order = True
    else:
        vendor_has_order = VendorOrder.query.filter_by(order_id=order.id, vendor_id=vendor.id).first() is not None
    if not vendor_has_order:
        flash('You do not have access to this order.', 'danger')
        return redirect(url_for('vendor.shipment_list'))
    if order.status == 'shipped':
        flash('Shipment already recorded for this order.', 'info')
        return redirect(url_for('vendor.shipment_list'))
    if order.status not in ('qa', 'ready_to_dispatch'):
        flash('Order not ready for shipment. Complete vendor work and wait for admin proof approval if required.', 'warning')
        return redirect(url_for('vendor.shipment_list'))
    if request.method == 'POST':
        courier_name = request.form.get('courier_name', '').strip()
        tracking_number = request.form.get('tracking_number', '').strip()
        ship = Shipment(order_id=order.id, courier_name=courier_name, tracking_number=tracking_number, status='dispatched')
        from datetime import datetime
        ship.shipped_at = datetime.utcnow()
        db.session.add(ship)
        order.status = 'shipped'
        db.session.commit()
        try:
            from app.services.notification_service import notify_order_status
            notify_order_status(order, 'shipped')
        except Exception as _e:
            print('notify shipped skipped:', _e)
        flash('Shipment recorded.', 'success')
        return redirect(url_for('vendor.shipment_list'))
    return render_template('vendor/shipment_form.html', vendor=vendor, order=order)


# ---------- Earnings ----------
@vendor_bp.route('/earnings')
@login_required
@vendor_required
def earnings():
    vendor = get_vendor()
    # Multi-vendor orders: this vendor's earnings live on VendorOrder rows, not Order/Payment
    # (Order.vendor_id is NULL for multi-vendor orders — same reasoning as dashboard() above).
    vendor_orders = VendorOrder.query.filter_by(vendor_id=vendor.id).order_by(VendorOrder.created_at.desc()).all()
    total = sum(float(vo.total_amount or 0) for vo in vendor_orders if vo.status == 'completed')
    return render_template('vendor/earnings.html', vendor=vendor, payments=vendor_orders, total_earnings=total)
