# Rider Panel Routes - GenSpark
from datetime import datetime
from functools import wraps

from flask import render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user, logout_user
from sqlalchemy import func

from app.rider import rider_bp
from app import db
from app.models import Rider, DeliveryAssignment

# Per-job rider payout used when crediting earnings if a row has none seeded.
DEFAULT_DELIVERY_FEE = 250

# Deliveries the rider still has to act on (the "active" panel).
ACTIVE_STATUSES = ('assigned', 'pickup_requested', 'approved', 'in_transit')


def rider_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login.', 'danger')
            return redirect(url_for('auth.login'))
        if not current_user.is_rider:
            # Don't silently bounce an admin/vendor session into the rider panel.
            logout_user()
            flash('Please login with a rider account.', 'warning')
            return redirect(url_for('auth.login'))
        rider = Rider.query.filter_by(user_id=current_user.id).first()
        if not rider:
            flash('Rider profile not found. Complete your profile.', 'warning')
            return redirect(url_for('rider.profile'))
        return f(*args, **kwargs)
    return decorated


def get_rider():
    return Rider.query.filter_by(user_id=current_user.id).first()


def _owned_delivery_or_404(rider, delivery_id):
    return DeliveryAssignment.query.filter_by(id=delivery_id, rider_id=rider.id).first_or_404()


@rider_bp.route('/')
@rider_bp.route('/dashboard')
@login_required
@rider_required
def dashboard():
    rider = get_rider()

    pending = DeliveryAssignment.query.filter(
        DeliveryAssignment.rider_id == rider.id,
        DeliveryAssignment.status.in_(ACTIVE_STATUSES),
    ).count()

    today = datetime.utcnow().date()
    completed_today = DeliveryAssignment.query.filter(
        DeliveryAssignment.rider_id == rider.id,
        DeliveryAssignment.status == 'delivered',
        func.date(DeliveryAssignment.delivered_at) == today,
    ).count()

    earnings_today = db.session.query(
        func.coalesce(func.sum(DeliveryAssignment.earning), 0)
    ).filter(
        DeliveryAssignment.rider_id == rider.id,
        DeliveryAssignment.status == 'delivered',
        func.date(DeliveryAssignment.delivered_at) == today,
    ).scalar() or 0

    active_deliveries = DeliveryAssignment.query.filter(
        DeliveryAssignment.rider_id == rider.id,
        DeliveryAssignment.status.in_(ACTIVE_STATUSES),
    ).order_by(
        # Urgent first, then newest.
        (DeliveryAssignment.priority == 'urgent').desc(),
        DeliveryAssignment.created_at.desc(),
    ).all()

    # Last 7 calendar days of earnings for the mini bar chart.
    earnings_series = _earnings_last_7_days(rider)

    return render_template(
        'rider/dashboard.html',
        rider=rider,
        pending=pending,
        completed_today=completed_today,
        earnings_today=float(earnings_today),
        active_deliveries=active_deliveries,
        earnings_series=earnings_series,
    )


def _earnings_last_7_days(rider):
    """Return [(label, amount), ...] oldest→newest for a 7-day bar chart."""
    from datetime import timedelta
    today = datetime.utcnow().date()
    rows = db.session.query(
        func.date(DeliveryAssignment.delivered_at),
        func.coalesce(func.sum(DeliveryAssignment.earning), 0),
    ).filter(
        DeliveryAssignment.rider_id == rider.id,
        DeliveryAssignment.status == 'delivered',
        DeliveryAssignment.delivered_at.isnot(None),
    ).group_by(func.date(DeliveryAssignment.delivered_at)).all()
    by_day = {str(d): float(amt) for d, amt in rows}
    series = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        series.append((day.strftime('%a'), by_day.get(str(day), 0.0)))
    return series


@rider_bp.route('/ping-active')
@login_required
@rider_required
def ping_active():
    """Lightweight JSON poll for the dashboard — lets the rider page detect a
    newly auto-assigned delivery and surface it live (no manual refresh)."""
    rider = get_rider()
    active = DeliveryAssignment.query.filter(
        DeliveryAssignment.rider_id == rider.id,
        DeliveryAssignment.status.in_(ACTIVE_STATUSES),
    ).order_by(DeliveryAssignment.created_at.desc()).all()
    latest = active[0] if active else None
    return jsonify({
        'active_count': len(active),
        'latest_code': latest.order_code if latest else None,
        'latest_pickup': latest.pickup_location if latest else None,
    })


@rider_bp.route('/deliveries')
@login_required
@rider_required
def deliveries():
    rider = get_rider()
    all_jobs = DeliveryAssignment.query.filter_by(rider_id=rider.id).order_by(
        DeliveryAssignment.created_at.desc()
    ).all()
    return render_template('rider/deliveries.html', rider=rider, deliveries=all_jobs)


