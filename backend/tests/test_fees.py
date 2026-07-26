"""Money-flow tests — order-level assembly fee (app/services/fees.py).

These pin the rule behind audit fix C1: assembly is charged ONLY for an
assemble-able PC (a CPU AND a motherboard present), never for lone accessories.
The configurator estimate, checkout, and order creation all rely on this rule
agreeing, so the customer is shown exactly what they are charged.

Run from the backend/ folder:  python -m pytest
"""
import pytest

from app.services.fees import needs_assembly, assembly_fee_for, ASSEMBLY_FEE_PKR


# --- MF-ASM: assembly-fee applicability -------------------------------------

def test_cpu_plus_motherboard_is_assemble_able():
    """MF-ASM-01 — CPU + motherboard ⇒ assembly fee applies."""
    names = ['AMD Ryzen 7 7700 Processor', 'ASUS B650 Motherboard']
    assert needs_assembly(names) is True
    assert assembly_fee_for(names) == ASSEMBLY_FEE_PKR


def test_motherboard_by_chipset_token_counts():
    """MF-ASM-02 — a board named only by chipset (B760) is still detected."""
    assert needs_assembly(['Intel Core i5-13400', 'MSI B760 Gaming']) is True


def test_cpu_only_no_assembly():
    """MF-ASM-03 — a CPU with no motherboard is not an assemble-able PC."""
    assert needs_assembly(['AMD Ryzen 7 7700 Processor']) is False
    assert assembly_fee_for(['AMD Ryzen 7 7700 Processor']) == 0.0


def test_accessories_only_no_assembly():
    """MF-ASM-04 — RAM / SSD / mouse alone are never charged assembly."""
    assert needs_assembly(['Corsair 16GB DDR5 RAM', 'Samsung 1TB NVMe SSD']) is False
    assert assembly_fee_for(['Logitech USB Mouse']) == 0.0


@pytest.mark.parametrize('names', [[], [None, ''], ['', '   ']])
def test_empty_or_blank_no_assembly(names):
    """MF-ASM-05 — empty / blank item names are handled gracefully (no fee)."""
    assert needs_assembly(names) is False
    assert assembly_fee_for(names) == 0.0


def test_case_model_number_is_not_mistaken_for_motherboard():
    """MF-ASM-06 (regression) — a case model like 'NZXT H510' matches the bare
    [B/X/H/Z/A]+3digits chipset pattern but is NOT a motherboard; a CPU + that
    case alone must never be charged assembly."""
    assert needs_assembly(['Intel Core i5-13400 Processor', 'NZXT H510 Flow Case']) is False
    assert assembly_fee_for(['Intel Core i5-13400 Processor', 'NZXT H510 Flow Case']) == 0.0
