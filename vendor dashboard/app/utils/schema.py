"""Database bootstrap and legacy column migrations (safe on empty Railway MySQL)."""
from sqlalchemy import text

from app import db


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
            for name in ('admin', 'vendor', 'customer'):
                db.session.add(Role(name=name))
            db.session.commit()
            print('(GenSpark) Seeded roles: admin, vendor, customer')

        if ComponentCategory.query.count() == 0:
            categories = [
                ('Processor', 'processor'),
                ('RAM', 'ram'),
                ('GPU', 'gpu'),
                ('Motherboard', 'motherboard'),
                ('Storage', 'storage'),
                ('PSU', 'psu'),
                ('Cabinet', 'cabinet'),
            ]
            for name, slug in categories:
                db.session.add(ComponentCategory(name=name, slug=slug))
            db.session.commit()
            print('(GenSpark) Seeded component categories')

        if not User.query.filter_by(email='admin@genspark.com').first():
            admin_role = Role.query.filter_by(name='admin').first()
            if admin_role:
                admin = User(name='Admin', email='admin@genspark.com', role_id=admin_role.id)
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                print('(GenSpark) Created admin: admin@genspark.com / admin123')

        if not User.query.filter_by(email='vendor@genspark.com').first():
            vendor_role = Role.query.filter_by(name='vendor').first()
            if vendor_role:
                vendor_user = User(
                    name='Vendor Demo',
                    email='vendor@genspark.com',
                    role_id=vendor_role.id,
                )
                vendor_user.set_password('vendor123')
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
                print('(GenSpark) Created vendor: vendor@genspark.com / vendor123')


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
