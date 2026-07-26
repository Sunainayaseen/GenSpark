# Rider (delivery) Management
import math
from datetime import datetime
from app import db


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance in km between two lat/lng points."""
    if None in (lat1, lng1, lat2, lng2):
        return None
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(r * 2 * math.asin(math.sqrt(a)), 3)


# Delivery lifecycle:
#   assigned         -> rider has the job, can request pickup
#   pickup_requested -> rider asked to pick up; WAITING FOR ADMIN APPROVAL
#   approved         -> admin verified; rider may collect from vendor
#   in_transit       -> picked up, on the way to customer
#   delivered        -> completed (counts toward earnings + rating)
#   rejected         -> admin declined the pickup request
DELIVERY_STATUSES = [
    'assigned', 'pickup_requested', 'approved', 'in_transit', 'delivered', 'rejected',
]

DELIVERY_PRIORITIES = ['normal', 'urgent']


class Rider(db.Model):
    """Rider profile — mirrors the Vendor model pattern (one-to-one with User)."""
    __tablename__ = 'riders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    phone = db.Column(db.String(20))
    city = db.Column(db.String(100))
    vehicle_type = db.Column(db.String(50))   # bike, car, van
    vehicle_number = db.Column(db.String(30))
    is_online = db.Column(db.Boolean, default=False, nullable=False)
    rating = db.Column(db.Float, default=5.0)          # 0.0 - 5.0
    total_completed = db.Column(db.Integer, default=0)  # lifetime delivered count
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('rider', uselist=False))
    deliveries = db.relationship('DeliveryAssignment', backref='rider', lazy='dynamic')

    @property
    def display_code(self):
        """Human-friendly rider id shown on the dashboard, e.g. RDR-0007."""
        return f'RDR-{self.id:04d}'


class DeliveryAssignment(db.Model):
    """A single delivery job handed to a rider. order_id is optional so demo/seed
    rows can exist without a full master Order (uses order_code for display)."""
    __tablename__ = 'delivery_assignments'
    id = db.Column(db.Integer, primary_key=True)
    rider_id = db.Column(db.Integer, db.ForeignKey('riders.id'), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    order_code = db.Column(db.String(50))  # e.g. GS-7711-AI (display label)

    pickup_location = db.Column(db.String(200))   # vendor / shop
    dropoff_location = db.Column(db.String(200))  # customer
    distance_km = db.Column(db.Float, default=0)
    priority = db.Column(db.String(20), default='normal')  # normal, urgent
    status = db.Column(db.String(30), default='assigned')
    earning = db.Column(db.Numeric(12, 2), default=0)  # rider payout for this job

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    pickup_requested_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)

    # --- Live tracking (Leaflet) -------------------------------------------
    pickup_lat = db.Column(db.Float)
    pickup_lng = db.Column(db.Float)
    dropoff_lat = db.Column(db.Float)
    dropoff_lng = db.Column(db.Float)
    current_lat = db.Column(db.Float)
    current_lng = db.Column(db.Float)
    current_speed = db.Column(db.Float)             # km/h (real GPS)
    location_updated_at = db.Column(db.DateTime)
    tracking_active = db.Column(db.Boolean, default=False, nullable=False)
    sim_mode = db.Column(db.Boolean, default=False, nullable=False)   # simulated mover
    sim_started_at = db.Column(db.DateTime)
    sim_duration_s = db.Column(db.Integer, default=180)              # pickup→dropoff seconds

    pings = db.relationship(
        'RiderLocationPing', backref='delivery', lazy='dynamic',
        cascade='all, delete-orphan',
    )

    @property
    def is_urgent(self):
        return (self.priority or '').lower() == 'urgent'

    def _live_position(self, now=None):
        """Return (lat, lng, progress 0-1 or None). Interpolates in sim mode."""
        now = now or datetime.utcnow()
        if (self.sim_mode and self.tracking_active and self.sim_started_at
                and self.pickup_lat is not None and self.dropoff_lat is not None):
            elapsed = (now - self.sim_started_at).total_seconds()
            dur = self.sim_duration_s or 180
            t = max(0.0, min(elapsed / dur, 1.0))
            lat = self.pickup_lat + (self.dropoff_lat - self.pickup_lat) * t
            lng = self.pickup_lng + (self.dropoff_lng - self.pickup_lng) * t
            return lat, lng, round(t, 3)
        if self.current_lat is not None:
            return self.current_lat, self.current_lng, None
        if self.pickup_lat is not None:
            return self.pickup_lat, self.pickup_lng, 0.0
        return None, None, None

    def _route_points(self, lat, lng):
        if self.sim_mode:
            pts = []
            if self.pickup_lat is not None:
                pts.append([self.pickup_lat, self.pickup_lng])
            if lat is not None:
                pts.append([round(lat, 6), round(lng, 6)])
            return pts
        rows = (
            RiderLocationPing.query
            .filter_by(delivery_id=self.id)
            .order_by(RiderLocationPing.created_at.asc())
            .limit(500).all()
        )
        return [[p.latitude, p.longitude] for p in rows]

    def tracking_snapshot(self):
        """Full payload for the customer / admin map and ETA display."""
        now = datetime.utcnow()
        lat, lng, progress = self._live_position(now)

        remaining_km = None
        eta_minutes = None
        if lat is not None and self.dropoff_lat is not None:
            remaining_km = haversine_km(lat, lng, self.dropoff_lat, self.dropoff_lng)
            if self.sim_mode and progress is not None:
                eta_minutes = round((self.sim_duration_s or 180) * (1 - progress) / 60)
            elif remaining_km is not None:
                speed = self.current_speed or 25.0
                eta_minutes = round((remaining_km / max(speed, 1.0)) * 60)

        # Tracking stops once delivered.
        active = bool(self.tracking_active) and self.status != 'delivered'
        return {
            'delivery_id': self.id,
            'order_id': self.order_id,
            'order_code': self.order_code,
            'status': self.status,
            'tracking_active': active,
            'latitude': round(lat, 6) if lat is not None else None,
            'longitude': round(lng, 6) if lng is not None else None,
            'pickup': ({'lat': self.pickup_lat, 'lng': self.pickup_lng}
                       if self.pickup_lat is not None else None),
            'dropoff': ({'lat': self.dropoff_lat, 'lng': self.dropoff_lng}
                        if self.dropoff_lat is not None else None),
            'route': self._route_points(lat, lng),
            'distance_remaining_km': remaining_km,
            'eta_minutes': eta_minutes,
            'speed': self.current_speed,
            'progress': progress,
            'sim_mode': bool(self.sim_mode),
            'updated_at': (self.location_updated_at or now).isoformat(),
        }


class RiderLocationPing(db.Model):
    """Append-only GPS breadcrumb trail for drawing the real route polyline."""
    __tablename__ = 'rider_location_pings'
    id = db.Column(db.Integer, primary_key=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey('delivery_assignments.id'), nullable=False, index=True)
    rider_id = db.Column(db.Integer, db.ForeignKey('riders.id'), nullable=False, index=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    speed = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
