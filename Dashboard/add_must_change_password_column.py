"""One-time script: add must_change_password column to users table if missing. Run once: python add_must_change_password_column.py"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db
from sqlalchemy import text
app = create_app()
with app.app_context():
    try:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0'))
            conn.commit()
        print('Column must_change_password added.')
    except Exception as e:
        if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
            print('Column already exists.')
        else:
            print('Error:', e)
