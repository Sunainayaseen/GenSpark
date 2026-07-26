"""White-box tests for the DB-driven build recommender and component search.

These seed a small in-stock catalog into the in-memory test DB and exercise:
  * _select_components / _recommend_from_catalog  (WB-SEL-01..08)
  * /api/components/search filters                (WB-SCH-01..02)

Run from the backend/ folder:  python -m pytest
"""
import pytest

from app import db
from app.models import Component, ComponentCategory
from app.api.ai_build_routes import _select_components, _recommend_from_catalog


# --- catalog seeding helpers ------------------------------------------------

def _cat(name, slug):
    c = ComponentCategory(name=name, slug=slug)
    db.session.add(c)
    db.session.flush()
    return c


def _comp(name, category, price, stock=5):
    db.session.add(Component(name=name, category_id=category.id, price=price, stock=stock))


def _seed_am5_catalog():
    """A coherent AMD AM5 catalog plus an OEM part that must be excluded."""
    cpu = _cat('Processor', 'cpu')
    gpu = _cat('Graphics Card', 'gpu')
    mobo = _cat('Motherboard', 'motherboard')
    ram = _cat('RAM', 'ram')
    storage = _cat('Storage', 'storage')
    psu = _cat('PSU', 'psu')
    case = _cat('Case', 'case')

    _comp('AMD Ryzen 7 7700 Processor', cpu, 80_000)
    _comp('Dell OptiPlex i5 Processor', cpu, 30_000)   # OEM — must be excluded
    _comp('NVIDIA GeForce RTX 4070', gpu, 180_000)
    _comp('ASUS B650 Motherboard', mobo, 30_000)
    _comp('Corsair 16GB DDR5 RAM', ram, 12_000)
    _comp('Samsung 1TB NVMe SSD', storage, 10_000)
    _comp('Corsair 650W Power Supply Gold', psu, 15_000)
    _comp('NZXT Mid Tower Case', case, 8_000)
    db.session.commit()


# --- WB-SEL: component selection logic --------------------------------------

def test_platform_matching_am5(db_session):
    """WB-SEL-01 — a Ryzen 7000 CPU is paired with an AM5 (B650) board."""
    _seed_am5_catalog()
    selected = _select_components(Component, ComponentCategory, 'gaming', 500_000)
    assert 'AMD Ryzen' in selected['CPU'].name
    assert 'B650' in selected['Motherboard'].name


def test_platform_matching_lga1700(db_session):
    """WB-SEL-02 — an Intel Core CPU is paired with an LGA1700 (B760) board."""
    cpu = _cat('Processor', 'cpu')
    mobo = _cat('Motherboard', 'motherboard')
    ram = _cat('RAM', 'ram')
    _comp('Intel Core i5-13400 Processor', cpu, 60_000)
    _comp('MSI B760 Motherboard', mobo, 28_000)
    _comp('Corsair 16GB DDR5 RAM', ram, 12_000)
    db.session.commit()

    selected = _select_components(Component, ComponentCategory, 'gaming', 300_000)
    assert 'Core i5' in selected['CPU'].name
    assert 'B760' in selected['Motherboard'].name


def test_required_types_present(db_session):
    """WB-SEL-04 — with ample budget every required slot is filled."""
    _seed_am5_catalog()
    selected = _select_components(Component, ComponentCategory, 'gaming', 500_000)
    for slot in ('CPU', 'GPU', 'Motherboard', 'RAM', 'Storage', 'PSU', 'Case'):
        assert slot in selected, f'missing slot {slot}'


def test_office_build_excludes_discrete_gpu(db_session):
    """WB-SEL-05 — an office build skips the discrete GPU (uses iGPU)."""
    _seed_am5_catalog()
    selected = _select_components(Component, ComponentCategory, 'office', 100_000)
    assert 'GPU' not in selected


def test_oem_systems_excluded(db_session):
    """WB-SEL-06 — OEM prebuilt parts (Dell OptiPlex) never get selected."""
    _seed_am5_catalog()
    selected = _select_components(Component, ComponentCategory, 'gaming', 500_000)
    assert 'OptiPlex' not in selected['CPU'].name


def test_empty_catalog_returns_none(db_session):
    """WB-SEL-07 — an empty catalog yields no recommendation (caller falls back)."""
    assert _select_components(Component, ComponentCategory, 'gaming', 100_000) == {}
    assert _recommend_from_catalog('gaming', '100k') is None


def test_build_components_carry_real_ids(db_session):
    """WB-SEL-08 — recommendation parts expose a real component_id for the cart."""
    _seed_am5_catalog()
    rec = _recommend_from_catalog('gaming', '300k')
    assert rec is not None and rec['source'] == 'rules-db'
    assert rec['build_components'], 'expected at least one component'
    for item in rec['build_components']:
        assert isinstance(item['component_id'], int) and item['component_id'] > 0


# --- WB-SCH: component search filters ----------------------------------------

def test_search_default_ordering_in_stock_first(client, db_session):
    """WB-SCH-01 — default search lists in-stock items (out-of-stock ranked last)."""
    cat = _cat('Graphics Card', 'gpu')
    _comp('RTX 4060 In Stock', cat, 90_000, stock=10)
    _comp('RTX 4060 Out Of Stock', cat, 80_000, stock=0)
    db.session.commit()

    resp = client.get('/api/components/search')
    assert resp.status_code == 200
    items = resp.get_json().get('components') or []
    assert items, 'expected components in default search'
    # The top result must be an in-stock item.
    assert items[0]['stock'] > 0


def test_search_category_filter(client, db_session):
    """WB-SCH-02 — category_id narrows results to that category only."""
    gpu = _cat('Graphics Card', 'gpu')
    cpu = _cat('Processor', 'cpu')
    _comp('GeForce RTX 4070', gpu, 180_000)
    _comp('AMD Ryzen 7 7700', cpu, 80_000)
    db.session.commit()

    resp = client.get(f'/api/components/search?category_id={gpu.id}')
    assert resp.status_code == 200
    names = [c['name'] for c in (resp.get_json().get('components') or [])]
    assert names and all('Ryzen' not in n for n in names)
