"""
Seed a small fleet of ONLINE riders so the Best-Rider Scoring Engine has real
candidates to choose between during the live auto-assignment demo.

Adds (idempotent): 3 extra riders in different cities with varied ratings, all
online and with no active workload — so for a Lahore pickup the engine can show
off "least-busy + nearest + top-rated" selection vs. the busy demo rider.

Run from the Dashboard/ folder:
    python seed_riders_fleet.py
"""
import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_DIR)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from app import create_app, db  # noqa: E402
from app.models import Role, User, Rider  # noqa: E402

RIDER_PASSWORD = 'rider123'

# (name, email, city, vehicle_type, vehicle_number, rating)
FLEET = [
    ('Usman T.', 'rider.usman@genspark.com', 'Lahore',    'bike', 'LEB-7781', 4.3),
    ('Bilal A.', 'rider.bilal@genspark.com', 'Karachi',   'car',  'KHI-2204', 4.6),
    ('Hamza R.', 'rider.hamza@genspark.com', 'Islamabad', 'bike', 'ISB-9012', 4.9),
]


def main():
    app = create_app(os.getenv('FLASK_ENV', 'development'))
    with app.app_context():
        role = Role.query.filter_by(name='rider').first()
        if not role:
            role = Role(name='rider')
            db.session.add(role)
            db.session.flush()

        created = 0
        for name, email, city, vtype, vnum, rating in FLEET:
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(name=name, email=email, role_id=role.id)
                user.set_password(RIDER_PASSWORD)
                db.session.add(user)
                db.session.flush()
            else:
                user.role_id = role.id

            rider = Rider.query.filter_by(user_id=user.id).first()
            if not rider:
                rider = Rider(
                    user_id=user.id, city=city, vehicle_type=vtype,
                    vehicle_number=vnum, rating=rating, is_online=True,
                    total_completed=0, phone='0300-0000000',
                )
                db.session.add(rider)
                created += 1
            else:
                rider.is_online = True
                rider.city = city
                rider.rating = rating

        db.session.commit()
        print(f'Done. Fleet riders ready (created {created}). All online.')
        print('Logins (password rider123):')
        for _, email, *_ in FLEET:
            print(f'   {email} / {RIDER_PASSWORD}')


if __name__ == '__main__':
    main()
