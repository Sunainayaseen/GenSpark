"""
Seed a demo rider account + sample delivery assignments for the Rider Dashboard.

Creates (idempotent — safe to re-run):
  * role 'rider' (if missing)
  * user  rider@genspark.com / rider123  (role: rider)
  * a Rider profile for that user
  * a spread of DeliveryAssignment rows covering every status so the dashboard,
    the admin "Rider Approvals" flow, and the earnings chart all have data:
        - assigned          -> shows the green "Request Pickup" button
        - pickup_requested  -> shows the orange "Waiting for Admin Approval" badge
        - approved          -> shows "Start Delivery"
        - in_transit        -> shows "Mark Delivered"
        - delivered (x3)    -> feeds Completed Today + earnings history

Run from the Dashboard/ folder:
    python seed_rider_demo.py
"""
import os
import sys
from datetime import datetime, timedelta

_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_DIR)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from app import create_app, db  # noqa: E402
from app.models import Role, User, Rider, DeliveryAssignment, Order  # noqa: E402

RIDER_EMAIL = 'rider@genspark.com'
RIDER_PASSWORD = 'rider123'

# (order_code, pickup, dropoff, distance_km, priority, status, earning, days_ago_delivered)
SAMPLE_DELIVERIES = [
    ('GS-7711-AI', 'TechZone, Hall Road, Lahore', 'DHA Phase 5, Lahore', 5.2, 'normal', 'assigned', 250, None),
    ('GS-7712-AI', 'PC Galaxy, Saddar, Karachi', 'Gulshan-e-Iqbal, Karachi', 8.7, 'urgent', 'pickup_requested', 350, None),
    ('GS-7713-AI', 'Mega Computers, Blue Area, Islamabad', 'F-10 Markaz, Islamabad', 3.1, 'normal', 'approved', 250, None),
    ('GS-7714-AI', 'CityTech, Gulberg, Lahore', 'Johar Town, Lahore', 6.4, 'normal', 'in_transit', 300, None),
    ('GS-7705-AI', 'TechZone, Hall Road, Lahore', 'Model Town, Lahore', 4.0, 'normal', 'delivered', 250, 0),
    ('GS-7706-AI', 'PC Galaxy, Saddar, Karachi', 'Clifton, Karachi', 7.8, 'urgent', 'delivered', 400, 1),
    ('GS-7707-AI', 'Mega Computers, Blue Area, Islamabad', 'G-11, Islamabad', 5.5, 'normal', 'delivered', 300, 3),
]


def get_or_create_rider_user():
    role = Role.query.filter_by(name='rider').first()
    if not role:
        role = Role(name='rider')
        db.session.add(role)
        db.session.flush()
        print("  created role 'rider'")

    user = User.query.filter_by(email=RIDER_EMAIL).first()
    if not user:
        user = User(name='Sarah K.', email=RIDER_EMAIL, role_id=role.id)
        user.set_password(RIDER_PASSWORD)
        db.session.add(user)
        db.session.flush()
        print(f'  created user {RIDER_EMAIL} / {RIDER_PASSWORD}')
    else:
        # Make sure an existing account is actually a rider.
        user.role_id = role.id

    rider = Rider.query.filter_by(user_id=user.id).first()
    if not rider:
        rider = Rider(
            user_id=user.id, phone='0300-1234567', city='Lahore',
            vehicle_type='bike', vehicle_number='LEA-1234',
            is_online=True, rating=4.8, total_completed=0,
        )
        db.session.add(rider)
        db.session.flush()
        print(f'  created rider profile {rider.display_code}')
    return rider


def main():
    app = create_app(os.getenv('FLASK_ENV', 'development'))
    with app.app_context():
        rider = get_or_create_rider_user()

        # Try to attach to a real order id when one exists (purely cosmetic link).
        first_order = Order.query.order_by(Order.id.asc()).first()
        order_id = first_order.id if first_order else None

        created, skipped, completed = 0, 0, 0
        for code, pickup, dropoff, dist, prio, status, earning, days_ago in SAMPLE_DELIVERIES:
            existing = DeliveryAssignment.query.filter_by(rider_id=rider.id, order_code=code).first()
            if existing:
                skipped += 1
                continue
            job = DeliveryAssignment(
                rider_id=rider.id,
                order_id=order_id,
                order_code=code,
                pickup_location=pickup,
                dropoff_location=dropoff,
                distance_km=dist,
                priority=prio,
                status=status,
                earning=earning,
            )
            now = datetime.utcnow()
            if status == 'pickup_requested':
                job.pickup_requested_at = now
            elif status == 'approved':
                job.pickup_requested_at = now - timedelta(minutes=20)
                job.approved_at = now
            elif status == 'in_transit':
                job.pickup_requested_at = now - timedelta(hours=1)
                job.approved_at = now - timedelta(minutes=50)
            elif status == 'delivered':
                delivered_at = now - timedelta(days=days_ago or 0)
                job.pickup_requested_at = delivered_at - timedelta(hours=2)
                job.approved_at = delivered_at - timedelta(hours=1, minutes=50)
                job.delivered_at = delivered_at
                completed += 1
            db.session.add(job)
            created += 1

        # Keep the rider's lifetime completed count in sync with delivered rows
        # (autoflush makes the just-added rows visible to this count).
        rider.total_completed = DeliveryAssignment.query.filter_by(
            rider_id=rider.id, status='delivered'
        ).count()

        db.session.commit()
        print(f'\nDone. Deliveries created: {created}, skipped (existing): {skipped}.')
        print(f'Login: {RIDER_EMAIL} / {RIDER_PASSWORD}  ->  /rider/dashboard')


if __name__ == '__main__':
    main()
