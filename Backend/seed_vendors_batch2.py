"""
Top up vendor accounts to a round 20 for the demo (idempotent — safe to re-run).

Adds 7 more approved vendor accounts in cities not yet covered by the existing
seed scripts (seed_vendors_components.py covers Lahore/Karachi/Islamabad/Gujranwala).
Login for each: <email> / vendor123

Run from the Dashboard/ folder:
    python seed_vendors_batch2.py
"""
import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_DIR)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from app import create_app, db  # noqa: E402
from app.models import Role, User, Vendor  # noqa: E402

VENDOR_PASSWORD = 'vendor123'

# (name, email, shop_name, city, address, phone)
VENDORS = [
    ('Faheem Akram',   'vendor.fsd@genspark.com', 'Crystal Computers',        'Faisalabad',  'Susan Road, Faisalabad',    '0300-1110005'),
    ('Zeeshan Malik',  'vendor.mux@genspark.com', 'Multan Tech Bazar',        'Multan',      'Hussain Agahi, Multan',     '0300-1110006'),
    ('Adnan Khattak',  'vendor.pew@genspark.com', 'Khyber Electronics',       'Peshawar',    'University Road, Peshawar', '0300-1110007'),
    ('Bilal Hayat',    'vendor.rwp@genspark.com', 'Pindi PC Point',           'Rawalpindi',  'Commercial Market, Pindi',  '0300-1110008'),
    ('Tariq Mehmood',  'vendor.skt@genspark.com', 'Sialkot Digital Store',    'Sialkot',     'Paris Road, Sialkot',       '0300-1110009'),
    ('Hassan Raza',    'vendor.lhr2@genspark.com','Liberty Tech Mart',        'Lahore',      'Liberty Market, Lahore',    '0300-1110010'),
    ('Fahad Siddiqui', 'vendor.khi2@genspark.com','Clifton Computer World',   'Karachi',     'Clifton Block 5, Karachi',  '0300-1110011'),
]


def get_or_create_vendor(role_id, name, email, shop, city, address, phone):
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(name=name, email=email, role_id=role_id)
        user.set_password(VENDOR_PASSWORD)
        db.session.add(user)
        db.session.flush()
    vendor = Vendor.query.filter_by(user_id=user.id).first()
    if not vendor:
        vendor = Vendor(
            user_id=user.id, shop_name=shop, city=city,
            address=address, phone=phone, approval_status='approved',
        )
        db.session.add(vendor)
        created = True
    else:
        vendor.approval_status = 'approved'
        created = False
    return created


def main():
    app = create_app(os.getenv('FLASK_ENV', 'development'))
    with app.app_context():
        role = Role.query.filter_by(name='vendor').first()
        if not role:
            raise RuntimeError('Vendor role not found. Run init_db.py first.')

        added = 0
        for name, email, shop, city, address, phone in VENDORS:
            if get_or_create_vendor(role.id, name, email, shop, city, address, phone):
                added += 1
        db.session.commit()

        total = Vendor.query.count()
        print(f'Done. Added {added} new vendor(s). Total vendors now: {total}.')
        print('Logins (password vendor123):')
        for _, email, shop, *_ in VENDORS:
            print(f'   {shop:<28} {email}')


if __name__ == '__main__':
    main()