@rider_bp.route('/deliveries/<int:delivery_id>/request-pickup', methods=['POST'])
@login_required
@rider_required
def request_pickup(delivery_id):
    rider = get_rider()
    job = _owned_delivery_or_404(rider, delivery_id)
    if job.status != 'assigned':
        flash('Pickup can only be requested for a newly assigned delivery.', 'warning')
        return redirect(request.referrer or url_for('rider.dashboard'))
    job.status = 'pickup_requested'
    job.pickup_requested_at = datetime.utcnow()
    db.session.commit()
    flash(f'Pickup requested for {job.order_code}. Waiting for admin approval.', 'success')
    return redirect(request.referrer or url_for('rider.dashboard'))


@rider_bp.route('/deliveries/<int:delivery_id>/start', methods=['POST'])
@login_required
@rider_required
def start_delivery(delivery_id):
    rider = get_rider()
    job = _owned_delivery_or_404(rider, delivery_id)
    if job.status != 'approved':
        flash('You can start a delivery only after admin approves the pickup.', 'warning')
        return redirect(request.referrer or url_for('rider.dashboard'))
    job.status = 'in_transit'
    db.session.commit()

    # High-priority WhatsApp + on-site: order is OUT FOR DELIVERY (rider en route).
    try:
        from app.services.notification_service import notify_out_for_delivery
        notify_out_for_delivery(job)
    except Exception as _e:
        print('notify out-for-delivery skipped:', _e)

    flash(f'{job.order_code} picked up — now in transit.', 'success')
    return redirect(request.referrer or url_for('rider.dashboard'))


@rider_bp.route('/deliveries/<int:delivery_id>/deliver', methods=['POST'])
@login_required
@rider_required
def mark_delivered(delivery_id):
    rider = get_rider()
    job = _owned_delivery_or_404(rider, delivery_id)
    if job.status != 'in_transit':
        flash('Only an in-transit delivery can be marked delivered.', 'warning')
        return redirect(request.referrer or url_for('rider.dashboard'))
    job.status = 'delivered'
    job.delivered_at = datetime.utcnow()
    job.tracking_active = False  # stop live tracking once delivered
    if not job.earning or float(job.earning) == 0:
        job.earning = DEFAULT_DELIVERY_FEE
    rider.total_completed = (rider.total_completed or 0) + 1
    db.session.commit()

    # Notify the customer (and admins) that the order was delivered.
    try:
        from app.services.notification_service import notify_delivery_delivered
        notify_delivery_delivered(job)
    except Exception as _e:
        print('notify delivered skipped:', _e)

    flash(f'{job.order_code} delivered. Earning credited.', 'success')
    return redirect(request.referrer or url_for('rider.dashboard'))


@rider_bp.route('/tracking/<int:delivery_id>')
@login_required
@rider_required
def live_tracking(delivery_id):
    rider = get_rider()
    job = _owned_delivery_or_404(rider, delivery_id)
    return render_template('rider/tracking.html', rider=rider, delivery=job)


@rider_bp.route('/availability', methods=['POST'])
@login_required
@rider_required
def toggle_availability():
    rider = get_rider()
    rider.is_online = not bool(rider.is_online)
    db.session.commit()
    flash('You are now ' + ('Online' if rider.is_online else 'Offline') + '.', 'info')
    return redirect(request.referrer or url_for('rider.dashboard'))


@rider_bp.route('/earnings')
@login_required
@rider_required
def earnings():
    rider = get_rider()
    delivered = DeliveryAssignment.query.filter_by(
        rider_id=rider.id, status='delivered'
    ).order_by(DeliveryAssignment.delivered_at.desc()).all()
    total = sum(float(d.earning or 0) for d in delivered)
    earnings_series = _earnings_last_7_days(rider)
    return render_template(
        'rider/earnings.html',
        rider=rider,
        delivered=delivered,
        total_earnings=total,
        earnings_series=earnings_series,
    )


@rider_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    # Not wrapped in rider_required so a brand-new rider can create their profile.
    if not current_user.is_rider:
        logout_user()
        flash('Please login with a rider account.', 'warning')
        return redirect(url_for('auth.login'))
    rider = get_rider()
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        city = request.form.get('city', '').strip()
        vehicle_type = request.form.get('vehicle_type', '').strip()
        vehicle_number = request.form.get('vehicle_number', '').strip()
        if rider:
            rider.phone = phone
            rider.city = city
            rider.vehicle_type = vehicle_type
            rider.vehicle_number = vehicle_number
            flash('Profile updated.', 'success')
        else:
            rider = Rider(
                user_id=current_user.id, phone=phone, city=city,
                vehicle_type=vehicle_type, vehicle_number=vehicle_number,
            )
            db.session.add(rider)
            flash('Rider profile created.', 'success')
        db.session.commit()
        return redirect(url_for('rider.dashboard'))
    return render_template('rider/profile.html', rider=rider)
