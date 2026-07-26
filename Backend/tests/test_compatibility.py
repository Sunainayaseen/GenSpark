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


# --- CMP-CONN: GPU <-> PSU connector check is a real comparison, not a no-op --

def test_underpowered_connectors_fail_even_with_enough_wattage():
    """CMP-CONN-01 — a high-wattage-but-few-connector PSU still fails the
    connector check for a card that needs more 8-pin-equivalents than it has.
    A 4090 needs 3x8-pin (native 16-pin via adapter); a 550W PSU only has 2x8-pin."""
    res = validate_build({
        'GPU': _part('NVIDIA RTX 4090 Graphics Card'),
        'PSU': _part('Corsair 650W 80+ Gold PSU'),
    })
    conn = _check(res, 'GPU ↔ PSU connectors')
    assert conn and conn['status'] == 'fail'


def test_sufficient_connectors_pass():
    """CMP-CONN-02 — a 1000W PSU (4x8-pin + 16-pin) covers a 4090's requirement."""
    res = validate_build({
        'GPU': _part('NVIDIA RTX 4090 Graphics Card'),
        'PSU': _part('Corsair 1000W 80+ Gold PSU'),
    })
    conn = _check(res, 'GPU ↔ PSU connectors')
    assert conn and conn['status'] == 'pass'


# --- CMP-COOLER-CASE: cooler height vs case clearance ------------------------

def test_air_cooler_fits_default_case_clearance():
    """CMP-COOLER-CASE-01 — a standard air cooler fits a standard case; proves
    the rule is now evaluated (previously it did not exist at all)."""
    res = validate_build({
        'Cooler': _part('Cooler Master Hyper Air Tower Cooler'),
        'Case': _part('Mid Tower Case'),
    })
    clearance = _check(res, 'Cooler ↔ Case clearance')
    assert clearance and clearance['status'] == 'pass'


def test_oversized_cooler_exceeds_case_clearance_fails():
    """CMP-COOLER-CASE-02 — a cooler taller than the case's clearance fails,
    using explicit structured specs (bypasses name-derivation to test the
    comparison itself, since no catalog-name-derived case is narrow enough
    to trigger this with today's default height/clearance figures)."""
    tall_cooler = SimpleNamespace(
        name='Oversized Air Tower Cooler',
        specs={'kind': 'cooler', 'height_mm': 200, 'sockets': [], 'tdp_rating_w': 220, 'confident': True},
    )
    tight_case = SimpleNamespace(
        name='Small Form Factor Case',
        specs={'kind': 'case', 'cooler_height_mm': 150, 'gpu_clearance_mm': 300,
               'form_factor': 'ITX', 'supported_form_factors': ['ITX'], 'confident': True},
    )
    res = validate_build({'Cooler': tall_cooler, 'Case': tight_case})
    clearance = _check(res, 'Cooler ↔ Case clearance')
    assert clearance and clearance['status'] == 'fail'
    assert res['compatible'] is False


# --- CMP-PCIE: PCIe generation mismatch is a warning, never a hard failure --

def test_pcie_gen_mismatch_is_a_warning_not_a_failure():
    """CMP-PCIE-01 — a Gen5 GPU on a Gen4 board still works (backward
    compatible), so the build must remain 'compatible' with only a warning."""
    res = validate_build({
        'GPU': _part('NVIDIA RTX 5070 Ti Graphics Card'),       # PCIe Gen5
        'Motherboard': _part('ASUS B550 Motherboard'),           # PCIe Gen4 board
    })
    pcie = _check(res, 'GPU ↔ Motherboard PCIe generation')
    assert pcie and pcie['status'] == 'warn'
    assert res['compatible'] is True


# --- CMP-BIOS: CPU generation vs motherboard chipset BIOS ceiling -----------

def test_newer_cpu_on_older_chipset_warns_bios_update():
    """CMP-BIOS-01 — a Ryzen 9000 CPU on a B650 board (launch BIOS covers up
    to 7000-series) needs a BIOS update — a warning, never a hard failure,
    since flashing the BIOS resolves it without new hardware."""
    res = validate_build({
        'CPU': _part('AMD Ryzen 7 9700X Processor'),
        'Motherboard': _part('ASUS B650 Motherboard'),
    })
    bios = _check(res, 'CPU ↔ Motherboard BIOS support')
    assert bios and bios['status'] == 'warn'
    assert res['compatible'] is True


def test_matching_cpu_gen_and_chipset_passes_bios_check():
    """CMP-BIOS-02 — a Ryzen 7000 CPU on the same B650 board is within its
    stock BIOS support."""
    res = validate_build({
        'CPU': _part('AMD Ryzen 7 7700 Processor'),
        'Motherboard': _part('ASUS B650 Motherboard'),
    })
    bios = _check(res, 'CPU ↔ Motherboard BIOS support')
    assert bios and bios['status'] == 'pass'
