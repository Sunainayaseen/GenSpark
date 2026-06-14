#!/usr/bin/env python3
"""
Remove a vendor permanently from the database (CLI).

Usage (from this folder):
  python remove_vendor.py                    # removes "Demo PC Store" if found
  python remove_vendor.py "Demo PC Store"
  python remove_vendor.py 1                  # by numeric id

Requires: Flask app context (same as run.py).
"""
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(_script_dir)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from app import create_app, db
from app.models import Vendor
from app.utils.vendor_delete import permanently_delete_vendor


def main():
    app = create_app(os.getenv('FLASK_ENV', 'development'))
    arg = (sys.argv[1] if len(sys.argv) > 1 else '').strip()

    with app.app_context():
        vendor = None
        if not arg:
            vendor = Vendor.query.filter_by(shop_name='Demo PC Store').first()
            if not vendor:
                print('No vendor specified and "Demo PC Store" not found. Usage: python remove_vendor.py <id or shop name>')
                sys.exit(1)
        elif arg.isdigit():
            vendor = Vendor.query.get(int(arg))
        else:
            vendor = Vendor.query.filter(Vendor.shop_name.ilike(arg.strip())).first()

        if not vendor:
            print('Vendor not found.')
            sys.exit(1)

        print(f'Removing vendor id={vendor.id} shop_name={vendor.shop_name!r} ...')
        ok, err = permanently_delete_vendor(vendor.id)
        if ok:
            print('Done. Vendor removed from database.')
        else:
            print(f'Failed: {err}')
            sys.exit(1)


if __name__ == '__main__':
    main()
