"""
Auto-Assignment Bridge + Best-Rider Scoring Engine.

When an order becomes ready for dispatch, `auto_assign_rider_for_order()` picks the
optimal rider and creates a DeliveryAssignment — turning the previously manual,
disconnected rider pipeline into an event-driven one.

Best-Rider score (higher = better) — implements the FYP priority formula
    Score = W_RATING*rating  -  W_DISTANCE*distance_km  -  W_WORKLOAD*active_jobs
i.e. favour the top-rated, nearest, least-busy ONLINE rider. (The spec wrote the
distance/workload terms as positive penalties; here they're subtracted so the
"best" rider is the maximum-score one.)
"""
from datetime import datetime

from app import db
from app.models import (
    Rider, DeliveryAssignment, Order, Vendor, VendorOrder, Notification,
)
from app.models.rider import haversine_km

# Scoring weights — rating dominates, then workload, then distance.
W_RATING = 10.0
W_DISTANCE = 0.5
W_WORKLOAD = 6.0

# Per-job rider payout = base + distance component.
BASE_FEE = 200
PER_KM_FEE = 12

# Deliveries that still occupy a rider (count toward workload).
ACTIVE_STATUSES = ('assigned', 'pickup_requested', 'approved', 'in_transit')

# Approx city centroids (lat, lng) — enough for a realistic distance ranking
# given riders/vendors only store a city string.
CITY_COORDS = {
    'lahore': (31.5204, 74.3587),
    'karachi': (24.8607, 67.0011),
    'islamabad': (33.6844, 73.0479),
    'rawalpindi': (33.5651, 73.0169),
    'gujranwala': (32.1877, 74.1945),
    'faisalabad': (31.4504, 73.1350),
    'multan': (30.1575, 71.5249),
    'peshawar': (34.0151, 71.5249),
    'sialkot': (32.4945, 74.5229),
    'hyderabad': (25.3960, 68.3578),
    'quetta': (30.1798, 66.9750),
}

DEFAULT_DISTANCE_KM = 15.0  # used when a city can't be geolocated
MIN_DISTANCE_KM = 4.0       # realistic intra-city floor (city centroids give 0 for same city)


def _coords_for_city(city):
    key = (city or '').strip().lower()
    if not key:
        return None
    if key in CITY_COORDS:
        return CITY_COORDS[key]
    # loose contains match (e.g. "DHA, Lahore")
    for name, coords in CITY_COORDS.items():
        if name in key:
            return coords
    return None


def _extract_city(text):
    """Pull a known city name out of a free-text shipping address."""
    blob = (text or '').lower()
    for name in CITY_COORDS:
        if name in blob:
            return name.title()
    return None


def _vendor_for_order(order):
    """Resolve the pickup vendor for an order (legacy vendor_id, else first VendorOrder)."""
    if getattr(order, 'vendor_id', None):
        v = Vendor.query.get(order.vendor_id)
        if v:
            return v
    vo = VendorOrder.query.filter_by(order_id=order.id).first()
    if vo:
        return Vendor.query.get(vo.vendor_id)
    return None


def rider_workload(rider):
    """Count of deliveries currently occupying this rider."""
    return DeliveryAssignment.query.filter(
        DeliveryAssignment.rider_id == rider.id,
        DeliveryAssignment.status.in_(ACTIVE_STATUSES),
    ).count()


def score_rider(rider, pickup_coords):
    """Return (score, distance_km, workload) for ranking. Higher score = better pick."""
    workload = rider_workload(rider)
    rating = float(rider.rating or 0)
    rider_coords = _coords_for_city(rider.city)
    distance = None
    if rider_coords and pickup_coords:
        distance = haversine_km(rider_coords[0], rider_coords[1], pickup_coords[0], pickup_coords[1])
    if distance is None:
        distance = DEFAULT_DISTANCE_KM
    score = (W_RATING * rating) - (W_DISTANCE * distance) - (W_WORKLOAD * workload)
    return score, round(distance, 1), workload


def pick_best_rider(pickup_coords):
    """
    Rank riders and return (rider, distance_km, workload, considered_count).
    Prefers ONLINE riders; falls back to all riders so a demo always assigns.
    """
    online = Rider.query.filter_by(is_online=True).all()
    pool = online or Rider.query.all()
    if not pool:
        return None, None, None, 0
    best, best_score, best_dist, best_load = None, None, None, None
    for rider in pool:
        score, dist, load = score_rider(rider, pickup_coords)
        if best_score is None or score > best_score:
            best, best_score, best_dist, best_load = rider, score, dist, load
    return best, best_dist, best_load, len(pool)


def auto_assign_rider_for_order(order, commit=True):
    """
    Create a DeliveryAssignment for `order` and assign the best rider.

    Idempotent: if a delivery already exists for this order, returns it unchanged.
    Returns a dict describing the outcome (never raises for "no rider"/"exists").
    """
    if order is None:
        return {'created': False, 'reason': 'no_order'}

    existing = DeliveryAssignment.query.filter_by(order_id=order.id).first()
    if existing:
        return {'created': False, 'reason': 'already_assigned', 'assignment': existing}

    # Pickup = vendor location; drop-off = customer shipping address.
    vendor = _vendor_for_order(order)
    pickup_city = (vendor.city if vendor else None) or 'Lahore'
    pickup_label = (
        f"{vendor.shop_name} ({pickup_city})" if vendor else f"GenSpark Warehouse ({pickup_city})"
    )
    pickup_coords = _coords_for_city(pickup_city) or CITY_COORDS['lahore']

    dropoff_city = _extract_city(order.shipping_address) or pickup_city
    dropoff_label = (order.shipping_address or f'Customer ({dropoff_city})').strip()
    dropoff_coords = _coords_for_city(dropoff_city) or pickup_coords

    rider, distance_km, workload, considered = pick_best_rider(pickup_coords)
    if not rider:
        return {'created': False, 'reason': 'no_rider'}

    total = float(order.total_amount or 0)
    priority = 'urgent' if total >= 200000 else 'normal'
    # Resolve a realistic distance (floor avoids a misleading 0 km for same-city).
    dist = distance_km if distance_km is not None else DEFAULT_DISTANCE_KM
    dist = max(dist, MIN_DISTANCE_KM)
    earning = round(BASE_FEE + PER_KM_FEE * dist)

    assignment = DeliveryAssignment(
        rider_id=rider.id,
        order_id=order.id,
        order_code=order.order_number or f'ORD-{order.id}',
        pickup_location=pickup_label,
        dropoff_location=dropoff_label,
        distance_km=dist,
        priority=priority,
        status='assigned',
        earning=earning,
        # Seed tracking coords so the live map has pickup/drop-off pins immediately.
        pickup_lat=pickup_coords[0], pickup_lng=pickup_coords[1],
        dropoff_lat=dropoff_coords[0], dropoff_lng=dropoff_coords[1],
    )
    db.session.add(assignment)
    db.session.flush()  # get assignment.id for the notification

    # Notify the rider (consumed by the rider dashboard's live poll).
    try:
        db.session.add(Notification(
            user_id=rider.user_id,
            title='New delivery assigned',
            message=f'{assignment.order_code}: {pickup_label} → {dropoff_label}',
            type='delivery',
            related_id=assignment.id,
        ))
    except Exception:
        # Notification is best-effort; never block assignment on it.
        pass

    if commit:
        db.session.commit()

    return {
        'created': True,
        'assignment': assignment,
        'rider': rider,
        'distance_km': distance_km,
        'workload': workload,
        'considered': considered,
        'earning': earning,
    }
