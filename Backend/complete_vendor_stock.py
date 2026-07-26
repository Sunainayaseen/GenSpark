"""One-off dev script: give every approved vendor full stock of every PC-build
component (CPU/GPU/Motherboard/RAM/Storage/PSU/Case), so the vendor-picker on
checkout shows all vendors as eligible instead of just the ones that happen to
already stock a complete build.

Safe to re-run: only inserts missing (vendor, component) rows or tops up
quantity on existing rows that are too low; never deletes or lowers anything.
"""
from app import create_app, db
from app.models import Vendor, VendorComponent, Component, ComponentCategory
from app.api.ai_build_routes import _REC_SLOT_RULES

MIN_QTY = 15

app = create_app('development')
with app.app_context():
    build_cats = {name for rule in _REC_SLOT_RULES.values() for name in rule['cats']}
    build_components = (
        Component.query.join(ComponentCategory)
        .filter(ComponentCategory.name.in_(build_cats))
        .all()
    )
    vendors = Vendor.query.filter_by(approval_status='approved').all()

    existing = {
        (vc.vendor_id, vc.component_id): vc
        for vc in VendorComponent.query.filter(
            VendorComponent.component_id.in_([c.id for c in build_components])
        )
    }

    created = 0
    topped_up = 0
    for vendor in vendors:
        for comp in build_components:
            key = (vendor.id, comp.id)
            row = existing.get(key)
            if row is None:
                db.session.add(VendorComponent(
                    vendor_id=vendor.id,
                    component_id=comp.id,
                    quantity=MIN_QTY,
                    price=comp.price or 0,
                ))
                created += 1
            elif int(row.quantity or 0) < MIN_QTY:
                row.quantity = MIN_QTY
                topped_up += 1

    db.session.commit()
    print(f'Vendors: {len(vendors)}  Build components: {len(build_components)}')
    print(f'New vendor-component rows created: {created}')
    print(f'Existing rows topped up to qty>={MIN_QTY}: {topped_up}')
