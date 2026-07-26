"""Order-level service fees — single source of truth for the backend.

Assembly is charged like shipping: an ORDER-LEVEL fee, never a cart line item
(a synthetic line would break vendor-split, which requires every item to have a
vendor, and the component/stock lookups). It applies only when the order is an
assemble-able PC — i.e. it contains a CPU AND a motherboard. Lone accessories
(a single RAM stick, SSD, etc.) are not charged assembly.

Mirrors the React configurator's flat ASSEMBLY_FEE so that the amount shown in
the configurator/checkout equals the amount actually charged at order time.
"""
import re

ASSEMBLY_FEE_PKR = 5000.0
# Flat shipping charged whenever the cart has at least one line — single source of
# truth for every checkout path (COD, Stripe full payment, COD advance deposit).
SHIPPING_FEE_PKR = 2000.0
# Fraction of the order total collected up-front for Cash-on-Delivery orders.
COD_ADVANCE_RATE = 0.30

_CPU_RE = re.compile(r'(processor|ryzen|core\s?i\d|\bcpu\b|athlon|xeon|core\s*ultra)', re.I)
_MOBO_WORD_RE = re.compile(r'(motherboard|mainboard)', re.I)
# A bare "[B/X/H/Z/A]+3digits" token (e.g. B650, H510) is a real chipset name, but it
# is ALSO a real case-model pattern (e.g. NZXT H510, Cooler Master H500) — so on its
# own it is not reliable proof of a motherboard. Only trust it next to a brand that
# actually makes motherboards, never on the bare token alone.
_MOBO_CHIPSET_RE = re.compile(r'\b[bxhza]\d{3}\b', re.I)
_MOBO_BRAND_RE = re.compile(r'\b(asus|msi|gigabyte|aorus|asrock|biostar|evga|colorful)\b', re.I)


def _is_motherboard_name(name) -> bool:
    n = name or ''
    if _MOBO_WORD_RE.search(n):
        return True
    return bool(_MOBO_BRAND_RE.search(n) and _MOBO_CHIPSET_RE.search(n))


def needs_assembly(item_names) -> bool:
    """True when the items form an assemble-able PC (CPU + motherboard present)."""
    names = [n or '' for n in item_names]
    has_cpu = any(_CPU_RE.search(n) for n in names)
    has_mobo = any(_is_motherboard_name(n) for n in names)
    return has_cpu and has_mobo


def assembly_fee_for(item_names) -> float:
    """Flat assembly fee for these item names (0 when it isn't a full PC build)."""
    return ASSEMBLY_FEE_PKR if needs_assembly(item_names) else 0.0
