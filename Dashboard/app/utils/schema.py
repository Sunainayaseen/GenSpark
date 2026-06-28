"""Database bootstrap and legacy column migrations (safe on empty Railway MySQL)."""
import os
import secrets

from sqlalchemy import text

from app import db


def _is_production():
    return os.getenv('FLASK_ENV', '').strip().lower() == 'production'


def _seed_password(default_password):
    """Dev: use the documented default. Production: generate a random one-time
    password (logged once) and force a change on first login, so no deploy ever
    ships with a publicly-known admin123/vendor123 credential."""
    if not _is_production():
        return default_password, False
    return secrets.token_urlsafe(12), True


def _table_exists(conn, table_name, dialect_name):
    if dialect_name == 'sqlite':
        row = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
            {'t': table_name},
        ).fetchone()
        return row is not None
    row = conn.execute(
        text(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"
        ),
        {'t': table_name},
    ).fetchone()
    return row is not None


def _column_exists(conn, table_name, column_name, dialect_name):
    if dialect_name == 'sqlite':
        rows = conn.execute(text(f"PRAGMA table_info({table_name})"))
        return column_name in [r[1] for r in rows]
    row = conn.execute(
        text(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
        ),
        {'t': table_name, 'c': column_name},
    ).fetchone()
    return row is not None


def ensure_database_schema(flask_app):
    """
    Create all tables from SQLAlchemy models (idempotent).
    Seed roles + default admin/vendor on a completely empty database.
    """
    from importlib import import_module
    import_module('app.models')  # register all models on metadata

    with flask_app.app_context():
        db.create_all()

        from app.models import Role, User, Vendor, ComponentCategory

        if Role.query.count() == 0:
            for name in ('admin', 'vendor', 'customer', 'rider'):
                db.session.add(Role(name=name))
            db.session.commit()
            print('(GenSpark) Seeded roles: admin, vendor, customer, rider')
        else:
            # Top up any role added after the first bootstrap (e.g. 'rider' on an
            # existing DB) so role-based login keeps working without a reset.
            existing = {r.name for r in Role.query.all()}
            added = [n for n in ('admin', 'vendor', 'customer', 'rider') if n not in existing]
            for name in added:
                db.session.add(Role(name=name))
            if added:
                db.session.commit()
                print('(GenSpark) Added missing roles:', ', '.join(added))

        if ComponentCategory.query.count() == 0:
            categories = [
                ('Processor', 'processor'),
                ('RAM', 'ram'),
                ('GPU', 'gpu'),
                ('Motherboard', 'motherboard'),
                ('Storage', 'storage'),
                ('PSU', 'psu'),
                ('Cabinet', 'cabinet'),
                ('Mouse', 'mouse'),
                ('Keyboard', 'keyboard'),
                ('Monitor', 'monitor'),
            ]
            for name, slug in categories:
                db.session.add(ComponentCategory(name=name, slug=slug))
            db.session.commit()
            print('(GenSpark) Seeded component categories')

        if not User.query.filter_by(email='admin@genspark.com').first():
            admin_role = Role.query.filter_by(name='admin').first()
            if admin_role:
                admin = User(name='Admin', email='admin@genspark.com', role_id=admin_role.id)
                password, generated = _seed_password('admin123')
                admin.set_password(password)
                admin.must_change_password = generated
                db.session.add(admin)
                db.session.commit()
                if generated:
                    print(f'(GenSpark) Created admin: admin@genspark.com / {password} — CHANGE ON FIRST LOGIN')
                else:
                    print('(GenSpark) Created admin: admin@genspark.com / admin123 (dev default)')

        if not User.query.filter_by(email='vendor@genspark.com').first():
            vendor_role = Role.query.filter_by(name='vendor').first()
            if vendor_role:
                vendor_user = User(
                    name='Vendor Demo',
                    email='vendor@genspark.com',
                    role_id=vendor_role.id,
                )
                password, generated = _seed_password('vendor123')
                vendor_user.set_password(password)
                vendor_user.must_change_password = generated
                db.session.add(vendor_user)
                db.session.flush()
                db.session.add(
                    Vendor(
                        user_id=vendor_user.id,
                        shop_name='Demo PC Store',
                        city='Karachi',
                        address='Sample address',
                        phone='9876543210',
                        approval_status='approved',
                    )
                )
                db.session.commit()
                if generated:
                    print(f'(GenSpark) Created vendor: vendor@genspark.com / {password} — CHANGE ON FIRST LOGIN')
                else:
                    print('(GenSpark) Created vendor: vendor@genspark.com / vendor123 (dev default)')


