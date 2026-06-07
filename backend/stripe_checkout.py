"""Stripe payment intent + transactional checkout against genspark_erp MySQL."""
from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import mysql.connector
import stripe
from dotenv import load_dotenv
from mysql.connector import Error as MySQLError

# Load backend/.env when this module is imported directly (scripts/tests)
load_dotenv(Path(__file__).resolve().parent / '.env', override=True)

# Debug: Verify STRIPE_SECRET_KEY is loaded
stripe_key = os.environ.get('STRIPE_SECRET_KEY')
print(f'(GenSpark stripe_checkout) STRIPE_SECRET_KEY loaded: {stripe_key[:10] if stripe_key else "None"}...')

# Configure stripe with the API key
if stripe_key:
    stripe.api_key = stripe_key


def stripe_configured() -> bool:
    key = (os.environ.get('STRIPE_SECRET_KEY') or '').strip()
    return bool(key) and key.startswith('sk_') and 'your_' not in key.lower()


def stripe_config_status() -> dict[str, Any]:
    """Safe diagnostics for logs (never returns the secret)."""
    key = (os.environ.get('STRIPE_SECRET_KEY') or '').strip()
    if not key:
        reason = 'STRIPE_SECRET_KEY missing or empty'
    elif not key.startswith('sk_'):
        reason = f'key must start with sk_ (got prefix {key[:7]!r}...)'
    elif 'your_' in key.lower():
        reason = 'placeholder key from .env.example (contains your_)'
    else:
        reason = 'ok'
    return {
        'configured': stripe_configured(),
        'reason': reason,
        'key_len': len(key),
        'currency': stripe_currency(),
    }


def stripe_currency() -> str:
    return (os.environ.get('STRIPE_CURRENCY') or 'pkr').strip().lower()


def stripe_amount_minor_units(amount_major: float) -> int:
    """Stripe amounts: smallest currency unit (cents / paisa)."""
    return max(1, int(round(float(amount_major) * 100)))


def create_payment_intent(amount_major: float) -> dict[str, Any]:
    if not stripe_configured():
        raise RuntimeError('STRIPE_SECRET_KEY is not configured in backend/.env')
    minor = stripe_amount_minor_units(amount_major)
    currency = stripe_currency()
    print(
        f'(GenSpark stripe_checkout) PaymentIntent.create amount_major={amount_major} '
        f'minor={minor} currency={currency}'
    )
    intent = stripe.PaymentIntent.create(
        amount=minor,
        currency=currency,
        automatic_payment_methods={'enabled': True},
    )
    print(
        f'(GenSpark stripe_checkout) PaymentIntent id={intent["id"]} '
        f'status={intent["status"]}'
    )
    return {'clientSecret': intent['client_secret']}


def _next_order_number() -> str:
    return f'ORD-{datetime.utcnow().strftime("%Y%m%d%H%M%S%f")}'


def _table_has_column(cursor, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (table, column),
    )
    row = cursor.fetchone()
    return bool(row and int(row[0]) > 0)


