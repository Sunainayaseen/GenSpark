"""
GenSpark - Database initialization script.
Run: python init_db.py
Creates all tables and seeds roles + default admin user.
"""
import os
os.environ.setdefault('FLASK_ENV', 'development')

from sqlalchemy import text
from app import create_app, db
from app.models import Role, User, Vendor, ComponentCategory, ComponentBrand, Component, PcBuild, Cart

app = create_app()
with app.app_context():
    db.create_all()

    # Add brand_id to components if missing (safe migration)
    with db.engine.connect() as conn:
        try:
            if db.engine.dialect.name == 'sqlite':
                r = conn.execute(text("PRAGMA table_info(components)"))
                cols = [row[1] for row in r]
                if 'brand_id' not in cols:
                    conn.execute(text("ALTER TABLE components ADD COLUMN brand_id INTEGER REFERENCES brands(brand_id)"))
                    conn.commit()
            elif db.engine.dialect.name == 'mysql':
                r = conn.execute(text(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'components'"
                ))
                cols = {row[0] for row in r}
                if 'brand_id' not in cols:
                    conn.execute(text("ALTER TABLE components ADD COLUMN brand_id INT NULL, ADD FOREIGN KEY (brand_id) REFERENCES brands(brand_id)"))
                    conn.commit()
        except Exception as e:
            print('Note: brand_id migration skipped:', e)

        # Ensure pc_builds.stock exists (used for cart quantity limits)
        try:
            if db.engine.dialect.name == 'sqlite':
                r2 = conn.execute(text("PRAGMA table_info(pc_builds)"))
                cols2 = [row[1] for row in r2]
                if 'stock' not in cols2:
                    conn.execute(text("ALTER TABLE pc_builds ADD COLUMN stock INTEGER NOT NULL DEFAULT 25"))
                    conn.commit()
            elif db.engine.dialect.name == 'mysql':
                r2 = conn.execute(text(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'pc_builds'"
                ))
                cols2 = {row[0] for row in r2}
                if 'stock' not in cols2:
                    conn.execute(text("ALTER TABLE pc_builds ADD COLUMN stock INT NOT NULL DEFAULT 25"))
                    conn.commit()
        except Exception as e:
            print('Note: pc_builds.stock migration skipped:', e)

        # Multi-vendor cart fields migration.
        try:
            if db.engine.dialect.name == 'sqlite':
                r3 = conn.execute(text("PRAGMA table_info(cart_items)"))
                cols3 = [row[1] for row in r3]
                if 'item_type' not in cols3:
                    conn.execute(text("ALTER TABLE cart_items ADD COLUMN item_type VARCHAR(30) NOT NULL DEFAULT 'component'"))
                if 'pc_build_id' not in cols3:
                    conn.execute(text("ALTER TABLE cart_items ADD COLUMN pc_build_id INTEGER"))
                if 'component_id' not in cols3:
                    conn.execute(text("ALTER TABLE cart_items ADD COLUMN component_id INTEGER"))
                if 'component_name' not in cols3:
                    conn.execute(text("ALTER TABLE cart_items ADD COLUMN component_name VARCHAR(150)"))
                if 'vendor_id' not in cols3:
                    conn.execute(text("ALTER TABLE cart_items ADD COLUMN vendor_id INTEGER"))
                if 'unit_price' not in cols3:
                    conn.execute(text("ALTER TABLE cart_items ADD COLUMN unit_price NUMERIC(12,2) DEFAULT 0"))
                conn.commit()
            elif db.engine.dialect.name == 'mysql':
                r3 = conn.execute(text(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cart_items'"
                ))
                cols3 = {row[0] for row in r3}
                # One ALTER per column — more reliable than a single multi-ADD on some MySQL setups.
                migrations = []
                # Older schema had product_id NOT NULL; allow NULL for component-only items.
                try:
                    r_nullable = conn.execute(text(
                        "SELECT IS_NULLABLE, COLUMN_TYPE "
                        "FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() "
                        "AND TABLE_NAME = 'cart_items' "
                        "AND COLUMN_NAME = 'product_id'"
                    )).fetchone()
                    if r_nullable and str(r_nullable[0]).upper() == 'NO':
                        col_type = r_nullable[1] or 'INT'
                        conn.execute(text(f"ALTER TABLE cart_items MODIFY product_id {col_type} NULL"))
                        conn.commit()
                except Exception as e:
                    print('Note: cart_items.product_id nullability migration skipped:', e)
                if 'item_type' not in cols3:
                    migrations.append("ALTER TABLE cart_items ADD COLUMN item_type VARCHAR(30) NOT NULL DEFAULT 'component'")
                if 'pc_build_id' not in cols3:
                    migrations.append("ALTER TABLE cart_items ADD COLUMN pc_build_id INT NULL")
                if 'component_id' not in cols3:
                    migrations.append("ALTER TABLE cart_items ADD COLUMN component_id INT NULL")
                if 'component_name' not in cols3:
                    migrations.append("ALTER TABLE cart_items ADD COLUMN component_name VARCHAR(150) NULL")
                if 'vendor_id' not in cols3:
                    migrations.append("ALTER TABLE cart_items ADD COLUMN vendor_id INT NULL")
                if 'unit_price' not in cols3:
                    migrations.append("ALTER TABLE cart_items ADD COLUMN unit_price DECIMAL(12,2) DEFAULT 0")
                for stmt in migrations:
                    conn.execute(text(stmt))
                if migrations:
                    conn.commit()
        except Exception as e:
            print('Note: cart_items multi-vendor migration skipped:', e)

        # Order item vendor mapping migration.
        try:
            if db.engine.dialect.name == 'sqlite':
                r4 = conn.execute(text("PRAGMA table_info(order_items)"))
                cols4 = [row[1] for row in r4]
                if 'component_name' not in cols4:
                    conn.execute(text("ALTER TABLE order_items ADD COLUMN component_name VARCHAR(150)"))
                if 'vendor_id' not in cols4:
                    conn.execute(text("ALTER TABLE order_items ADD COLUMN vendor_id INTEGER"))
                conn.commit()
            elif db.engine.dialect.name == 'mysql':
                r4 = conn.execute(text(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'order_items'"
                ))
                cols4 = {row[0] for row in r4}
                alters = []
                if 'component_name' not in cols4:
                    alters.append("ADD COLUMN component_name VARCHAR(150) NULL")
                if 'vendor_id' not in cols4:
                    alters.append("ADD COLUMN vendor_id INT NULL")
                if alters:
                    conn.execute(text("ALTER TABLE order_items " + ", ".join(alters)))
                    conn.commit()
        except Exception as e:
            print('Note: order_items vendor mapping migration skipped:', e)

        # vendor_orders proof_approved (admin must approve vendor completion photo)
        try:
            if db.engine.dialect.name == 'sqlite':
                r5 = conn.execute(text("PRAGMA table_info(vendor_orders)"))
                cols5 = [row[1] for row in r5]
                if 'proof_approved' not in cols5:
                    conn.execute(text(
                        "ALTER TABLE vendor_orders ADD COLUMN proof_approved BOOLEAN NOT NULL DEFAULT 1"
                    ))
                    conn.commit()
            elif db.engine.dialect.name == 'mysql':
                r5 = conn.execute(text(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vendor_orders' "
                    "AND COLUMN_NAME = 'proof_approved'"
                )).fetchone()
                if not r5:
                    conn.execute(text(
                        "ALTER TABLE vendor_orders ADD COLUMN proof_approved TINYINT(1) NOT NULL DEFAULT 1"
                    ))
                    conn.commit()
        except Exception as e:
            print('Note: vendor_orders.proof_approved migration skipped:', e)

    # If using MySQL and any key table has old schema, drop all app tables and recreate
    if not app.config.get('USE_SQLITE') and db.engine.dialect.name == 'mysql':
        with db.engine.connect() as conn:
            need_recreate = False
            for table_name, required_cols in (
                ('users', {'password_hash', 'role_id', 'status', 'must_change_password', 'created_at'}),
                ('vendors', {'user_id', 'shop_name', 'approval_status'}),
            ):
                try:
                    r = conn.execute(text(
                        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"
                    ), {'t': table_name})
                    existing = {row[0] for row in r}
                except Exception:
                    existing = set()
                if required_cols - existing:
                    need_recreate = True
                    break
            if need_recreate:
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                for table in db.metadata.sorted_tables:
                    conn.execute(text(f"DROP TABLE IF EXISTS `{table.name}`"))
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                conn.commit()
                print('Dropped old app tables (schema mismatch); recreating.')
                db.create_all()

    # Seed roles
    for name in ['admin', 'vendor', 'customer']:
        if not Role.query.filter_by(name=name).first():
            db.session.add(Role(name=name))
    db.session.commit()
    # Seed component categories
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
        if not ComponentCategory.query.filter_by(slug=slug).first():
            db.session.add(ComponentCategory(name=name, slug=slug))
    db.session.commit()
    # Default admin user (if not exists)
    if not User.query.filter_by(email='admin@genspark.com').first():
        admin_role = Role.query.filter_by(name='admin').first()
        admin = User(name='Admin', email='admin@genspark.com', role_id=admin_role.id)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Created admin user: admin@genspark.com / admin123')
    # Default vendor user (if not exists)
    if not User.query.filter_by(email='vendor@genspark.com').first():
        vendor_role = Role.query.filter_by(name='vendor').first()
        vendor_user = User(name='Vendor Demo', email='vendor@genspark.com', role_id=vendor_role.id)
        vendor_user.set_password('vendor123')
        db.session.add(vendor_user)
        db.session.flush()
        vendor_profile = Vendor(
            user_id=vendor_user.id,
            shop_name='Demo PC Store',
            city='Mumbai',
            address='Sample address',
            phone='9876543210',
            approval_status='approved'
        )
        db.session.add(vendor_profile)
        db.session.commit()
        print('Created vendor user: vendor@genspark.com / vendor123')

    # Seed a few PcBuild products (so cart add-to-cart works with existing mock UI ids)
    default_builds = [
        {
            'id': 1,
            'name': 'Gaming — Performance Build',
            'build_type': 'Performance',
            'description': 'Demo build seeded for cart functionality.',
            'total_price': 125000,
            'image_url': '/gs-logo.png',
            'stock': 25,
            'is_active': True,
        },
        {
            'id': 2,
            'name': 'Gaming — Balanced Build',
            'build_type': 'Balanced',
            'description': 'Demo build seeded for cart functionality.',
            'total_price': 95000,
            'image_url': '/gs-logo.png',
            'stock': 25,
            'is_active': True,
        },
        {
            'id': 3,
            'name': 'Gaming — Budget Build',
            'build_type': 'Budget',
            'description': 'Demo build seeded for cart functionality.',
            'total_price': 65000,
            'image_url': '/gs-logo.png',
            'stock': 25,
            'is_active': True,
        },
    ]
    for b in default_builds:
        if not PcBuild.query.filter_by(id=b['id']).first():
            db.session.add(PcBuild(**b))
    db.session.commit()

    print('Database initialized successfully.')
