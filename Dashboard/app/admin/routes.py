# Admin Panel Routes - GenSpark
import secrets
import string
from datetime import datetime
from types import SimpleNamespace
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from functools import wraps
from app.admin import admin_bp
from app import db
from app.models import (
    User, Role, Vendor, VendorDocument, VendorRating,
    Component, ComponentCategory, ComponentBrand, VendorComponent,
    PcBuild, BuildComponent, Order, OrderItem, Payment, Shipment,
    AssemblyTracking, QaCheck, Notification, VendorOrder, VendorOrderItem, OrderStatusHistory,
    Rider, DeliveryAssignment
)
from app.models.order import sync_master_order_status_from_vendor_orders
from app.utils.dispatch import auto_assign_rider_for_order
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError, ProgrammingError


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


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    total_vendors = Vendor.query.count()
    total_orders = Order.query.count()
    total_components = Component.query.count()
    total_builds = PcBuild.query.count()
    revenue = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(
        Order.status.in_(['shipped', 'delivered'])
    ).scalar() or 0
    pending_orders = Order.query.filter_by(status='pending').count()
    approved_vendors = Vendor.query.filter_by(approval_status='approved').count()
    pending_vendor_count = Vendor.query.filter(Vendor.approval_status != 'approved').count()
    # Defensive: keep the dashboard alive even if the riders table isn't migrated yet.
    try:
        total_riders = Rider.query.count()
    except Exception:
        db.session.rollback()
        total_riders = 0
    try:
        pending_rider_pickups = DeliveryAssignment.query.filter_by(status='pickup_requested').count()
    except Exception:
        db.session.rollback()
        pending_rider_pickups = 0
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    return render_template('admin/dashboard.html',
        total_users=total_users, total_vendors=total_vendors,
        total_orders=total_orders, total_components=total_components,
        total_builds=total_builds, revenue=revenue,
        pending_orders=pending_orders, approved_vendors=approved_vendors,
        total_riders=total_riders,
        pending_vendor_count=pending_vendor_count,
        pending_rider_pickups=pending_rider_pickups,
        recent_orders=recent_orders,
    )


# ---------- Users ----------
@admin_bp.route('/users')
@login_required
@admin_required
def users_list():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users_list.html', users=users)


@admin_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def user_toggle_status(user_id):
    user = User.query.get_or_404(user_id)
    user.status = 'blocked' if user.status == 'active' else 'active'
    db.session.commit()
    flash(f'User {user.email} status updated.', 'success')
    return redirect(url_for('admin.users_list'))


def _generate_one_time_password():
    return secrets.token_urlsafe(8)


def _next_order_number(prefix='ORD'):
    return f'{prefix}-{datetime.utcnow().strftime("%Y%m%d%H%M%S%f")}'


