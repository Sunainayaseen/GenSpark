"""
GenSpark Backend Application Factory

This is the refactored, production-ready application entry point.
Follows best practices with proper separation of concerns:
- Routes → Controllers → Services → Database
- Centralized response formatting
- Modular configuration
- Clean error handling
"""

import os
import logging
from pathlib import Path
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
APP_DIR = Path(__file__).resolve().parent.parent
load_dotenv(APP_DIR / '.env', override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def create_app(config_name='development'):
    """
    Application factory for GenSpark backend.
    
    Args:
        config_name: Configuration name (development or production)
    
    Returns:
        Flask application instance
    """
    app = Flask(__name__, instance_path=str(APP_DIR / 'instance'))
    
    # Configuration
    configure_app(app, config_name)
    
    # Extensions
    setup_cors(app)
    
    # Database
    from app.core.database import probe_db_connection
    ok, message, details = probe_db_connection()
    if ok:
        app.logger.info('✓ Database connected: %s', details)
    else:
        app.logger.warning('✗ Database connection failed (app continues): %s', message)
    
    # Routes and Blueprints
    register_blueprints(app)
    
    # Error Handlers
    register_error_handlers(app)
    
    # Health Check Route (root level)
    @app.route('/')
    def index():
        from app.core.responses import success
        return success(message='GenSpark Backend Ready')
    
    return app


def configure_app(app: Flask, config_name: str):
    """Configure Flask application."""
    app.config['ENV'] = config_name
    app.config['DEBUG'] = config_name == 'development'
    app.config['TESTING'] = False
    app.config['JSON_SORT_KEYS'] = False
    
    # Security
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'genspark-dev-secret-key')
    
    # Session
    app.config['SESSION_COOKIE_SECURE'] = config_name == 'production'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 7  # 7 days


def setup_cors(app: Flask):
    """Configure Cross-Origin Resource Sharing."""
    from app.common.constants import CORS_ORIGINS
    
    extra_origins = os.getenv('GENSPARK_CORS_ORIGINS', '').split(',')
    origins = CORS_ORIGINS + [o.strip() for o in extra_origins if o.strip()]
    
    CORS(
        app,
        resources={r'/api/*': {'origins': origins}},
        supports_credentials=True,
        allow_headers=['Content-Type', 'Authorization', 'X-Requested-With', 'Accept'],
        methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
        expose_headers=['Content-Type'],
        max_age=86400,
    )


def register_blueprints(app: Flask):
    """Register all API blueprints."""
    from app.api.routes import (
        health_routes,
        db_routes,
        build_routes,
        component_routes,
    )

    app.register_blueprint(health_routes.bp)
    app.register_blueprint(db_routes.bp)
    app.register_blueprint(build_routes.bp)
    app.register_blueprint(component_routes.bp)
    
    app.logger.info('✓ All API blueprints registered')


def register_error_handlers(app: Flask):
    """Register error handlers for standard HTTP errors."""
    from app.core.responses import not_found, server_error
    
    @app.errorhandler(404)
    def handle_404(error):
        return not_found('Endpoint not found')
    
    @app.errorhandler(500)
    def handle_500(error):
        app.logger.exception('Unhandled server error')
        return server_error('Internal server error')


if __name__ == '__main__':
    app = create_app('development')
    app.run(host='0.0.0.0', port=5000, debug=True)
