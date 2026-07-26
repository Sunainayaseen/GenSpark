"""
Give EVERY catalog component a clean, category-relevant product image.

Fills `image_url` for any component that is still missing one, choosing the
image by the product NAME (not the DB category, which is sometimes mislabelled —
e.g. an SSD filed under "Motherboard"). Uses the app's curated stock photos so
the look stays consistent and modern. Components that already have an image are
left untouched.

Idempotent. Run from Dashboard/:  python set_all_component_images.py
"""
import os
import re
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_DIR)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from app import create_app, db        # noqa: E402
from app.models import Component      # noqa: E402

_Q = 'auto=format&fit=crop&w=720&h=720&crop=center&q=85'
# All verified HTTP 200 (keyboard's own photo 404'd → reuse the peripheral shot).
_STOCK = {
    'cpu': 'photo-1686195165991-74af7c2918d5',
    'gpu': 'photo-1591488320449-011701bb6704',
    'ram': 'photo-1541029071515-84cc54f84dc5',
    'storage': 'photo-1760623227551-2eae8f9cb675',
    'motherboard': 'photo-1650526573230-8f8dfb89e509',
    'psu': 'photo-1756576170672-1123237f1d77',
    'case': 'photo-1573053986275-840ffc7cc685',
    'cooling': 'photo-1754821130717-60c970da55dc',
    'monitor': 'photo-1593640408182-31c70c8268f5',
    'mouse': 'photo-1527864550417-7fd91fc51a46',
    'keyboard': 'photo-1632078056157-f7eb9c54e9cc',
    'peripheral': 'photo-1632078056157-f7eb9c54e9cc',
    'generic': 'photo-1518770660439-4636190af475',
}


def detect_kind(name, category):
    """Match the frontend's name-first heuristic so mislabelled rows still work."""
    s = f'{category or ""} {name or ""}'.lower()
    if re.search(r'\bmouse\b|optical mouse|wireless mouse', s):
        return 'mouse'
    if re.search(r'keyboard|keypad', s):
        return 'keyboard'
    if re.search(r'\bmonitor\b|display|\bscreen\b', s):
        return 'monitor'
    if re.search(r'geforce|\brtx\b|\bgtx\b|radeon|\brx\s?\d|graphics|video card|\bgpu\b', s):
        return 'gpu'
    if re.search(r'ryzen|core\s?i[3579]|\bi[3579]\b|processor|\bcpu\b|xeon|celeron|athlon|threadripper', s):
        return 'cpu'
    if re.search(r'\bram\b|ddr\d|dimm|memory', s):
        return 'ram'
    if re.search(r'\bssd\b|nvme|\bhdd\b|hard\s?drive|storage|\bm\.?2\b', s):
        return 'storage'
    if re.search(r'motherboard|mainboard|mobo|\b[bxhza]\d{3}\b|chipset', s):
        return 'motherboard'
    if re.search(r'power supply|\bpsu\b|\d{3,4}\s?w\b|80\s?\+|bronze|gold|platinum|smps', s):
        return 'psu'
    if re.search(r'\bcase\b|tower|chassis|cabinet|mesh', s):
        return 'case'
    if re.search(r'cooler|cooling|\bfan\b|\baio\b|liquid|heatsink', s):
        return 'cooling'
    return 'generic'


def main():
    app = create_app(os.getenv('FLASK_ENV', 'development'))
    with app.app_context():
        rows = Component.query.all()
        filled = 0
        by_kind = {}
        for c in rows:
            current = (c.image_url or '').strip()
            if current:
                continue  # keep existing images (incl. the 41 already set)
            kind = detect_kind(c.name, c.category.name if getattr(c, 'category', None) else '')
            c.image_url = f'https://images.unsplash.com/{_STOCK[kind]}?{_Q}'
            by_kind[kind] = by_kind.get(kind, 0) + 1
            filled += 1
        db.session.commit()
        print(f'Filled image_url for {filled} components without one.')
        for k, n in sorted(by_kind.items()):
            print(f'  {k:<12} {n}')
        total = Component.query.filter(
            (Component.image_url.isnot(None)) & (Component.image_url != '')
        ).count()
        print(f'Components with an image now: {total} / {len(rows)}')


if __name__ == '__main__':
    main()
