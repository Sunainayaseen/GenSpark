# GenSpark - Flask Application Factory
import os

from flask import Flask, request, make_response, jsonify, redirect, url_for
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from sqlalchemy import text
from config import config, build_sqlalchemy_database_uri, _use_sqlite_from_env

# React (Vite) + Vercel production — extend via GENSPARK_CORS_ORIGINS=comma,separated,urls
DEFAULT_CORS_ORIGINS = [
    'https://genspark-frontend.vercel.app',
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:5174',
    'http://127.0.0.1:5174',
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
# Real-time engine. threading mode = no eventlet/gevent native dep (Windows-safe).
socketio = SocketIO(async_mode='threading', cors_allowed_origins=_cors_origins())


def model_warmup(app):
    """Load YOLO weights (and run one tiny inference) at startup so the first real
    /api/detect/component request is fast instead of paying the cold-start cost.

    Runs in a background daemon thread: never blocks app boot, never crashes the
    server if weights are missing. Disable with GENSPARK_YOLO_WARMUP=0.
    """
    if os.getenv('GENSPARK_YOLO_WARMUP', '1').strip().lower() in ('0', 'false', 'no'):
        return

    import threading

    def _warm():
        try:
            import numpy as np
            from app.yolo_weights import get_yolo_model

            model, path = get_yolo_model()
            # One dummy frame primes torch/CUDA graphs so request #1 isn't slow.
            model.predict(source=np.zeros((640, 640, 3), dtype='uint8'), verbose=False)
            app.logger.info('YOLO model warmed up: %s', path)
        except FileNotFoundError as exc:
            app.logger.warning('YOLO warmup skipped (weights missing): %s', exc)
        except Exception as exc:
            app.logger.warning('YOLO warmup skipped: %s', exc)

    threading.Thread(target=_warm, name='yolo-warmup', daemon=True).start()


_INSECURE_SECRET_KEYS = {'genspark-erp-secret-key', 'your-secret-key-change-in-production'}


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    if config_name == 'production' and app.config.get('SECRET_KEY') in _INSECURE_SECRET_KEYS:
        # Fail fast rather than silently sign sessions/JWTs with a secret that is
        # sitting in plain sight in this repo's own source/.env.example.
        raise RuntimeError(
            'Refusing to start in production with the default/placeholder SECRET_KEY. '
            'Set a real SECRET_KEY environment variable (e.g. python -c "import secrets; print(secrets.token_hex(32))").'
        )
    if app.config.get('TESTING'):
        # Isolated in-memory DB shared across the app's connections (StaticPool),
        # so pytest never touches the real MySQL/SQLite data.
        from sqlalchemy.pool import StaticPool
        app.config['USE_SQLITE'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'connect_args': {'check_same_thread': False},
            'poolclass': StaticPool,
        }
    else:
        # Resolve DB after env is loaded (never at config.py import — breaks Railway build)
        app.config['USE_SQLITE'] = _use_sqlite_from_env()
        app.config['SQLALCHEMY_DATABASE_URI'] = build_sqlalchemy_database_uri()

    CORS(
        app,
        supports_credentials=True,
        origins=_cors_origins(),
        allow_headers=['Content-Type', 'Authorization', 'X-GenSpark-Model-Reload-Key'],
        methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
        intercept_exceptions=True,
    )

    db.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    jwt.init_app(app)
    socketio.init_app(app, cors_allowed_origins=_cors_origins(), async_mode='threading')
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    # Register Socket.IO event handlers (connect / join_room).
    from app import realtime  # noqa: F401

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints
    from app.auth import auth_bp
    from app.admin import admin_bp
    from app.vendor import vendor_bp
    from app.rider import rider_bp
    from app.api import api_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(vendor_bp, url_prefix='/vendor')
    app.register_blueprint(rider_bp, url_prefix='/rider')
    app.register_blueprint(api_bp, url_prefix='/api')

    @app.context_processor
    def inject_template_globals():
        """Make the current year available to every template (footers, etc.)."""
        from datetime import datetime
        return {'current_year': datetime.now().year}

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

    if app.config.get('TESTING'):
        # Plain create_all on the in-memory DB — skip MySQL-specific ALTER migrations.
        with app.app_context():
            db.create_all()
    else:
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

    @app.errorhandler(413)
    def request_too_large(e):
        if request.path.startswith('/api'):
            return jsonify({
                'success': False,
                'error': 'File is too large. Maximum upload size is 16 MB.',
            }), 413
        return make_response('<h1>File too large</h1><p>Maximum upload size is 16 MB.</p>', 413)

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

    # Warm the detector in the background so the first detection request is fast.
    model_warmup(app)

    return app
