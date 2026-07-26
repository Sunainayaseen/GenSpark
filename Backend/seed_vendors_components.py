"""
Seed a small set of demo vendors + components (and link them) for the GenSpark ERP.

Adds (idempotent — safe to re-run, no duplicates):
  * 4 vendor accounts (role 'vendor', profile approved) in different cities.
    Login for each: <email> / vendor123
  * 5 components across categories, each with price + catalog stock.
  * vendor_components links so each component has real per-vendor stock/price
    (this is what the cart's vendor-assignment + vendor inventory screens read).

Run from the Dashboard/ folder:
    python seed_vendors_components.py
"""
import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_DIR)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from app import create_app, db  # noqa: E402
from app.models import (  # noqa: E402
    Role, User, Vendor, Component, ComponentCategory, VendorComponent,
)

VENDOR_PASSWORD = 'vendor123'

# (name, email, shop_name, city, address, phone)
VENDORS = [
    ('Imran Traders',   'vendor.lhr@genspark.com', 'TechZone Computers',   'Lahore',    'Hall Road, Lahore',        '0300-1110001'),
    ('Karachi PC Hub',  'vendor.khi@genspark.com', 'PC Galaxy',            'Karachi',   'Saddar, Karachi',          '0300-1110002'),
    ('Capital Systems', 'vendor.isb@genspark.com', 'Mega Computers',       'Islamabad', 'Blue Area, Islamabad',     '0300-1110003'),
    ('CityTech Store',  'vendor.gjr@genspark.com', 'CityTech Electronics', 'Gujranwala','GT Road, Gujranwala',      '0300-1110004'),
]

# (component name, category, price PKR, catalog stock)
# brand_id is left NULL on purpose: the live MySQL schema's components.brand_id FK
# points at a different brand table than the ORM maps, so setting it breaks inserts.
COMPONENTS = [
    ('Intel Core i5-13400F 10-Core Processor', 'Processor',   58000, 30),
    ('NVIDIA GeForce RTX 4070 Ti SUPER 16GB',  'GPU',         285000, 14),
    ('Gigabyte B760M DS3H DDR4 (mATX)',         'Motherboard', 32000, 26),
    ('Kingston Fury Beast 32GB DDR5 5200MHz',   'RAM',         34000, 28),
    ('Samsung 990 PRO 2TB NVMe SSD',            'Storage',     48000, 22),
]

# Spread each component across this many vendors with slight price variation.
VENDOR_PRICE_DELTAS = (1.0, 1.04, 0.97, 1.02)

# Minimum catalog + per-vendor stock for every seeded component, so parts never
# resolve as "Out of stock".
DEFAULT_MIN_STOCK = 50


def get_or_create_category(name):
    cat = ComponentCategory.query.filter_by(name=name).first()
    if not cat:
        cat = ComponentCategory(name=name, slug=name.lower())
        db.session.add(cat)
        db.session.flush()
    return cat


def get_or_create_vendor(name, email, shop, city, address, phone):
    role = Role.query.filter_by(name='vendor').first()
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(name=name, email=email, role_id=role.id)
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
        db.session.flush()
    else:
        vendor.approval_status = 'approved'
    return vendor, (email, VENDOR_PASSWORD)


def get_or_create_component(name, category, price, stock):
    # Guarantee positive, healthy stock regardless of the per-row value above.
    stock = max(int(stock or 0), DEFAULT_MIN_STOCK)
    comp = Component.query.filter_by(name=name).first()
    if not comp:
        comp = Component(
            name=name, category_id=category.id,
            description=f'{name} - genuine retail unit for GenSpark builds.',
            price=price, stock=stock,
        )
        db.session.add(comp)
        db.session.flush()
        return comp, True
    comp.category_id = category.id
    comp.price = price
    if (comp.stock or 0) < stock:
        comp.stock = stock
    return comp, False


def link_vendor_component(vendor, comp, base_price, idx):
    delta = VENDOR_PRICE_DELTAS[idx % len(VENDOR_PRICE_DELTAS)]
    vprice = round(base_price * delta)
    link = VendorComponent.query.filter_by(vendor_id=vendor.id, component_id=comp.id).first()
    if link:
        link.price = vprice
        if (link.quantity or 0) < DEFAULT_MIN_STOCK:
            link.quantity = DEFAULT_MIN_STOCK
        return 0
    db.session.add(VendorComponent(vendor_id=vendor.id, component_id=comp.id, quantity=DEFAULT_MIN_STOCK, price=vprice))
    return 1


def main():
    app = create_app(os.getenv('FLASK_ENV', 'development'))
    with app.app_context():
        vendors, creds = [], []
        for v in VENDORS:
            vendor, cred = get_or_create_vendor(*v)
            vendors.append(vendor)
            creds.append(cred)

        comp_created, links = 0, 0
        for name, cat_name, price, stock in COMPONENTS:
            cat = get_or_create_category(cat_name)
            comp, created = get_or_create_component(name, cat, price, stock)
            comp_created += 1 if created else 0
            # Link each component to the first 3 vendors (so cart has real choices).
            for idx, vendor in enumerate(vendors[:3]):
                links += link_vendor_component(vendor, comp, price, idx)

        db.session.commit()

        print(f'\nDone. Vendors ready: {len(vendors)}, new components: {comp_created}, new vendor links: {links}.')
        print('Vendor logins (password vendor123):')
        for email, pw in creds:
            print(f'   {email} / {pw}')


if __name__ == '__main__':
    main()
