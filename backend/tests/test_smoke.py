"""Smoke tests for the GenSpark backend.

These cover the three layers a reviewer cares about most:
  1. the server is up (health endpoint),
  2. routing/auth redirect works,
  3. a real DB-backed API endpoint returns seeded data.

Run from the backend/ folder:  python -m pytest
"""
from app import db
from app.models import Component, ComponentCategory


def test_health_endpoint_is_ok(client):
    """The lightweight /health check responds 200 OK (no DB, no templates)."""
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.data == b'OK'


def test_root_redirects_to_login(client):
    """Unauthenticated root should redirect into the auth/login flow."""
    resp = client.get('/')
    assert resp.status_code in (301, 302)
    assert '/auth/login' in resp.headers['Location']


def test_components_search_returns_seeded_component(client, db_session):
    """Seeding a component makes it discoverable via /api/components/search."""
    category = ComponentCategory(name='Graphics Card', slug='gpu')
    db_session.add(category)
    db_session.flush()  # assign category.id

    db_session.add(Component(
        name='GeForce RTX 4070 Test Card',
        category_id=category.id,
        price=180000,
        stock=5,
    ))
    db_session.commit()

    resp = client.get('/api/components/search?q=RTX 4070')
    assert resp.status_code == 200

    payload = resp.get_json()
    names = [c['name'] for c in (payload.get('components') or payload.get('results') or [])]
    assert any('RTX 4070' in n for n in names), payload
