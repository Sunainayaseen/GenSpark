"""Seed products + components for Stripe integration test."""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=True)

import mysql.connector

cfg = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'genspark_erp'),
}

cn = mysql.connector.connect(**cfg)
cur = cn.cursor()

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS products (
        id INT AUTO_INCREMENT PRIMARY KEY,
        product_name VARCHAR(255) NOT NULL,
        stock_quantity INT NOT NULL CHECK (stock_quantity >= 0)
    )
    """
)
cur.execute(
    """
    INSERT INTO products (id, product_name, stock_quantity)
    VALUES (1, 'NVIDIA RTX 4090 GPU', 5)
    ON DUPLICATE KEY UPDATE product_name=VALUES(product_name), stock_quantity=VALUES(stock_quantity)
    """
)

for stmt in (
    "ALTER TABLE orders ADD COLUMN payment_status VARCHAR(50) DEFAULT 'Pending'",
    "ALTER TABLE orders ADD COLUMN stripe_txn_id VARCHAR(255) NULL",
):
    try:
        cur.execute(stmt)
    except mysql.connector.Error as exc:
        if exc.errno != 1060:  # duplicate column
            print(f'Note: {exc}')

try:
    cur.execute('ALTER TABLE orders ADD UNIQUE INDEX uq_orders_stripe_txn (stripe_txn_id)')
except mysql.connector.Error as exc:
    if exc.errno not in (1061, 1060):
        print(f'Note index: {exc}')

# Catalog starts at id 54+ on this project — keep stock at 5 for integration tests
cur.execute('UPDATE components SET stock = 5 WHERE id = 54')
cn.commit()

cur.execute('SELECT id, product_name, stock_quantity FROM products WHERE id = 1')
print('products:', cur.fetchone())
cur.execute('SELECT id, name, stock, price FROM components WHERE id = 54')
print('components:', cur.fetchone())

cur.close()
cn.close()
print('DB setup OK')
