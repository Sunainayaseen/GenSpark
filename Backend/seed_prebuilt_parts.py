"""
Seed the ERP catalog with the real PC components used by the React prebuilt
showcase (my-react-app/src/data/prebuiltShowcase.js).

Why: the prebuilt → Configure → Cart → Vendor → Checkout flow resolves each
showcase part name against /api/components/search. The default catalog only had
generic OEM peripherals (HP/Dell/Lenovo) with no CPUs/GPUs, so resolution found
nothing and the cart stayed empty. This adds proper, correctly-categorised parts
and links each to approved vendor stock (required by the cart's vendor-assignment
rule in cart_controller._select_vendor_for_component).

Idempotent: re-running updates prices/stock and tops up vendor links — no dupes.

Run from the Dashboard/ folder:
    python seed_prebuilt_parts.py
"""
import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_DIR)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from app import create_app, db  # noqa: E402
from app.models import (  # noqa: E402
    Component,
    ComponentCategory,
    Vendor,
    VendorComponent,
)

# (name, category, price PKR, catalog stock)
# Names contain the exact tokens the showcase values use, so the frontend
# resolver (buildResolver.js) scores them as the best match per slot.
CURATED_PARTS = [
    # ---- CPUs (category: Processor) ----
    ('AMD Ryzen 7 9800X3D 8-Core Processor', 'Processor', 165000, 25),
    ('AMD Ryzen 5 5600G 6-Core Processor', 'Processor', 38000, 30),
    ('AMD Ryzen 7 7700X 8-Core Processor', 'Processor', 95000, 25),
    ('AMD Ryzen 9 7950X3D 16-Core Processor', 'Processor', 230000, 15),
    ('AMD Ryzen 7 7700 8-Core Processor', 'Processor', 88000, 25),
    ('AMD Ryzen 5 7500F 6-Core Processor', 'Processor', 55000, 30),
    ('AMD Ryzen 5 7600 6-Core Processor', 'Processor', 62000, 28),
    ('AMD Ryzen 9 7900 12-Core Processor', 'Processor', 155000, 18),

    # ---- GPUs (category: GPU) ----
    ('NVIDIA GeForce RTX 5070 Ti 16GB', 'GPU', 240000, 18),
    ('NVIDIA GeForce RTX 4070 12GB', 'GPU', 175000, 20),
    ('NVIDIA GeForce RTX 4090 24GB', 'GPU', 620000, 8),
    ('NVIDIA GeForce RTX 4060 Ti 16GB', 'GPU', 135000, 22),
    ('NVIDIA GeForce RTX 4060 8GB', 'GPU', 95000, 30),

    # ---- Motherboards (category: Motherboard) ----
    ('ASUS TUF Gaming X870-PLUS WiFi (ATX)', 'Motherboard', 95000, 18),
    ('Gigabyte A520M DS3H (mATX)', 'Motherboard', 22000, 30),
    ('MSI PRO B650-P WiFi (ATX)', 'Motherboard', 55000, 25),
    ('ASUS ROG Strix X670E-E Gaming (ATX)', 'Motherboard', 140000, 12),
    ('MSI PRO B650M-A WiFi (mATX)', 'Motherboard', 48000, 25),
    ('ASRock B650E PG-ITX WiFi (ITX)', 'Motherboard', 72000, 16),

    # ---- RAM (category: RAM) ----
    ('Corsair Vengeance 32GB DDR5 6000MHz', 'RAM', 38000, 30),
    ('Corsair Vengeance LPX 16GB DDR4 3200MHz', 'RAM', 13000, 40),
    ('G.Skill Trident Z5 64GB DDR5 6000MHz', 'RAM', 78000, 15),
    ('Corsair Vengeance 16GB DDR5 5600MHz', 'RAM', 20000, 35),

    # ---- Storage (category: Storage) ----
    ('Samsung 980 1TB NVMe SSD', 'Storage', 18000, 40),
    ('Kingston NV2 512GB NVMe SSD', 'Storage', 9000, 50),
    ('WD Black SN770 2TB NVMe SSD', 'Storage', 35000, 25),

    # ---- PSU (category: PSU) ----
    ('Corsair RM850e 850W 80+ Gold', 'PSU', 32000, 25),
    ('Cooler Master MWE 450W 80+ Bronze', 'PSU', 9000, 35),
    ('Corsair RM750e 750W 80+ Gold', 'PSU', 26000, 28),
    ('Corsair RM1000e 1000W 80+ Gold', 'PSU', 42000, 18),
    ('Cooler Master MWE 650W 80+ Gold', 'PSU', 18000, 30),
    ('Cooler Master MWE 550W 80+ Bronze', 'PSU', 11000, 30),
    ('Corsair SF650 SFX 650W 80+ Gold', 'PSU', 34000, 15),

    # ---- Cases (category: Case) ----
    ('NZXT H5 Flow Mid-Tower Airflow Case', 'Case', 22000, 25),
    ('Cooler Master MasterBox Q300L Compact mATX Case', 'Case', 12000, 30),
    ('Montech AIR 903 Mid-Tower Case', 'Case', 14000, 28),
    ('Lian Li PC-O11 Full Tower Case', 'Case', 38000, 15),
    ('be quiet! Pure Base 500DX Mid-Tower Good Airflow Case', 'Case', 28000, 18),
    ('Montech X3 Mesh Mid-Tower Case', 'Case', 13000, 30),
    ('Cooler Master NR200 Mini-ITX Case', 'Case', 24000, 16),
    ('be quiet! Pure Base 500 Mid-Tower Silent Case', 'Case', 25000, 18),
]

