"""
Rider live-tracking API (Leaflet map integration).

Endpoints (registered on /api):
  POST /api/rider/location/update        rider pushes a real GPS fix
  POST /api/rider/tracking/start         rider starts tracking (sim or gps mode)
  POST /api/rider/tracking/stop          rider stops sharing location
  GET  /api/rider/location/<order_id>    customer/public live position + ETA
  GET  /api/tracking/<delivery_id>       alias by delivery id
  GET  /api/riders/active-locations      admin: all active riders on the map

Auth: rider write-endpoints require a logged-in rider that OWNS the delivery
(session or Bearer JWT — bridged in app.api.before_request). The read endpoint
is public so a customer can open a tracking link.
"""
from datetime import datetime

from flask import jsonify, request
from flask_login import current_user

from app import db
from app.api import api_bp
from app.models import Rider, DeliveryAssignment, RiderLocationPing, Order

# Demo defaults (Lahore) used when a delivery has no geocoded pickup/dropoff yet.
DEFAULT_PICKUP = (31.5204, 74.3587)    # Lahore city centre
DEFAULT_DROPOFF = (31.4697, 74.4089)   # DHA Lahore
_TRACKABLE_STATUSES = ('approved', 'in_transit')


def _current_rider():
    if not current_user.is_authenticated or not getattr(current_user, 'is_rider', False):
        return None
    return Rider.query.filter_by(user_id=current_user.id).first()


def _valid_coord(lat, lng):
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return None
    return lat, lng


def _resolve_delivery(ident):
    """Find a delivery by its linked order_id first, else by its own id."""
    job = DeliveryAssignment.query.filter_by(order_id=ident).first()
    if job:
        return job
    return DeliveryAssignment.query.get(ident)


def _can_view_tracking(job):
    """Who may read a delivery's live position.

    A logged-in owner (the customer who placed the order), the assigned rider, or an
    admin can always view it. An anonymous public tracking-link viewer may only see a
    delivery that is actively out for delivery — this keeps shareable links working
    while stopping ID-enumeration from harvesting arbitrary orders' GPS/locations.
    """
    if current_user.is_authenticated:
        if getattr(current_user, 'is_admin', False):
            return True
        if getattr(current_user, 'is_rider', False):
            rider = Rider.query.filter_by(user_id=current_user.id).first()
            if rider and job.rider_id == rider.id:
                return True
        if job.order_id:
            order = Order.query.get(job.order_id)
            if order and order.user_id == current_user.id:
                return True
    return job.status in _TRACKABLE_STATUSES


@api_bp.route('/rider/location/update', methods=['POST', 'OPTIONS'])
def rider_location_update():
    if request.method == 'OPTIONS':
        return '', 204
    rider = _current_rider()
    if not rider:
        return jsonify({'success': False, 'error': 'Rider authentication required'}), 401

    data = request.get_json(silent=True) or {}
    ident = data.get('delivery_id') or data.get('order_id')
    coord = _valid_coord(data.get('latitude'), data.get('longitude'))
    if ident is None:
        return jsonify({'success': False, 'error': 'delivery_id (or order_id) required'}), 400
    if not coord:
        return jsonify({'success': False, 'error': 'Invalid latitude/longitude'}), 400

    job = DeliveryAssignment.query.filter_by(id=int(ident), rider_id=rider.id).first()
    if not job:
        job = DeliveryAssignment.query.filter_by(order_id=int(ident), rider_id=rider.id).first()
    if not job:
        return jsonify({'success': False, 'error': 'Delivery not found for this rider'}), 404

    lat, lng = coord
    speed = data.get('speed')
    try:
        speed = float(speed) if speed is not None else None
    except (TypeError, ValueError):
        speed = None

    job.current_lat = lat
    job.current_lng = lng
    job.current_speed = speed
    job.location_updated_at = datetime.utcnow()
    job.tracking_active = True
    job.sim_mode = False
    if job.pickup_lat is None:
        job.pickup_lat, job.pickup_lng = lat, lng  # first fix = pickup origin

    db.session.add(RiderLocationPing(
        delivery_id=job.id, rider_id=rider.id,
        latitude=lat, longitude=lng, speed=speed,
    ))
    db.session.commit()
    return jsonify({'success': True, 'tracking': job.tracking_snapshot()}), 200