def apply_legacy_migrations(flask_app):
    """ALTER existing tables only — skip if table missing (fresh Railway DB)."""
    with flask_app.app_context():
        dialect = db.engine.dialect.name
        with db.engine.connect() as conn:
            # cart_items.product_id nullability
            if _table_exists(conn, 'cart_items', dialect):
                try:
                    if dialect == 'mysql':
                        r = conn.execute(text(
                            "SELECT IS_NULLABLE, COLUMN_TYPE "
                            "FROM INFORMATION_SCHEMA.COLUMNS "
                            "WHERE TABLE_SCHEMA = DATABASE() "
                            "AND TABLE_NAME = 'cart_items' AND COLUMN_NAME = 'product_id'"
                        )).fetchone()
                        if r and str(r[0]).upper() == 'NO':
                            col_type = r[1] or 'INT'
                            conn.execute(text(
                                f"ALTER TABLE cart_items MODIFY product_id {col_type} NULL"
                            ))
                            conn.commit()
                except Exception as e:
                    print('Note: cart_items.product_id migration skipped:', e)

            # vendor_orders.proof_approved (old DBs without column)
            if _table_exists(conn, 'vendor_orders', dialect):
                try:
                    if not _column_exists(conn, 'vendor_orders', 'proof_approved', dialect):
                        if dialect == 'mysql':
                            conn.execute(text(
                                "ALTER TABLE vendor_orders "
                                "ADD COLUMN proof_approved TINYINT(1) NOT NULL DEFAULT 1"
                            ))
                        else:
                            conn.execute(text(
                                "ALTER TABLE vendor_orders "
                                "ADD COLUMN proof_approved BOOLEAN NOT NULL DEFAULT 1"
                            ))
                        conn.commit()
                except Exception as e:
                    print('Note: vendor_orders.proof_approved migration skipped:', e)

            # orders.shipping_fee (old DBs without column)
            if _table_exists(conn, 'orders', dialect):
                try:
                    if not _column_exists(conn, 'orders', 'shipping_fee', dialect):
                        if dialect == 'mysql':
                            conn.execute(text(
                                "ALTER TABLE orders "
                                "ADD COLUMN shipping_fee DECIMAL(12,2) NOT NULL DEFAULT 0"
                            ))
                        else:
                            conn.execute(text(
                                "ALTER TABLE orders "
                                "ADD COLUMN shipping_fee NUMERIC(12,2) NOT NULL DEFAULT 0"
                            ))
                        conn.commit()
                except Exception as e:
                    print('Note: orders.shipping_fee migration skipped:', e)

            # delivery_assignments live-tracking columns (Leaflet rider tracking)
            if _table_exists(conn, 'delivery_assignments', dialect):
                tracking_cols = [
                    ('pickup_lat', 'DOUBLE', 'FLOAT'),
                    ('pickup_lng', 'DOUBLE', 'FLOAT'),
                    ('dropoff_lat', 'DOUBLE', 'FLOAT'),
                    ('dropoff_lng', 'DOUBLE', 'FLOAT'),
                    ('current_lat', 'DOUBLE', 'FLOAT'),
                    ('current_lng', 'DOUBLE', 'FLOAT'),
                    ('current_speed', 'DOUBLE', 'FLOAT'),
                    ('location_updated_at', 'DATETIME', 'DATETIME'),
                    ('tracking_active', 'TINYINT(1) NOT NULL DEFAULT 0', 'BOOLEAN NOT NULL DEFAULT 0'),
                    ('sim_mode', 'TINYINT(1) NOT NULL DEFAULT 0', 'BOOLEAN NOT NULL DEFAULT 0'),
                    ('sim_started_at', 'DATETIME', 'DATETIME'),
                    ('sim_duration_s', 'INT DEFAULT 180', 'INTEGER DEFAULT 180'),
                ]
                for col, mysql_type, sqlite_type in tracking_cols:
                    try:
                        if not _column_exists(conn, 'delivery_assignments', col, dialect):
                            col_type = mysql_type if dialect == 'mysql' else sqlite_type
                            conn.execute(text(
                                f"ALTER TABLE delivery_assignments ADD COLUMN {col} {col_type}"
                            ))
                            conn.commit()
                    except Exception as e:
                        print(f'Note: delivery_assignments.{col} migration skipped:', e)