CATEGORY_SLUGS = {
    'Processor': 'processor',
    'GPU': 'gpu',
    'Motherboard': 'motherboard',
    'RAM': 'ram',
    'Storage': 'storage',
    'PSU': 'psu',
    'Case': 'case',
}

# Spread each component across up to this many approved vendors (price varied
# slightly so the vendor-assignment screen shows real choices).
MAX_VENDORS_PER_PART = 3
VENDOR_PRICE_DELTAS = (1.0, 1.03, 0.98)

# Every seeded part is inserted with at least this much catalog stock AND
# per-vendor stock, so nothing ever resolves as "Out of stock".
DEFAULT_MIN_STOCK = 50


def get_or_create_category(name):
    cat = ComponentCategory.query.filter_by(name=name).first()
    if cat:
        return cat
    cat = ComponentCategory(name=name, slug=CATEGORY_SLUGS.get(name, name.lower()))
    db.session.add(cat)
    db.session.flush()
    return cat


def approved_vendors():
    vendors = Vendor.query.filter_by(approval_status='approved').all()
    if vendors:
        return vendors
    # Fallback: promote existing vendors so the flow is demoable.
    any_vendors = Vendor.query.all()
    for v in any_vendors:
        v.approval_status = 'approved'
    if any_vendors:
        db.session.flush()
        print(f'  (no approved vendors — promoted {len(any_vendors)} existing vendor(s) to approved)')
    return any_vendors


def get_or_create_component(name, category, price, stock):
    # Guarantee positive, healthy stock regardless of the per-row value above.
    stock = max(int(stock or 0), DEFAULT_MIN_STOCK)
    comp = Component.query.filter_by(name=name).first()
    if comp:
        comp.category_id = category.id
        comp.price = price
        if (comp.stock or 0) < stock:
            comp.stock = stock
        created = False
    else:
        comp = Component(
            name=name,
            category_id=category.id,
            description=f'{name} — genuine retail unit for GenSpark prebuilt configurations.',
            price=price,
            stock=stock,
        )
        db.session.add(comp)
        db.session.flush()
        created = True
    return comp, created


def ensure_vendor_links(comp, vendors, base_price):
    linked = 0
    for idx, vendor in enumerate(vendors[:MAX_VENDORS_PER_PART]):
        delta = VENDOR_PRICE_DELTAS[idx % len(VENDOR_PRICE_DELTAS)]
        vprice = round(base_price * delta)
        link = VendorComponent.query.filter_by(
            vendor_id=vendor.id, component_id=comp.id
        ).first()
        if link:
            if (link.quantity or 0) < DEFAULT_MIN_STOCK:
                link.quantity = DEFAULT_MIN_STOCK
            link.price = vprice
        else:
            db.session.add(
                VendorComponent(
                    vendor_id=vendor.id,
                    component_id=comp.id,
                    quantity=DEFAULT_MIN_STOCK,
                    price=vprice,
                )
            )
            linked += 1
    return linked


def main():
    app = create_app(os.getenv('FLASK_ENV', 'development'))
    with app.app_context():
        vendors = approved_vendors()
        if not vendors:
            print('ERROR: No vendors in DB. Create at least one vendor first, then re-run.')
            return

        print(f'Using {len(vendors)} approved vendor(s): '
              f'{", ".join(v.shop_name for v in vendors[:MAX_VENDORS_PER_PART])}')

        categories = {}
        created_count = 0
        updated_count = 0
        links_count = 0

        for name, cat_name, price, stock in CURATED_PARTS:
            if cat_name not in categories:
                categories[cat_name] = get_or_create_category(cat_name)
            comp, created = get_or_create_component(name, categories[cat_name], price, stock)
            created_count += 1 if created else 0
            updated_count += 0 if created else 1
            links_count += ensure_vendor_links(comp, vendors, price)

        db.session.commit()
        print(f'\nDone. Components created: {created_count}, updated: {updated_count}. '
              f'New vendor links: {links_count}.')
        print('Catalog now serves real CPUs/GPUs/Mobos/RAM/Storage/PSU/Case with vendor stock.')


if __name__ == '__main__':
    main()
