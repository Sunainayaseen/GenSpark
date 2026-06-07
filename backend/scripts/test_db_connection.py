"""Quick local MySQL check — run: backend\\.venv\\Scripts\\python scripts\\test_db_connection.py"""
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
print(f"Connecting to {cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['database']}")
cn = mysql.connector.connect(**cfg)
cur = cn.cursor()
cur.execute('SELECT COUNT(*) FROM components')
n = cur.fetchone()[0]
print(f"components rows: {n}")
cur.close()
cn.close()
print('OK — local MySQL connected')
