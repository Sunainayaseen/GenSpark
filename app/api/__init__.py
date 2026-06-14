"""
API module initialization and blueprint registration.
"""

from flask import Blueprint

# Create the main API blueprint
api_bp = Blueprint('api', __name__)

# Import route blueprints to register them
from app.api.routes import (
    health_routes,
    db_routes,
    build_routes,
    component_routes,
)


def register_api_blueprints(app):
    """Register all API blueprints with the Flask app."""
    app.register_blueprint(health_routes.bp)
    app.register_blueprint(db_routes.bp)
    app.register_blueprint(build_routes.bp)
    app.register_blueprint(component_routes.bp)
