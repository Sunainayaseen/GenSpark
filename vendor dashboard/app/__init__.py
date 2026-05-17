# GenSpark - Flask Application Factory
import os

from flask import Flask, request, make_response, jsonify, redirect, url_for
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from flask_jwt_extended import JWTManager
from sqlalchemy import text
from config import config, build_sqlalchemy_database_uri, _use_sqlite_from_env

# React (Vite) + Vercel production — extend via GENSPARK_CORS_ORIGINS=comma,separated,urls
DEFAULT_CORS_ORIGINS = [
    'https://genspark-frontend.vercel.app',
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:4173',
    'http://127.0.0.1:4173',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]


def _cors_origins():
    origins = list(DEFAULT_CORS_ORIGINS)
    extra = os.getenv('GENSPARK_CORS_ORIGINS', '')
    for item in extra.split(','):
        item = item.strip()
        if item and item not in origins:
            origins.append(item)
    return origins

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
csrf = CSRFProtect()
jwt = JWTManager()


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    # Resolve DB after env is loaded (never at config.py import — breaks Railway build)
    app.config['USE_SQLITE'] = _use_sqlite_from_env()
    app.config['SQLALCHEMY_DATABASE_URI'] = build_sqlalchemy_database_uri()

    CORS(
        app,
        supports_credentials=True,
        origins=_cors_origins(),
        allow_headers=['Content-Type', 'Authorization', 'X-GenSpark-Model-Reload-Key'],
        methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    )

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

    # Fresh Railway MySQL: create_all + seed first; ALTER only if tables already exist.
    from app.utils.schema import ensure_database_schema, apply_legacy_migrations
    try:
        ensure_database_schema(app)
        apply_legacy_migrations(app)
    except Exception as e:
        print('Note: database schema bootstrap skipped:', e)

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
        if request.path.startswith('/api'):
            return jsonify({
                'success': False,
                'error': 'Not found',
                'path': request.path,
            }), 404
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
