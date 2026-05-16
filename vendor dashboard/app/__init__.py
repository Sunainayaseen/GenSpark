# GenSpark - Flask Application Factory
from flask import Flask, request, make_response, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from flask_jwt_extended import JWTManager
from sqlalchemy import text
from config import config

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
csrf = CSRFProtect()
jwt = JWTManager()


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # CORS: allow React from localhost ya LAN IP (e.g. 192.168.x.x:5178)
    def _is_allowed_origin(origin):
        if not origin:
            return False
        return (
            origin.startswith('http://localhost:') or
            origin.startswith('http://127.0.0.1:') or
            origin.startswith('http://192.168.') or
            origin.startswith('http://10.')
        )

    @app.after_request
    def _cors_after_request(response):
        origin = request.environ.get('HTTP_ORIGIN')
        if _is_allowed_origin(origin):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    db.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    jwt.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints
    from app.auth import auth_bp
    from app.admin import admin_bp
    from app.vendor import vendor_bp
    from app.api import api_bp
    from app.ecommerce import ecom_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(vendor_bp, url_prefix='/vendor')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(ecom_bp, url_prefix='/api/ecom')

    @app.template_filter('status_label')
    def status_label(value):
        """Convert machine status keys to readable labels for UI badges."""
        raw = str(value or '').strip().lower()
        labels = {
            'ready_to_dispatch': 'Completed',
            'admin-review': 'Admin Review',
            'pending_email': 'Pending Email Verification',
        }
        if raw in labels:
            return labels[raw]
        return raw.replace('_', ' ').replace('-', ' ').title() if raw else '-'

    # API routes are exempt from CSRF (use token/auth for security in production)
    csrf.exempt(api_bp)
    csrf.exempt(ecom_bp)

    # Lightweight DB schema guardrails for older databases (no Alembic here).
    # Fixes MySQL installs where cart_items.product_id was created NOT NULL.
    try:
        with app.app_context():
            if db.engine.dialect.name == 'mysql':
                with db.engine.connect() as conn:
                    r = conn.execute(text(
                        "SELECT IS_NULLABLE, COLUMN_TYPE "
                        "FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() "
                        "AND TABLE_NAME = 'cart_items' "
                        "AND COLUMN_NAME = 'product_id'"
                    )).fetchone()
                    if r and str(r[0]).upper() == 'NO':
                        # Keep same type, only relax nullability.
                        col_type = r[1] or 'INT'
                        conn.execute(text(f"ALTER TABLE cart_items MODIFY product_id {col_type} NULL"))
                        conn.commit()
    except Exception as e:
        # Non-fatal: app can still run; cart may error until DB is fixed.
        print('Note: cart_items.product_id nullability migration skipped:', e)

    try:
        with app.app_context():
            if db.engine.dialect.name == 'mysql':
                with db.engine.connect() as conn:
                    r = conn.execute(text(
                        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vendor_orders' "
                        "AND COLUMN_NAME = 'proof_approved'"
                    )).fetchone()
                    if not r:
                        conn.execute(text(
                            "ALTER TABLE vendor_orders ADD COLUMN proof_approved TINYINT(1) NOT NULL DEFAULT 1"
                        ))
                        conn.commit()
            elif db.engine.dialect.name == 'sqlite':
                with db.engine.connect() as conn:
                    r = conn.execute(text("PRAGMA table_info(vendor_orders)"))
                    cols = [row[1] for row in r]
                    if 'proof_approved' not in cols:
                        conn.execute(text(
                            "ALTER TABLE vendor_orders ADD COLUMN proof_approved BOOLEAN NOT NULL DEFAULT 1"
                        ))
                        conn.commit()
    except Exception as e:
        print('Note: vendor_orders.proof_approved migration skipped:', e)

    try:
        with app.app_context():
            if db.engine.dialect.name == 'mysql':
                with db.engine.connect() as conn:
                    r = conn.execute(text(
                        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'orders' "
                        "AND COLUMN_NAME = 'shipping_fee'"
                    )).fetchone()
                    if not r:
                        conn.execute(text(
                            "ALTER TABLE orders ADD COLUMN shipping_fee DECIMAL(12,2) NOT NULL DEFAULT 0"
                        ))
                        conn.commit()
            elif db.engine.dialect.name == 'sqlite':
                with db.engine.connect() as conn:
                    r = conn.execute(text("PRAGMA table_info(orders)"))
                    cols = [row[1] for row in r]
                    if 'shipping_fee' not in cols:
                        conn.execute(text(
                            "ALTER TABLE orders ADD COLUMN shipping_fee NUMERIC(12,2) NOT NULL DEFAULT 0"
                        ))
                        conn.commit()
    except Exception as e:
        print('Note: orders.shipping_fee migration skipped:', e)

    @app.route('/health')
    def health():
        """Minimal response – no DB, no template. Use to verify server is Flask."""
        r = make_response('OK', 200)
        r.headers['Content-Type'] = 'text/plain; charset=utf-8'
        return r

    @app.route('/')
    def index():
        """Keep legacy behavior: root opens login/dashboard flow."""
        return redirect(url_for('auth.login'))

    @app.errorhandler(500)
    def internal_server_error(e):
        """Return JSON for /api/* so React can show a clear message instead of parsing HTML."""
        if request.path.startswith('/api'):
            try:
                db.session.rollback()
            except Exception:
                pass
            return jsonify({
                'success': False,
                'error': 'Server error. Open the Flask terminal (vendor dashboard) to see the full traceback, then restart with: python run.py',
            }), 500
        return (
            '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Server error</title></head>'
            '<body style="font-family:sans-serif;padding:2rem;"><h1>Server error</h1>'
            '<p>Check the Flask console for details.</p></body></html>',
            500,
        )

    @app.errorhandler(404)
    def not_found(e):
        from flask import make_response
        html = (
            '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Not found</title></head><body style="font-family:sans-serif;padding:2rem;max-width:560px;">'
            '<h1>Page not found</h1>'
            '<p>If you opened <strong>127.0.0.1:5000</strong>, use these links:</p>'
            '<ul><li><a href="/">Home</a></li>'
            '<li><a href="/auth/login">Login</a></li>'
            '<li><a href="/admin/dashboard">Admin dashboard</a></li>'
            '<li><a href="/api/ping">API ping</a></li></ul>'
            '<p style="color:#666;">Make sure you started Flask with <strong>START-FLASK.bat</strong> or <code>python run.py</code> from the <strong>vendor dashboard</strong> folder (not from backend folder).</p>'
            '</body></html>'
        )
        return make_response(html, 404)

    return app
