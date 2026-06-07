import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=True)

import mysql.connector

email = (sys.argv[1] if len(sys.argv) > 1 else 'shamim@gmail.com').strip().lower()
cn = mysql.connector.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'root'),
    password=os.getenv('DB_PASSWORD', ''),
    database=os.getenv('DB_NAME', 'genspark_erp'),
)
cur = cn.cursor(dictionary=True)
cur.execute(
    """
    SELECT u.id, u.email, u.name, u.status, u.must_change_password,
           LENGTH(u.password_hash) AS hash_len, r.name AS role
    FROM users u
    LEFT JOIN roles r ON r.id = u.role_id
    WHERE LOWER(u.email) = %s
    LIMIT 1
    """,
    (email,),
)
row = cur.fetchone()
print(row or 'NOT FOUND')
cur.close()
cn.close()
