"""
End-to-end Stripe + MySQL integration test (run while backend is on :5000).

Requires real test keys in backend/.env:
  STRIPE_SECRET_KEY=sk_test_...
  STRIPE_CURRENCY=usd   (use usd for smallest test charge; pkr also works if enabled)

Usage:
  python scripts/integration_test_stripe.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=True)

import mysql.connector
import stripe

API = os.getenv('INTEGRATION_API_BASE', 'http://127.0.0.1:5000')
COMPONENT_ID = int(os.getenv('INTEGRATION_COMPONENT_ID', '54'))
TEST_AMOUNT = float(os.getenv('INTEGRATION_TEST_AMOUNT', '1.00'))


def http_json(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    url = f'{API.rstrip("/")}{path}'
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or '{}')
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {'error': raw}
        return exc.code, payload


def db_state():
    cfg = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'genspark_erp'),
    }
    cn = mysql.connector.connect(**cfg)
    cur = cn.cursor(dictionary=True)
    cur.execute('SELECT id, name, stock FROM components WHERE id = %s', (COMPONENT_ID,))
    comp = cur.fetchone()
    cur.execute('SELECT id, product_name, stock_quantity FROM products WHERE id = 1')
    prod = cur.fetchone()
    cur.execute(
        'SELECT id, payment_status, stripe_txn_id, total_amount FROM orders ORDER BY id DESC LIMIT 3'
    )
    orders = cur.fetchall()
    cur.close()
    cn.close()
    return comp, prod, orders


def main() -> int:
    secret = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
    if not secret or 'your_' in secret.lower() or not secret.startswith('sk_'):
        print('FAIL: Set STRIPE_SECRET_KEY in backend/.env (sk_test_... from Stripe Dashboard)')
        return 1

    stripe.api_key = secret
    currency = (os.getenv('STRIPE_CURRENCY') or 'usd').lower()

    print('--- DB before ---')
    comp, prod, orders = db_state()
    print('component:', comp)
    print('product:', prod)
    print('recent orders:', orders)

    if not comp:
        print(f'FAIL: component id {COMPONENT_ID} not found')
        return 1

    stock_before = int(comp['stock'] or 0)
    if stock_before < 1:
        print(f'Seeding component {COMPONENT_ID} stock to 5...')
        cn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'genspark_erp'),
        )
        cur = cn.cursor()
        cur.execute('UPDATE components SET stock = 5 WHERE id = %s', (COMPONENT_ID,))
        cn.commit()
        cur.close()
        cn.close()
        stock_before = 5

    print('\n--- API health ---')
    code, body = http_json('GET', '/health')
    print(code, body)
    if code != 200:
        print('FAIL: backend not running on', API)
        return 1

    print('\n--- create-payment-intent ---')
    code, body = http_json('POST', '/api/create-payment-intent', {'amount': TEST_AMOUNT})
    print(code, body)
    if code != 200 or not body.get('clientSecret'):
        print('FAIL: could not create payment intent')
        return 1

    print('\n--- Stripe confirm (test card) ---')
    intent = stripe.PaymentIntent.create(
        amount=max(1, int(round(TEST_AMOUNT * 100))),
        currency=currency,
        payment_method='pm_card_visa',
        confirm=True,
    )
    if intent.status != 'succeeded':
        print('FAIL: PaymentIntent status', intent.status)
        return 1
    print('PaymentIntent', intent.id, intent.status)

    unit_price = float(comp.get('price') or TEST_AMOUNT)
    cart_items = [
        {
            'product_id': COMPONENT_ID,
            'quantity': 1,
            'price': unit_price,
            'vendor_id': None,
        }
    ]

    print('\n--- complete-checkout ---')
    code, body = http_json(
        'POST',
        '/api/order/complete-checkout',
        {
            'user_id': 1,
            'items': cart_items,
            'total_amount': unit_price,
            'payment_intent_id': intent.id,
            'shipping_address': 'Integration Test Address',
            'shipping_fee': 0,
        },
    )
    print(code, json.dumps(body, indent=2))
    if code != 200 or not body.get('success'):
        print('FAIL: complete-checkout')
        return 1

    print('\n--- DB after ---')
    comp2, prod2, orders2 = db_state()
    print('component:', comp2)
    print('product:', prod2)
    print('recent orders:', orders2)

    stock_after = int((comp2 or {}).get('stock') or 0)
    if stock_after != stock_before - 1:
        print(f'FAIL: expected component stock {stock_before - 1}, got {stock_after}')
        return 1

    paid = any((o.get('payment_status') or '').lower() == 'paid' for o in orders2)
    if not paid:
        print('WARN: no order with payment_status=Paid in last 3 rows (check migration SQL)')

    print('\nSUCCESS: Integration test passed.')
    print(f'Order id: {body.get("order_id")}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
