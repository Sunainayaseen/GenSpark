"""Inspect vendors table in local genspark_erp."""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=True)

import mysql.connector

cn = mysql.connector.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'root'),
    password=os.getenv('DB_PASSWORD', ''),
    database=os.getenv('DB_NAME', 'genspark_erp'),
)
cur = cn.cursor(dictionary=True)
for table in ('users', 'vendors', 'vendor_components'):
    cur.execute(f'SELECT COUNT(*) AS n FROM {table}')
    print(table, cur.fetchone()['n'])
cur.execute(
    'SELECT approval_status, COUNT(*) AS c FROM vendors GROUP BY approval_status'
)
print('approval_status:', cur.fetchall())
cur.execute(
    'SELECT id, shop_name, city, phone, approval_status FROM vendors ORDER BY id LIMIT 15'
)
for row in cur.fetchall() or []:
    print(row)
cur.close()
cn.close()
