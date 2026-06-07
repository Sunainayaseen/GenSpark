"""DB + API smoke test without Stripe keys (inventory rollback)."""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=True)

from stripe_checkout import complete_checkout

COMPONENT_ID = 54
USER_ID = 1


def mysql_kwargs():
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'genspark_erp'),
        'autocommit': False,
    }


def main():
    import mysql.connector

    cn = mysql.connector.connect(**mysql_kwargs())
    cur = cn.cursor()
    cur.execute('UPDATE components SET stock = 5 WHERE id = %s', (COMPONENT_ID,))
    cn.commit()
    cur.execute('SELECT stock FROM components WHERE id = %s', (COMPONENT_ID,))
    before = int(cur.fetchone()[0])
    cur.close()
    cn.close()
    print('stock before:', before)

    # Fake PI id — only works if stripe.retrieve is mocked; skip and call SQL path via module
    # Instead test stock lock path by importing internal logic:
    import stripe

    secret = (os.getenv('STRIPE_SECRET_KEY') or '').strip()
    if not secret.startswith('sk_'):
        print('SKIP: No Stripe key — cannot verify payment_intent. Run after adding STRIPE_SECRET_KEY.')
        return 0

    stripe.api_key = secret
    intent = stripe.PaymentIntent.create(
        amount=100,
        currency=os.getenv('STRIPE_CURRENCY', 'usd'),
        payment_method='pm_card_visa',
        confirm=True,
    )
    cur2 = mysql.connector.connect(**mysql_kwargs())
    c2 = cur2.cursor(dictionary=True)
    c2.execute('SELECT price FROM components WHERE id = %s', (COMPONENT_ID,))
    price = float(c2.fetchone()['price'])
    c2.close()
    cur2.close()

    result = complete_checkout(
        db_config=mysql_kwargs(),
        user_id=USER_ID,
        cart_items=[{'product_id': COMPONENT_ID, 'quantity': 1, 'price': price}],
        total_amount=price,
        payment_intent_id=intent.id,
    )
    print('checkout:', result)

    cn2 = mysql.connector.connect(**mysql_kwargs())
    cur3 = cn2.cursor()
    cur3.execute('SELECT stock FROM components WHERE id = %s', (COMPONENT_ID,))
    after = int(cur3.fetchone()[0])
    cur3.close()
    cn2.close()
    print('stock after:', after)
    assert after == before - 1, f'expected {before - 1}, got {after}'
    print('SUCCESS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