@api_bp.route('/rider/tracking/start', methods=['POST', 'OPTIONS'])
def rider_tracking_start():
    if request.method == 'OPTIONS':
        return '', 204
    rider = _current_rider()
    if not rider:
        return jsonify({'success': False, 'error': 'Rider authentication required'}), 401

    data = request.get_json(silent=True) or {}
    ident = data.get('delivery_id') or data.get('order_id')
    if ident is None:
        return jsonify({'success': False, 'error': 'delivery_id required'}), 400

    job = DeliveryAssignment.query.filter_by(id=int(ident), rider_id=rider.id).first()
    if not job:
        return jsonify({'success': False, 'error': 'Delivery not found for this rider'}), 404
    if job.status not in _TRACKABLE_STATUSES:
        return jsonify({
            'success': False,
            'error': f'Tracking can start only when the delivery is approved/in-transit (current: {job.status}).',
        }), 400

    mode = (data.get('mode') or 'sim').strip().lower()

    # Pickup / dropoff coordinates (provided, existing, or demo defaults).
    pickup = _valid_coord(*(data.get('pickup') or [None, None])) if data.get('pickup') else None
    dropoff = _valid_coord(*(data.get('dropoff') or [None, None])) if data.get('dropoff') else None
    if pickup:
        job.pickup_lat, job.pickup_lng = pickup
    elif job.pickup_lat is None:
        job.pickup_lat, job.pickup_lng = DEFAULT_PICKUP
    if dropoff:
        job.dropoff_lat, job.dropoff_lng = dropoff
    elif job.dropoff_lat is None:
        # Spread demo dropoffs a little per delivery so multiple riders differ.
        off = (job.id % 10) * 0.004
        job.dropoff_lat = DEFAULT_DROPOFF[0] + off
        job.dropoff_lng = DEFAULT_DROPOFF[1] - off

    job.tracking_active = True
    if job.status == 'approved':
        job.status = 'in_transit'

    if mode == 'gps':
        job.sim_mode = False
    else:
        job.sim_mode = True
        job.sim_started_at = datetime.utcnow()
        try:
            job.sim_duration_s = int(data.get('duration_s') or 180)
        except (TypeError, ValueError):
            job.sim_duration_s = 180
        job.current_lat, job.current_lng = job.pickup_lat, job.pickup_lng

    job.location_updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'tracking': job.tracking_snapshot()}), 200


@api_bp.route('/rider/tracking/stop', methods=['POST', 'OPTIONS'])
def rider_tracking_stop():
    if request.method == 'OPTIONS':
        return '', 204
    rider = _current_rider()
    if not rider:
        return jsonify({'success': False, 'error': 'Rider authentication required'}), 401

    data = request.get_json(silent=True) or {}
    ident = data.get('delivery_id') or data.get('order_id')
    job = DeliveryAssignment.query.filter_by(id=int(ident or 0), rider_id=rider.id).first()
    if not job:
        return jsonify({'success': False, 'error': 'Delivery not found for this rider'}), 404
    job.tracking_active = False
    db.session.commit()
    return jsonify({'success': True, 'tracking': job.tracking_snapshot()}), 200


@api_bp.route('/rider/location/<int:order_id>', methods=['GET'])
def get_live_location(order_id):
    """Customer view — live position + status + ETA for an order. Visible to the
    order owner / assigned rider / admin, or to anyone while it is out for delivery."""
    job = _resolve_delivery(order_id)
    if not job:
        return jsonify({'success': False, 'error': 'No delivery found for this order'}), 404
    if not _can_view_tracking(job):
        return jsonify({'success': False, 'error': 'Not authorized to view this delivery'}), 403
    return jsonify({'success': True, 'tracking': job.tracking_snapshot()}), 200


@api_bp.route('/tracking/<int:delivery_id>', methods=['GET'])
def get_tracking_by_delivery(delivery_id):
    job = DeliveryAssignment.query.get(delivery_id)
    if not job:
        return jsonify({'success': False, 'error': 'Delivery not found'}), 404
    if not _can_view_tracking(job):
        return jsonify({'success': False, 'error': 'Not authorized to view this delivery'}), 403
    return jsonify({'success': True, 'tracking': job.tracking_snapshot()}), 200


@api_bp.route('/riders/active-locations', methods=['GET'])
def admin_active_locations():
    """Admin monitoring view — every rider currently sharing location."""
    if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
        return jsonify({'success': False, 'error': 'Admin access required'}), 403

    jobs = (
        DeliveryAssignment.query
        .filter(DeliveryAssignment.tracking_active.is_(True))
        .filter(DeliveryAssignment.status != 'delivered')
        .all()
    )
    out = []
    for job in jobs:
        snap = job.tracking_snapshot()
        if snap['latitude'] is None:
            continue
        rider = Rider.query.get(job.rider_id)
        snap['rider'] = {
            'id': job.rider_id,
            'code': rider.display_code if rider else f'RDR-{job.rider_id:04d}',
            'name': rider.user.name if rider and rider.user else 'Rider',
            'vehicle': rider.vehicle_type if rider else None,
        }
        out.append(snap)
    return jsonify({'success': True, 'count': len(out), 'riders': out}), 200
