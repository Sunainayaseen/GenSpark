"""
Seed approved vendors into local genspark_erp (if table is empty).

Run: backend\\.venv\\Scripts\\python scripts\\seed_vendors_local.py

Requires: roles (vendor), users table. Creates vendor users + vendors + sample stock links.
"""
from __future__ import annotations

from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=True)

import mysql.connector
from mysql.connector import Error as MySQLError

VENDOR_SEED = (
    ('ProWave Traders', 'Lahore', '+92 333 1122445'),
    ('Digital Point PK', 'Karachi', '+92 321 445577'),
    ('SmartTech Hub', 'Islamabad', '+92 321 9876654'),
    ('NextWave Computers', 'Lahore', '+92 300 9988799'),
    ('PrimeTech World', 'Karachi', '+92 312 5566889'),
    ('Future Electronics', 'Islamabad', '+92 334 6677990'),
    ('Mega Systems', 'Karachi', '+92 300 7654432'),
    ('Pak Smart Solutions', 'Lahore', '+92 345 1234578'),
)


def connect():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'genspark_erp'),
    )


def ensure_vendor_role(cur) -> int:
    cur.execute("SELECT id FROM roles WHERE name = 'vendor' LIMIT 1")
    row = cur.fetchone()
    if row:
        return int(row[0])
    cur.execute("INSERT INTO roles (name) VALUES ('vendor')")
    return int(cur.lastrowid)


def main() -> int:
    cn = connect()
    cur = cn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM vendors WHERE approval_status = 'approved'")
        approved = int(cur.fetchone()[0])
        if approved > 0:
            print(f'Skip: already {approved} approved vendor(s) in local DB.')
            cur.execute(
                'SELECT id, shop_name, city FROM vendors WHERE approval_status = %s ORDER BY id',
                ('approved',),
            )
            for row in cur.fetchall():
                print(f'  - id={row[0]} {row[1]} ({row[2]})')
            return 0

        role_id = ensure_vendor_role(cur)
        print(f'Using vendor role_id={role_id}')

        for idx, (shop, city, phone) in enumerate(VENDOR_SEED, start=1):
            email = f'vendor{idx}@genspark.local'
            cur.execute('SELECT id FROM users WHERE email = %s LIMIT 1', (email,))
            user_row = cur.fetchone()
            if user_row:
                user_id = int(user_row[0])
            else:
                # Placeholder hash — vendors log in via admin reset in production
                cur.execute(
                    """
                    INSERT INTO users (name, email, password_hash, role_id, status)
                    VALUES (%s, %s, %s, %s, 'active')
                    """,
                    (shop, email, 'genspark-local-vendor-seed', role_id),
                )
                user_id = int(cur.lastrowid)

            cur.execute(
                """
                INSERT INTO vendors (user_id, shop_name, city, phone, approval_status)
                VALUES (%s, %s, %s, %s, 'approved')
                """,
                (user_id, shop, city, phone),
            )
            vendor_id = int(cur.lastrowid)
            print(f'Added vendor id={vendor_id} {shop}')

        # Link each vendor to first N components with stock
        cur.execute(
            'SELECT id, price FROM components WHERE stock > 0 ORDER BY id LIMIT 80'
        )
        components = cur.fetchall()
        cur.execute('SELECT id FROM vendors WHERE approval_status = %s', ('approved',))
        vendor_ids = [int(r[0]) for r in cur.fetchall()]

        links = 0
        for vid in vendor_ids:
            for comp_id, price in components[:12]:
                cur.execute(
                    """
                    INSERT IGNORE INTO vendor_components (vendor_id, component_id, quantity, price)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (vid, int(comp_id), 10, price),
                )
                links += cur.rowcount

        cn.commit()
        print(f'Done. vendor_components rows added/kept: {links}')
        return 0
    except MySQLError as exc:
        cn.rollback()
        print('MySQL error:', exc)
        return 1
    finally:
        cur.close()
        cn.close()


if __name__ == '__main__':
    raise SystemExit(main())