@admin_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def user_add():
    """Admin add new user – auto one-time password; user must change on first login."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = (request.form.get('email') or '').strip().lower()
        role_name = request.form.get('role', 'customer').strip() or 'customer'
        if not name or not email:
            flash('Name and email are required.', 'danger')
            return redirect(url_for('admin.user_add'))
        if User.query.filter_by(email=email).first():
            flash(f'User with email {email} already exists.', 'danger')
            return redirect(url_for('admin.user_add'))
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            flash(f'Role "{role_name}" not found. Run init_db.py.', 'danger')
            return redirect(url_for('admin.user_add'))
        one_time_password = _generate_one_time_password()
        user = User(name=name, email=email, role_id=role.id, must_change_password=True)
        user.set_password(one_time_password)
        db.session.add(user)
        db.session.commit()
        email_sent = False
        try:
            from app.utils.email_helper import send_one_time_password_email
            email_sent = send_one_time_password_email(email, name, one_time_password, role_type='user')
        except Exception as e:
            from flask import current_app
            current_app.logger.exception(f'One-time password email failed: {e}')
        if email_sent:
            flash(
                f'User {email} added as {role_name}. One-time password email bhej di gayi (MailHog: http://localhost:8025). User must change password on first login.',
                'success'
            )
        else:
            flash(
                f'User {email} added as {role_name}. One-time password: {one_time_password} – email nahi bheji (MailHog check karo / .env MAIL_SERVER=localhost). User must change it on first login.',
                'warning'
            )
        return redirect(url_for('admin.users_list'))
    roles = Role.query.order_by(Role.name).all()
    return render_template('admin/user_form.html', roles=roles)


# ---------- Vendors ----------
@admin_bp.route('/vendors')
@login_required
@admin_required
def vendors_list():
    vendors = Vendor.query.order_by(Vendor.created_at.desc()).all()
    return render_template('admin/vendors_list.html', vendors=vendors)


@admin_bp.route('/vendors/<int:vendor_id>/approve', methods=['POST'])
@login_required
@admin_required
def vendor_approve(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)
    vendor.approval_status = 'approved'
    db.session.commit()
    try:
        from app.utils.email_helper import send_vendor_approval_email
        send_vendor_approval_email(vendor)
    except Exception:
        pass
    flash(f'Vendor {vendor.shop_name} approved.', 'success')
    return redirect(url_for('admin.vendors_list'))


@admin_bp.route('/vendors/<int:vendor_id>/block', methods=['POST'])
@login_required
@admin_required
def vendor_block(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)
    vendor.approval_status = 'blocked'
    db.session.commit()
    flash(f'Vendor {vendor.shop_name} blocked.', 'success')
    return redirect(url_for('admin.vendors_list'))


@admin_bp.route('/vendors/add', methods=['GET', 'POST'])
@login_required
@admin_required
def vendor_add():
    """Admin add new vendor – auto one-time password; vendor must change on first login."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = (request.form.get('email') or '').strip().lower()
        shop_name = request.form.get('shop_name', '').strip()
        city = request.form.get('city', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()
        approval_status = request.form.get('approval_status', 'approved').strip() or 'approved'
        if not name or not email or not shop_name:
            flash('Name, email and shop name are required.', 'danger')
            return redirect(url_for('admin.vendor_add'))
        if User.query.filter_by(email=email).first():
            flash(f'User with email {email} already exists.', 'danger')
            return redirect(url_for('admin.vendor_add'))
        vendor_role = Role.query.filter_by(name='vendor').first()
        if not vendor_role:
            flash('Vendor role not found. Run init_db.py.', 'danger')
            return redirect(url_for('admin.vendor_add'))
        one_time_password = _generate_one_time_password()
        user = User(name=name, email=email, role_id=vendor_role.id, must_change_password=True)
        user.set_password(one_time_password)
        db.session.add(user)
        db.session.flush()
        vendor = Vendor(
            user_id=user.id,
            shop_name=shop_name,
            city=city or None,
            address=address or None,
            phone=phone or None,
            approval_status=approval_status
        )
        db.session.add(vendor)
        db.session.commit()
        email_sent = False
        try:
            from app.utils.email_helper import send_one_time_password_email
            email_sent = send_one_time_password_email(email, name, one_time_password, role_type='vendor')
        except Exception as e:
            from flask import current_app
            current_app.logger.exception(f'One-time password email failed: {e}')
        if email_sent:
            flash(
                f'Vendor "{shop_name}" added. One-time password email bhej di gayi (MailHog: http://localhost:8025). Vendor must change password on first login.',
                'success'
            )
        else:
            flash(
                f'Vendor "{shop_name}" added. One-time password: {one_time_password} – email nahi bheji (MailHog check karo / .env MAIL_SERVER=localhost). Vendor must change it on first login.',
                'warning'
            )
        return redirect(url_for('admin.vendors_list'))
    return render_template('admin/vendor_form.html')


# ---------- Components & Categories ----------
@admin_bp.route('/categories')
@login_required
@admin_required
def categories_list():
    categories = ComponentCategory.query.all()
    return render_template('admin/categories_list.html', categories=categories)


@admin_bp.route('/categories/add', methods=['GET', 'POST'])
@login_required
@admin_required
def category_add():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        slug = request.form.get('slug', '').strip() or name.lower().replace(' ', '_')
        if name:
            c = ComponentCategory(name=name, slug=slug)
            db.session.add(c)
            db.session.commit()
            flash('Category added.', 'success')
            return redirect(url_for('admin.categories_list'))
    return render_template('admin/category_form.html', category=None)


@admin_bp.route('/categories/<int:category_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def category_edit(category_id):
    category = ComponentCategory.query.get_or_404(category_id)
    if request.method == 'POST':
        category.name = request.form.get('name', category.name)
        category.slug = request.form.get('slug', '').strip() or category.name.lower().replace(' ', '_')
        db.session.commit()
        flash('Category updated.', 'success')
        return redirect(url_for('admin.categories_list'))
    return render_template('admin/category_form.html', category=category)


# ---------- Brands ----------
@admin_bp.route('/brands')
@login_required
@admin_required
def brands_list():
    brands = ComponentBrand.query.order_by(ComponentBrand.name).all()
    return render_template('admin/brands_list.html', brands=brands)


@admin_bp.route('/brands/add', methods=['GET', 'POST'])
@login_required
@admin_required
def brand_add():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            b = ComponentBrand(name=name)
            db.session.add(b)
            db.session.commit()
            flash('Brand added.', 'success')
            return redirect(url_for('admin.brands_list'))
    return render_template('admin/brand_form.html', brand=None)


@admin_bp.route('/brands/<int:brand_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def brand_edit(brand_id):
    brand = ComponentBrand.query.get_or_404(brand_id)
    if request.method == 'POST':
        brand.name = request.form.get('name', brand.name).strip()
        if brand.name:
            db.session.commit()
            flash('Brand updated.', 'success')
            return redirect(url_for('admin.brands_list'))
    return render_template('admin/brand_form.html', brand=brand)


@admin_bp.route('/components')
@login_required
@admin_required
def components_list():
    brand_id = request.args.get('brand_id', type=int)
    query = Component.query.order_by(Component.name)
    if brand_id is not None:
        query = query.filter(Component.brand_id == brand_id)
    components = query.all()
    brands = _get_brands_for_dropdown()
    return render_template('admin/components_list.html', components=components, brands=brands, selected_brand_id=brand_id)


@admin_bp.route('/components/add', methods=['GET', 'POST'])
@login_required
@admin_required
def component_add():
    from app.utils.component_media import save_component_image

    categories = ComponentCategory.query.all()
    brands = _get_brands_for_dropdown()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id', type=int)
        raw_brand = request.form.get('brand_id', '').strip()
        brand_id = int(raw_brand) if raw_brand else None
        price = request.form.get('price', type=float) or 0
        stock = request.form.get('stock', type=int) or 0
        description = request.form.get('description', '')
        if name and category_id is not None:
            try:
                c = Component(name=name, category_id=category_id, brand_id=brand_id, price=price, stock=stock, description=description)
                db.session.add(c)
                db.session.flush()
                image_file = request.files.get('image')
                if image_file and image_file.filename:
                    url = save_component_image(image_file, c.id)
                    if url:
                        c.image_url = url
                db.session.commit()
                flash('Component added.', 'success')
                return redirect(url_for('admin.components_list'))
            except (IntegrityError, ProgrammingError) as e:
                db.session.rollback()
                msg = str(e.orig) if getattr(e, 'orig', None) else str(e)
                if 'brand_id' in msg or 'Unknown column' in msg or 'doesn\'t exist' in msg:
                    flash('Database error: components table needs brand_id column. Run: ALTER TABLE components ADD COLUMN brand_id INT NULL, ADD CONSTRAINT fk_comp_brand FOREIGN KEY (brand_id) REFERENCES brands(brand_id);', 'danger')
                else:
                    flash(f'Database error: {msg[:200]}', 'danger')
            except Exception as e:
                db.session.rollback()
                flash(f'Error saving component: {str(e)[:200]}', 'danger')
        return render_template('admin/component_form.html', component=None, categories=categories, brands=brands)
    return render_template('admin/component_form.html', component=None, categories=categories, brands=brands)


@admin_bp.route('/components/<int:component_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def component_edit(component_id):
    from app.utils.component_media import save_component_image

    component = Component.query.get_or_404(component_id)
    categories = ComponentCategory.query.all()
    brands = _get_brands_for_dropdown()
    if request.method == 'POST':
        component.name = request.form.get('name', component.name)
        component.category_id = request.form.get('category_id', type=int) or component.category_id
        raw_brand = request.form.get('brand_id', '').strip()
        component.brand_id = int(raw_brand) if raw_brand else None
        component.price = request.form.get('price', type=float) or 0
        component.stock = request.form.get('stock', type=int) or 0
        component.description = request.form.get('description', '')
        image_file = request.files.get('image')
        if image_file and image_file.filename:
            url = save_component_image(image_file, component.id)
            if url:
                component.image_url = url
        try:
            db.session.commit()
            flash('Component updated.', 'success')
            return redirect(url_for('admin.components_list'))
        except (IntegrityError, ProgrammingError) as e:
            db.session.rollback()
            msg = str(e.orig) if getattr(e, 'orig', None) else str(e)
            if 'brand_id' in msg or 'Unknown column' in msg:
                flash('Database error: components table needs brand_id column. Run the ALTER TABLE command in MySQL (see flash message from Add Component).', 'danger')
            else:
                flash(f'Database error: {msg[:200]}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving: {str(e)[:200]}', 'danger')
    return render_template('admin/component_form.html', component=component, categories=categories, brands=brands)


# ---------- PC Builds ----------
@admin_bp.route('/builds')
@login_required
@admin_required
def builds_list():
    builds = PcBuild.query.order_by(PcBuild.created_at.desc()).all()
    return render_template('admin/builds_list.html', builds=builds)


@admin_bp.route('/builds/add', methods=['GET', 'POST'])
@login_required
@admin_required
def build_add():
    components = Component.query.all()
    categories = ComponentCategory.query.all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        build_type = request.form.get('build_type', '')
        description = request.form.get('description', '')
        if name:
            build = PcBuild(name=name, build_type=build_type, description=description, total_price=0)
            db.session.add(build)
            db.session.flush()
            total = 0
            comp_ids = request.form.getlist('component_id')
            qty_list = request.form.getlist('quantity')
            for i, cid in enumerate(comp_ids):
                if cid and int(cid) > 0:
                    qty = int(qty_list[i]) if i < len(qty_list) else 1
                    comp = Component.query.get(int(cid))
                    if comp:
                        bc = BuildComponent(pc_build_id=build.id, component_id=comp.id, quantity=qty)
                        db.session.add(bc)
                        total += float(comp.price or 0) * qty
            build.total_price = total
            db.session.commit()
            flash('Build added.', 'success')
            return redirect(url_for('admin.builds_list'))
    return render_template('admin/build_form.html', build=None, components=components, categories=categories)


@admin_bp.route('/builds/<int:build_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def build_edit(build_id):
    build = PcBuild.query.get_or_404(build_id)
    components = Component.query.all()
    categories = ComponentCategory.query.all()
    if request.method == 'POST':
        build.name = request.form.get('name', build.name)
        build.build_type = request.form.get('build_type', build.build_type)
        build.description = request.form.get('description', build.description)
        BuildComponent.query.filter_by(pc_build_id=build.id).delete()
        total = 0
        comp_ids = request.form.getlist('component_id')
        qty_list = request.form.getlist('quantity')
        for i, cid in enumerate(comp_ids):
            if cid and int(cid) > 0:
                qty = int(qty_list[i]) if i < len(qty_list) else 1
                comp = Component.query.get(int(cid))
                if comp:
                    bc = BuildComponent(pc_build_id=build.id, component_id=comp.id, quantity=qty)
                    db.session.add(bc)
                    total += float(comp.price or 0) * qty
        build.total_price = total
        db.session.commit()
        flash('Build updated.', 'success')
        return redirect(url_for('admin.builds_list'))
    return render_template('admin/build_form.html', build=build, components=components, categories=categories)


# ---------- Orders ----------
@admin_bp.route('/orders')
@login_required
@admin_required
def orders_list():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    # Same statuses as order_detail / API: customer checkouts are usually `pending` first
    orders_pending_approval = [o for o in orders if (o.status or '') in ('pending', 'admin-review')]
    return render_template(
        'admin/orders_list.html',
        orders=orders,
        orders_pending_approval=orders_pending_approval,
    )


@admin_bp.route('/orders/<int:order_id>')
@login_required
@admin_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    vendor_map = {}
    for it in order.items:
        if it.vendor_id and it.vendor_id not in vendor_map:
            v = Vendor.query.get(it.vendor_id)
            vendor_map[it.vendor_id] = v.shop_name if v else '—'
    vendor_orders = VendorOrder.query.filter_by(order_id=order.id).order_by(VendorOrder.id.asc()).all()
    vo_rows = []
    for vo in vendor_orders:
        v = Vendor.query.get(vo.vendor_id)
        vo_rows.append(SimpleNamespace(
            id=vo.id,
            shop_name=v.shop_name if v else '—',
            status=vo.status,
            proof_image_url=vo.proof_image_url,
            proof_approved=bool(getattr(vo, 'proof_approved', True)),
        ))
    items_subtotal = sum(float((it.total_price or 0)) for it in order.items)
    shipping_fee = float(getattr(order, 'shipping_fee', 0) or 0)
    return render_template(
        'admin/order_detail.html',
        order=order,
        vendor_map=vendor_map,
        vendor_orders=vo_rows,
        items_subtotal=items_subtotal,
        shipping_fee=shipping_fee,
    )


@admin_bp.route('/orders/<int:order_id>/vendor-orders/<int:vendor_order_id>/approve-proof', methods=['POST'])
@login_required
@admin_required
def admin_approve_vendor_proof(order_id, vendor_order_id):
    vo = VendorOrder.query.filter_by(id=vendor_order_id, order_id=order_id).first_or_404()
    if not vo.proof_image_url:
        flash('No proof image on this vendor order.', 'warning')
        return redirect(request.referrer or url_for('admin.order_detail', order_id=order_id))
    vo.proof_approved = True
    db.session.add(OrderStatusHistory(
        order_id=order_id,
        status='processing',
        notes=f'Admin approved completion proof (vendor order #{vo.id})',
    ))
    sync_master_order_status_from_vendor_orders(order_id)
    db.session.commit()

    # Auto-Assignment Bridge: the moment the order is ready to dispatch, hand it
    # to the best available rider (idempotent — safe if already assigned).
    order = Order.query.get(order_id)
    msg = 'Proof approved. Vendor can now dispatch this order from Shipment.'
    if order and order.status == 'ready_to_dispatch':
        try:
            from app.services.notification_service import notify_order_ready_to_dispatch
            notify_order_ready_to_dispatch(order)
        except Exception as _e:
            print('notify ready_to_dispatch skipped:', _e)
        result = auto_assign_rider_for_order(order)
        if result.get('created'):
            r = result['rider']
            msg += f' Auto-assigned to {r.display_code} ({r.user.name if r.user else "rider"}).'
    flash(msg, 'success')
    return redirect(url_for('admin.order_detail', order_id=order_id))


@admin_bp.route('/orders/<int:order_id>/ready-for-dispatch', methods=['POST'])
@login_required
@admin_required
def mark_ready_for_dispatch(order_id):
    """Explicit 'Ready for Dispatch' action — flips the order and fires the
    Auto-Assignment Bridge so a rider is selected with zero manual steps."""
    order = Order.query.get_or_404(order_id)

    # Idempotent: a repeated click (or a double-submit) must not add a second
    # timeline entry or re-notify the customer. Still (safely) re-run the
    # rider auto-assignment in case the first pass found no rider.
    if order.status in ('ready_to_dispatch', 'shipped', 'delivered', 'completed'):
        result = auto_assign_rider_for_order(order)
        if result.get('created'):
            r = result['rider']
            flash(
                f'Order was already ready — auto-assigned to {r.display_code} '
                f'({r.user.name if r.user else "rider"}).',
                'success',
            )
        else:
            flash('Order is already marked ready for dispatch.', 'info')
        return redirect(request.referrer or url_for('admin.order_detail', order_id=order_id))

    order.status = 'ready_to_dispatch'
    db.session.add(OrderStatusHistory(
        order_id=order.id,
        status='ready_to_dispatch',
        notes='Admin marked order ready for dispatch.',
    ))
    db.session.commit()

    # Notify the customer that their order is ready for dispatch.
    try:
        from app.services.notification_service import notify_order_ready_to_dispatch
        notify_order_ready_to_dispatch(order)
    except Exception as _e:
        print('notify ready_to_dispatch skipped:', _e)

    result = auto_assign_rider_for_order(order)
    if result.get('created'):
        r = result['rider']
        flash(
            f'Order ready for dispatch — auto-assigned to {r.display_code} '
            f'({r.user.name if r.user else "rider"}), '
            f'{result["distance_km"]} km, workload {result["workload"]}.',
            'success',
        )
    elif result.get('reason') == 'already_assigned':
        flash('Order is ready for dispatch (a rider was already assigned).', 'info')
    elif result.get('reason') == 'no_rider':
        flash('Order marked ready, but no rider is available to auto-assign.', 'warning')
    else:
        flash('Order marked ready for dispatch.', 'success')
    return redirect(request.referrer or url_for('admin.order_detail', order_id=order_id))


@admin_bp.route('/orders/<int:order_id>/approve-generate', methods=['POST'])
@login_required
@admin_required
def order_approve_generate(order_id):
    parent = Order.query.get_or_404(order_id)

    if parent.status in ('approved', 'processing', 'completed', 'rejected', 'ready_to_dispatch', 'shipped', 'delivered'):
        flash('This order cannot be approved in its current state.', 'info')
        return redirect(request.referrer or url_for('admin.order_detail', order_id=order_id))

    parent_items = parent.items.all()
    if not parent_items:
        flash('Order has no items.', 'warning')
        return redirect(request.referrer or url_for('admin.order_detail', order_id=order_id))

    vendor_buckets = {}
    unassigned = []
    for it in parent_items:
        qty = int(it.quantity or 0)
        if qty <= 0:
            continue
        if not it.vendor_id:
            unassigned.append(it.id)
            continue
        vendor_buckets.setdefault(it.vendor_id, []).append(it)

    if unassigned:
        flash(f'Cannot approve. Some order items have no vendor assignment: {", ".join(str(i) for i in unassigned)}', 'warning')
        return redirect(request.referrer or url_for('admin.order_detail', order_id=order_id))

    generated_count = 0
    created_vendor_orders = []
    for vendor_id, order_items in vendor_buckets.items():
        v_order = VendorOrder(
            order_id=parent.id,
            vendor_id=vendor_id,
            status='assigned',
            total_amount=0,
        )
        db.session.add(v_order)
        db.session.flush()
        created_vendor_orders.append(v_order)

        subtotal = 0.0
        for oi in order_items:
            qty = int(oi.quantity or 0)
            unit_price = float(oi.unit_price or 0)
            line_total = unit_price * qty
            subtotal += line_total
            db.session.add(VendorOrderItem(
                vendor_order_id=v_order.id,
                component_id=oi.item_id,
                component_name=oi.component_name,
                quantity=qty,
                unit_price=unit_price,
                total_price=line_total,
            ))
            inv = VendorComponent.query.filter_by(vendor_id=vendor_id, component_id=oi.item_id).first()
            if inv:
                inv.quantity = max(0, int(inv.quantity or 0) - qty)
        v_order.total_amount = subtotal
        generated_count += 1

    parent.status = 'processing'
    db.session.add(OrderStatusHistory(order_id=parent.id, status='approved', notes='Approved by admin'))
    db.session.add(OrderStatusHistory(order_id=parent.id, status='processing', notes='Vendor orders assigned'))
    db.session.commit()

    if generated_count > 0:
        # Live customer notification (in-app bell + Socket.IO toast).
        try:
            from app.services.notification_service import notify_order_status, notify_vendor_order_assigned
            notify_order_status(parent, 'approved')
            # Notify each assigned vendor (the previously-missing vendor-facing alert).
            for vo in created_vendor_orders:
                notify_vendor_order_assigned(vo)
        except Exception as _e:
            print('notify approved skipped:', _e)
        flash(f'Approved. {generated_count} vendor order(s) generated.', 'success')
    return redirect(request.referrer or url_for('admin.order_detail', order_id=order_id))


@admin_bp.route('/orders/<int:order_id>/reject', methods=['POST'])
@login_required
@admin_required
def order_reject(order_id):
    parent = Order.query.get_or_404(order_id)
    if parent.status in ('processing', 'completed', 'rejected'):
        flash('Order cannot be rejected now.', 'warning')
        return redirect(request.referrer or url_for('admin.order_detail', order_id=order_id))
    if VendorOrder.query.filter_by(order_id=parent.id).first():
        flash('Vendor orders already exist for this order.', 'warning')
        return redirect(request.referrer or url_for('admin.order_detail', order_id=order_id))
    reason = (request.form.get('reason') or '').strip()
    parent.status = 'rejected'
    parent.notes = (parent.notes or '') + ('\nadmin_reject_reason=' + reason if reason else '\nadmin_reject')
    db.session.add(OrderStatusHistory(
        order_id=parent.id,
        status='rejected',
        notes=reason or 'Order rejected by admin',
    ))
    db.session.commit()
    try:
        from app.services.notification_service import notify_order_status
        notify_order_status(parent, 'rejected')
    except Exception as _e:
        print('notify rejected skipped:', _e)
    flash('Order rejected.', 'success')
    return redirect(request.referrer or url_for('admin.order_detail', order_id=order_id))


# ---------- QA ----------
@admin_bp.route('/qa')
@login_required
@admin_required
def qa_list():
    orders_qa = Order.query.filter(Order.status.in_(['assembly', 'qa'])).order_by(Order.updated_at.desc()).all()
    return render_template('admin/qa_list.html', orders=orders_qa)


@admin_bp.route('/qa/order/<int:order_id>/pass', methods=['POST'])
@login_required
@admin_required
def qa_pass(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = 'shipped'
    qa = QaCheck(order_id=order.id, result='pass', checked_by=current_user.id)
    db.session.add(qa)
    db.session.commit()
    try:
        from app.services.notification_service import notify_order_status
        notify_order_status(order, 'shipped')
    except Exception as _e:
        print('notify shipped skipped:', _e)
    flash('QA passed. Order marked for shipment.', 'success')
    return redirect(url_for('admin.qa_list'))


@admin_bp.route('/qa/order/<int:order_id>/fail', methods=['POST'])
@login_required
@admin_required
def qa_fail(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = 'assembly'
    qa = QaCheck(order_id=order.id, result='fail', notes=request.form.get('notes'), checked_by=current_user.id)
    db.session.add(qa)
    db.session.commit()
    try:
        from app.services.notification_service import notify_order_status
        notify_order_status(order, 'assembly')
    except Exception as _e:
        print('notify assembly skipped:', _e)
    flash('QA failed. Sent back to assembly.', 'warning')
    return redirect(url_for('admin.qa_list'))


# ---------- Payments ----------
@admin_bp.route('/payments')
@login_required
@admin_required
def payments_list():
    payments = Payment.query.order_by(Payment.created_at.desc()).all()
    return render_template('admin/payments_list.html', payments=payments)


# ---------- Reports / Analytics ----------
@admin_bp.route('/reports')
@login_required
@admin_required
def reports():
    from sqlalchemy import func
    total_revenue = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(
        Order.status.in_(['shipped', 'delivered'])
    ).scalar() or 0
    orders_by_status = db.session.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    top_vendors = db.session.query(Vendor.shop_name, func.count(Order.id).label('cnt')).join(
        Order, Order.vendor_id == Vendor.id
    ).group_by(Vendor.id).order_by(func.count(Order.id).desc()).limit(10).all()
    return render_template('admin/reports.html',
        total_revenue=total_revenue,
        orders_by_status=orders_by_status,
        top_vendors=top_vendors
    )


# ---------- Rider pickup approvals (Admin-Led Verification flow) ----------
@admin_bp.route('/rider-approvals')
@login_required
@admin_required
def rider_approvals():
    pending = DeliveryAssignment.query.filter_by(status='pickup_requested').order_by(
        DeliveryAssignment.pickup_requested_at.asc()
    ).all()
    recent = DeliveryAssignment.query.filter(
        DeliveryAssignment.status.in_(['approved', 'in_transit', 'delivered', 'rejected'])
    ).order_by(DeliveryAssignment.updated_at.desc()).limit(20).all()
    return render_template('admin/rider_approvals.html', pending=pending, recent=recent)


# ---------- Live rider map (Leaflet monitoring view) ----------
@admin_bp.route('/live-map')
@login_required
@admin_required
def live_map():
    active = DeliveryAssignment.query.filter(
        DeliveryAssignment.tracking_active.is_(True),
        DeliveryAssignment.status != 'delivered',
    ).count()
    return render_template('admin/live_map.html', active_count=active)


@admin_bp.route('/rider-approvals/<int:delivery_id>/approve', methods=['POST'])
@login_required
@admin_required
def rider_pickup_approve(delivery_id):
    job = DeliveryAssignment.query.get_or_404(delivery_id)
    if job.status != 'pickup_requested':
        flash('This delivery is not awaiting approval.', 'warning')
        return redirect(url_for('admin.rider_approvals'))
    job.status = 'approved'
    job.approved_at = datetime.utcnow()
    db.session.commit()
    flash(f'Pickup approved for {job.order_code}.', 'success')
    return redirect(url_for('admin.rider_approvals'))


@admin_bp.route('/rider-approvals/<int:delivery_id>/reject', methods=['POST'])
@login_required
@admin_required
def rider_pickup_reject(delivery_id):
    job = DeliveryAssignment.query.get_or_404(delivery_id)
    if job.status != 'pickup_requested':
        flash('This delivery is not awaiting approval.', 'warning')
        return redirect(url_for('admin.rider_approvals'))
    job.status = 'rejected'
    db.session.commit()
    flash(f'Pickup request for {job.order_code} rejected.', 'info')
    return redirect(url_for('admin.rider_approvals'))
