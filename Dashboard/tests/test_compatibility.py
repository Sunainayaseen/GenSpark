"""Rule-based compatibility engine tests (app/services/compatibility.py).

Components are faked by name only (specs=None) so `validate_build` exercises the
real `hardware_specs.derive_specs` classification — exactly the live path the
recommender uses. Covers socket/DDR/PSU rules and audit fix M3 (cooler socket
support is now derived from the name instead of being a universal no-op).

Run from the Dashboard/ folder:  python -m pytest
"""
from types import SimpleNamespace

from app.services.compatibility import validate_build


def _part(name):
    """A minimal stand-in for a Component row: validate_build only reads .name/.specs."""
    return SimpleNamespace(name=name, specs=None)


def _check(result, rule):
    for c in result['checks']:
        if c['rule'] == rule:
            return c
    return None


# --- CMP-OK: a coherent build validates -------------------------------------

def test_compatible_am5_build_passes():
    """CMP-OK-01 — Ryzen 7000 + B650 + DDR5 is fully compatible."""
    res = validate_build({
        'CPU': _part('AMD Ryzen 7 7700 Processor'),
        'Motherboard': _part('ASUS B650 Motherboard'),
        'RAM': _part('Corsair 16GB DDR5 RAM'),
    })
    assert res['compatible'] is True
    sock = _check(res, 'CPU ↔ Motherboard socket')
    assert sock and sock['status'] == 'pass'


# --- CMP-FAIL: hard incompatibilities are caught ----------------------------

def test_socket_mismatch_fails():
    """CMP-FAIL-01 — an Intel (LGA1700) CPU on an AM5 board fails the socket rule."""
    res = validate_build({
        'CPU': _part('Intel Core i5-13400 Processor'),
        'Motherboard': _part('ASUS B650 Motherboard'),
    })
    assert res['compatible'] is False
    sock = _check(res, 'CPU ↔ Motherboard socket')
    assert sock and sock['status'] == 'fail'


def test_ddr_generation_mismatch_fails():
    """CMP-FAIL-02 — DDR4 RAM cannot run on a DDR5 (B650) board."""
    res = validate_build({
        'Motherboard': _part('ASUS B650 Motherboard'),
        'RAM': _part('Corsair 16GB DDR4 RAM'),
    })
    ddr = _check(res, 'Motherboard ↔ RAM generation')
    assert ddr and ddr['status'] == 'fail'
    assert res['compatible'] is False


# --- CMP-COOLER (audit fix M3): socket derived from the cooler name ----------

def test_named_socket_cooler_can_fail():
    """CMP-COOLER-01 — an AM4-only cooler fails on an Intel LGA1700 CPU.

    Before the fix every cooler claimed universal socket support, so this could
    never fail (a false negative). The socket is now parsed from the name.
    """
    res = validate_build({
        'CPU': _part('Intel Core i5-13400 Processor'),   # LGA1700
        'Cooler': _part('AM4 Tower CPU Cooler'),          # AMD AM4 only
    })
    cooler = _check(res, 'CPU ↔ Cooler socket')
    assert cooler and cooler['status'] == 'fail'


def test_generic_oem_cooler_still_passes():
    """CMP-COOLER-02 — a generic OEM cooler (no platform in its name) stays
    broadly compatible, so legitimate builds are not falsely failed."""
    res = validate_build({
        'CPU': _part('Intel Core i5-13400 Processor'),
        'Cooler': _part('HP CPU Cooling Fan'),
    })
    cooler = _check(res, 'CPU ↔ Cooler socket')
    assert cooler and cooler['status'] == 'pass'
