"""
Assign clean, category-relevant product images to the seeded catalog parts.

Why: the curated parts (AMD/NVIDIA/Corsair/... from seed_prebuilt_parts.py) had
no image_url, so the frontend fuzzy-matcher picked the wrong OEM photo (e.g. a
yellow HP power-supply box for a Corsair PSU). Setting image_url directly makes
it win (it's the first image candidate), giving each part a clean, on-brand
category photo. OEM (Dell/HP/Lenovo) products are left untouched — their local
product photos stay correct.

Idempotent. Run from Dashboard/:  python set_component_images.py
"""
import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_DIR)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from app import create_app, db          # noqa: E402
from app.models import Component        # noqa: E402
from seed_prebuilt_parts import CURATED_PARTS  # noqa: E402  (exact seeded names)

# Mirrors the frontend's curated stock photos (componentImage.js STOCK_PHOTO_BY_KIND).
_Q = 'auto=format&fit=crop&w=720&h=720&crop=center&q=85'
_STOCK = {
    'cpu': 'photo-1686195165991-74af7c2918d5',
    'gpu': 'photo-1591488320449-011701bb6704',
    'ram': 'photo-1541029071515-84cc54f84dc5',
    'storage': 'photo-1760623227551-2eae8f9cb675',
    'motherboard': 'photo-1650526573230-8f8dfb89e509',
    'psu': 'photo-1756576170672-1123237f1d77',
    'case': 'photo-1573053986275-840ffc7cc685',
}
_CATEGORY_TO_KIND = {
    'Processor': 'cpu', 'CPU': 'cpu',
    'GPU': 'gpu', 'Graphics Card': 'gpu',
    'Motherboard': 'motherboard',
    'RAM': 'ram',
    'Storage': 'storage',
    'PSU': 'psu', 'Power Supply': 'psu',
    'Case': 'case', 'Cabinet': 'case',
}


def image_for(kind):
    return f'https://images.unsplash.com/{_STOCK[kind]}?{_Q}'


def main():
    app = create_app(os.getenv('FLASK_ENV', 'development'))
    with app.app_context():
        updated = 0
        for name, category, *_ in CURATED_PARTS:
            kind = _CATEGORY_TO_KIND.get(category)
            if not kind:
                continue
            comp = Component.query.filter_by(name=name).first()
            if not comp:
                continue
            comp.image_url = image_for(kind)
            updated += 1
        db.session.commit()
        print(f'Updated image_url for {updated} seeded components '
              f'(clean category photos). OEM products untouched.')


if __name__ == '__main__':
    main()