def complete_checkout(
    *,
    db_config: dict,
    user_id: int,
    cart_items: list[dict],
    total_amount: float,
    payment_intent_id: str,
    shipping_address: str = '',
    shipping_fee: float = 0.0,
) -> dict[str, Any]:
    if not stripe_configured():
        raise RuntimeError('STRIPE_SECRET_KEY is not configured')

    if not payment_intent_id:
        raise ValueError('payment_intent_id is required')

    intent = stripe.PaymentIntent.retrieve(payment_intent_id)
    if intent.get('status') != 'succeeded':
        raise ValueError(f'Payment not completed (status={intent.get("status")})')

    if not cart_items:
        raise ValueError('Cart is empty')

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    try:
        if _table_has_column(cursor, 'orders', 'stripe_txn_id'):
            cursor.execute(
                'SELECT id FROM orders WHERE stripe_txn_id = %s LIMIT 1',
                (payment_intent_id,),
            )
            existing = cursor.fetchone()
            if existing:
                return {
                    'success': True,
                    'message': 'Order already recorded for this payment.',
                    'order_id': int(existing['id']),
                    'duplicate': True,
                }

        for item in cart_items:
            product_id = int(item['product_id'])
            qty = int(item['quantity'])
            if qty <= 0:
                raise ValueError(f'Invalid quantity for product {product_id}')
            cursor.execute(
                'SELECT id, name, stock, price FROM components WHERE id = %s FOR UPDATE',
                (product_id,),
            )
            product = cursor.fetchone()
            if not product:
                raise ValueError(f'Component id {product_id} not found')
            if int(product['stock'] or 0) < qty:
                raise ValueError(f'Insufficient stock for {product["name"]}')

        has_payment_status = _table_has_column(cursor, 'orders', 'payment_status')
        has_stripe_txn = _table_has_column(cursor, 'orders', 'stripe_txn_id')

        order_cols = ['user_id', 'order_number', 'total_amount', 'status', 'shipping_address', 'shipping_fee', 'notes']
        order_vals = [
            user_id,
            _next_order_number(),
            Decimal(str(round(float(total_amount), 2))),
            'pending',
            (shipping_address or '').strip() or 'Pakistan',
            Decimal(str(round(float(shipping_fee), 2))),
            f'payment_method=stripe;stripe_pi={payment_intent_id}',
        ]
        if has_payment_status:
            order_cols.append('payment_status')
            order_vals.append('Paid')
        if has_stripe_txn:
            order_cols.append('stripe_txn_id')
            order_vals.append(payment_intent_id)

        placeholders = ', '.join(['%s'] * len(order_cols))
        cursor.execute(
            f'INSERT INTO orders ({", ".join(order_cols)}) VALUES ({placeholders})',
            tuple(order_vals),
        )
        order_id = int(cursor.lastrowid)

        for item in cart_items:
            product_id = int(item['product_id'])
            qty = int(item['quantity'])
            unit_price = Decimal(str(item.get('price') or 0))
            line_total = unit_price * qty

            cursor.execute(
                'UPDATE components SET stock = stock - %s WHERE id = %s',
                (qty, product_id),
            )
            try:
                cursor.execute(
                    'UPDATE products SET stock_quantity = stock_quantity - %s WHERE id = %s',
                    (qty, product_id),
                )
            except MySQLError:
                pass
            cursor.execute(
                'SELECT name FROM components WHERE id = %s LIMIT 1',
                (product_id,),
            )
            comp = cursor.fetchone()
            comp_name = (comp or {}).get('name') or f'Component #{product_id}'

            cursor.execute(
                """
                INSERT INTO order_items (
                    order_id, item_type, item_id, component_name,
                    vendor_id, quantity, unit_price, total_price
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    order_id,
                    'component',
                    product_id,
                    comp_name,
                    item.get('vendor_id'),
                    qty,
                    unit_price,
                    line_total,
                ),
            )

        cursor.execute(
            """
            INSERT INTO order_status_history (order_id, status, notes)
            VALUES (%s, %s, %s)
            """,
            (order_id, 'pending', 'Stripe payment received — awaiting admin approval'),
        )

        if _table_has_column(cursor, 'payments', 'id'):
            cursor.execute(
                """
                INSERT INTO payments (order_id, amount, payment_status, payment_method, transaction_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    order_id,
                    Decimal(str(round(float(total_amount), 2))),
                    'completed',
                    'stripe',
                    payment_intent_id,
                ),
            )

        cursor.execute('SELECT id FROM cart WHERE user_id = %s LIMIT 1', (user_id,))
        cart_row = cursor.fetchone()
        if cart_row:
            cursor.execute('DELETE FROM cart_items WHERE cart_id = %s', (int(cart_row['id']),))

        conn.commit()
        return {
            'success': True,
            'message': 'Transaction complete!',
            'order_id': order_id,
            'order_number': order_vals[1],
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
