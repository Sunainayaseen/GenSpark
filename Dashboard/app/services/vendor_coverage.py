"""Single-vendor-per-build rule.

GenSpark has no central warehouse — assembly is physically performed by whichever
vendor supplies the parts. A PC build (CPU/GPU/Motherboard/RAM/Storage/PSU/Case) must
therefore come from exactly one vendor; standalone accessories are unaffected.

"Which catalog categories count as a build part" reuses `_REC_SLOT_RULES` from
`ai_build_routes.py` (the recommender's own category map) so this never drifts out of
sync with what `/api/recommend-build` and `/api/build-options` already consider a
build slot.
"""
from __future__ import annotations

VENDOR_CONFLICT_MESSAGE = (
    'All selected components must be sourced from a single vendor because assembly '
    'is performed by the supplying vendor. Please choose components from one vendor '
    'only.'
)


def build_category_names() -> set[str]:
    from app.api.ai_build_routes import _REC_SLOT_RULES
    return {name for rule in _REC_SLOT_RULES.values() for name in rule['cats']}


def is_build_component(component) -> bool:
    category = getattr(component, 'category', None)
    name = getattr(category, 'name', None)
    return bool(name) and name in build_category_names()


def vendor_coverage_for_components(component_quantities: dict[int, int]) -> dict:
    """component_quantities: {component_id: required_qty}.

    Returns {'vendors': [...sorted full-coverage-first, then cheapest total...],
             'best': <vendor dict or None>, 'covers_all': bool,
             'missing_component_ids': [...]}.
    """
    if not component_quantities:
        return {'vendors': [], 'best': None, 'covers_all': True, 'missing_component_ids': []}

    from app import db
    from app.models import Vendor, VendorComponent, VendorRating
    from sqlalchemy import func

    rows = (
        VendorComponent.query
        .join(Vendor, Vendor.id == VendorComponent.vendor_id)
        .filter(VendorComponent.component_id.in_(component_quantities.keys()))
        .filter(Vendor.approval_status == 'approved')
        .all()
    )

    by_vendor: dict[int, dict] = {}
    for row in rows:
        required = component_quantities.get(row.component_id, 0)
        if int(row.quantity or 0) < required:
            continue
        info = by_vendor.setdefault(row.vendor_id, {})
        info[row.component_id] = float(row.price) if row.price is not None else 0.0

    rating_rows = (
        db.session.query(
            VendorRating.vendor_id,
            func.avg(VendorRating.rating),
            func.count(VendorRating.id),
        )
        .filter(VendorRating.vendor_id.in_(by_vendor.keys()))
        .group_by(VendorRating.vendor_id)
        .all()
        if by_vendor else []
    )
    ratings_by_vendor = {
        vid: {'avg_rating': round(float(avg), 1), 'rating_count': int(count)}
        for vid, avg, count in rating_rows
    }

    required_ids = set(component_quantities.keys())
    vendors_out = []
    for vendor_id, covered in by_vendor.items():
        vendor = Vendor.query.get(vendor_id)
        covered_ids = set(covered.keys())
        rating_info = ratings_by_vendor.get(vendor_id, {})
        vendors_out.append({
            'id': vendor_id,
            'shop_name': vendor.shop_name if vendor else f'Vendor #{vendor_id}',
            'city': vendor.city if vendor else None,
            'phone': vendor.phone if vendor else None,
            'covered_component_ids': sorted(covered_ids),
            'covered_count': len(covered_ids),
            'total_price': sum(covered.values()),
            'full_coverage': covered_ids == required_ids,
            'avg_rating': rating_info.get('avg_rating'),
            'rating_count': rating_info.get('rating_count', 0),
        })

    vendors_out.sort(key=lambda v: (not v['full_coverage'], -v['covered_count'], v['total_price']))
    best = vendors_out[0] if vendors_out else None
    covers_all = bool(best and best['full_coverage'])
    missing = sorted(required_ids - set(best['covered_component_ids'])) if best else sorted(required_ids)
    return {
        'vendors': vendors_out,
        'best': best,
        'covers_all': covers_all,
        'missing_component_ids': [] if covers_all else missing,
    }


def check_build_vendor_consistency(components_by_slot: dict):
    """components_by_slot: {slot: Component}. Returns (check_dict, best_vendor_or_None).

    check_dict mirrors compatibility.py's check shape:
        {'rule': 'Vendor consistency', 'status': 'pass'|'skip'|'fail', 'detail': str,
         'conflicting_slots': [...]}
    """
    build_parts = {slot: c for slot, c in (components_by_slot or {}).items()
                   if c and is_build_component(c)}
    if not build_parts:
        return {'rule': 'Vendor consistency', 'status': 'skip',
                'detail': 'No build components to check.', 'conflicting_slots': []}, None

    quantities = {c.id: 1 for c in build_parts.values()}
    coverage = vendor_coverage_for_components(quantities)
    best = coverage['best']

    if coverage['covers_all']:
        return {
            'rule': 'Vendor consistency', 'status': 'pass',
            'detail': f"All parts available from {best['shop_name']}.",
            'conflicting_slots': [],
        }, best

    missing_ids = set(coverage['missing_component_ids'])
    conflicting_slots = [slot for slot, c in build_parts.items() if c.id in missing_ids]
    return {
        'rule': 'Vendor consistency', 'status': 'fail',
        'detail': VENDOR_CONFLICT_MESSAGE,
        'conflicting_slots': conflicting_slots,
    }, best
