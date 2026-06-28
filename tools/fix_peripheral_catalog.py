"""
Fix catalog rows where mice/keyboards use wrong category (Cabinet) or bad image_url.

Usage (from repo root, with MySQL running):
  myvenv\\Scripts\\python.exe tools\\fix_peripheral_catalog.py

Re-upload photos via Admin → Components → Edit → Product image for best results.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'backend'))

def _load_env() -> None:
    env_path = REPO / 'backend' / '.env'
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        os.environ.setdefault(key.strip(), val.strip())


_load_env()

import mysql.connector


def infer_slug(name: str) -> str | None:
    n = (name or '').lower()
    if re.search(r'\bmouse\b|mice\b|optical mouse', n):
        return 'mouse'
    if re.search(r'keyboard|keypad', n):
        return 'keyboard'
    if re.search(r'\bmonitor\b', n):
        return 'monitor'
    if re.search(r'\bram\b|memory|ddr', n):
        return 'ram'
    return None


def main() -> int:
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', '3306')),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'genspark_erp'),
    )
    cur = conn.cursor(dictionary=True)

    cur.execute('SELECT id, slug, name FROM component_categories')
    cats = {}
    for row in cur.fetchall():
        if row.get('slug'):
            cats[row['slug']] = row['id']

    # Ensure peripheral categories exist
    for label, slug in (
        ('Mouse', 'mouse'),
        ('Keyboard', 'keyboard'),
        ('Monitor', 'monitor'),
    ):
        if slug not in cats:
            cur.execute(
                'INSERT INTO component_categories (name, slug) VALUES (%s, %s)',
                (label, slug),
            )
            conn.commit()
            cats[slug] = cur.lastrowid
            print(f'Created category: {label}')

    cur.execute('SELECT id, name, category_id, image_url FROM components')
    fixed = 0
    for row in cur.fetchall():
        slug = infer_slug(row['name'])
        if not slug or slug not in cats:
            continue
        new_cat = cats[slug]
        url = (row.get('image_url') or '').lower()
        bad_url = not url or 'cabinet' in url or 'case' in url or 'gs-logo' in url or 'hero-build' in url
        needs_cat = row['category_id'] != new_cat
        if needs_cat or bad_url:
            new_url = None if bad_url else row.get('image_url')
            cur.execute(
                'UPDATE components SET category_id = %s, image_url = %s WHERE id = %s',
                (new_cat, new_url, row['id']),
            )
            fixed += 1
            print(f"Fixed #{row['id']} {row['name']} -> {slug}")

    conn.commit()
    cur.close()
    conn.close()
    print(f'Done. Updated {fixed} row(s). Upload images in Admin → Components → Edit.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
