"""Shared pytest fixtures for the GenSpark backend.

The app is built with the 'testing' config, which uses an in-memory SQLite
database (see config.TestingConfig + create_app). Each test gets a fresh,
isolated DB — the real MySQL `genspark_erp` is never touched.
"""
import pytest

from app import create_app, db


@pytest.fixture()
def app():
    app = create_app('testing')
    yield app
    # Tear down the in-memory schema so tests stay isolated from each other.
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db_session(app):
    """An app context with the live db session for tests that seed/query data."""
    with app.app_context():
        yield db.session
