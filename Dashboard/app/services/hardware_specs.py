"""
Deterministic hardware-spec derivation.

The catalog stores parts as free-text names ("AMD Ryzen 5 5600G 6-Core Processor",
"ASUS ROG Strix X670E-E Gaming (ATX)"). The compatibility engine needs STRUCTURED
specs (socket, chipset, DDR generation, wattage, PCIe connectors, clearances, …) to
validate a build by rule instead of by guesswork.

`derive_specs(name)` parses a name into that structured form using deterministic
rules + small model lookup tables. It is the single source of truth used by BOTH:

  * seed_component_specs.py — to persist specs onto Component.specs (one-time), and
  * compatibility.py        — as a live fallback for any part not yet seeded.

Every value is derived from the name only (never guessed at random); unknown parts
return conservative defaults flagged with `confident: False` so the validator can
degrade gracefully instead of asserting a compatibility it cannot prove.

The returned dict always has a `kind` in:
    cpu | gpu | motherboard | ram | psu | case | cooler | storage | other
plus kind-specific fields documented inline below.
"""
from __future__ import annotations

import re

# Mobo form factors a case can physically take (largest → list of supported).
_CASE_FORM_SUPPORT = {
    'ATX': ['ATX', 'mATX', 'ITX'],
    'mATX': ['mATX', 'ITX'],
    'ITX': ['ITX'],
}

# --- GPU model table: (regex, length_mm, tdp_w, min_psu_w, pcie_power, pcie_gen) ---
# Figures are reference specs for the class; min_psu_w is the board-partner guidance.
_GPU_TABLE = (
    (r'rtx\s*4090',          336, 450, 850, '16-pin (3×8-pin adapter)', 4),
    (r'rtx\s*4070\s*ti\s*super', 304, 285, 750, '16-pin / 2×8-pin', 4),
    (r'rtx\s*5070\s*ti',     300, 300, 750, '16-pin / 2×8-pin', 5),
    (r'rtx\s*4070\s*ti',     305, 285, 700, '16-pin / 2×8-pin', 4),
    (r'rtx\s*4070',          242, 200, 650, '8-pin / 16-pin', 4),
    (r'rtx\s*4060\s*ti',     200, 165, 600, '8-pin', 4),
    (r'rtx\s*4060',          245, 115, 550, '8-pin', 4),
    (r'rtx\s*3060',          242, 170, 550, '8-pin', 4),
    (r'rtx\s*3050',          230, 130, 450, '8-pin', 4),
    (r'gtx\s*16\d0',         230, 120, 450, '8-pin', 3),
    (r'rx\s*7900',           320, 320, 800, '2×8-pin', 4),
    (r'rx\s*7800',           267, 263, 700, '2×8-pin', 4),
    (r'rx\s*7600',           204, 165, 550, '8-pin', 4),
)
_GPU_DEFAULT = (250, 200, 650, '8-pin', 4)

# --- CPU: socket + DDR + iGPU + TDP, by family/model. ---
_CPU_TDP = (
    (r'(i9|ryzen\s*9)', 120),
    (r'(i7|ryzen\s*7)', 105),
    (r'(i5|ryzen\s*5)', 65),
    (r'(i3|ryzen\s*3)', 65),
)


def _search(name, table, default):
    for pat, *vals in table:
        if re.search(pat, name, re.I):
            return vals[0] if len(vals) == 1 else vals
    return default


def _cpu_gen(n: str, socket: str | None) -> int | None:
    """Numeric CPU generation marker, used only for the BIOS-support advisory
    below — AMD: series thousand (7000/9000), Intel: generation number (12/13/14)."""
    if socket == 'AM5':
        m = re.search(r'\b([789])\d{3}', n)
        return int(m.group(1)) * 1000 if m else None
    if socket == 'AM4':
        m = re.search(r'\b([12345])\d{3}', n)
        return int(m.group(1)) * 1000 if m else None
    if socket == 'LGA1700':
        m = re.search(r'i[3579][\s-]?(\d{2})\d{3}', n)
        return int(m.group(1)) if m else None
    return None


def _cpu_specs(name: str) -> dict:
    n = name.lower()
    socket = chipset = None
    ddr: list[str] = []
    igpu = False
    confident = True

    if 'ryzen' in n or ('amd' in n and 'radeon' not in n):
        # AM5 = Ryzen 7000/8000/9000; AM4 = 5000/3000 and the 5600G APU.
        if re.search(r'\bryzen\s*\d\s*[789]\d{3}', n) or re.search(r'\b[789]\d{3}', n):
            socket, ddr = 'AM5', ['DDR5']
            igpu = not re.search(r'\b\d{3,4}f\b', n)        # only 'F' parts drop the iGPU
        else:
            socket, ddr = 'AM4', ['DDR4']
            igpu = bool(re.search(r'\b\d{3,4}ge?\b', n))    # 5600G / 5700GE have the iGPU
    elif 'core i' in n or 'intel' in n:
        socket = 'LGA1700'
        ddr = ['DDR4', 'DDR5']                              # board decides; both possible
        igpu = not re.search(r'\d{3,5}f\b', n)              # 13400F has none
        if 'elitedesk' in n or 'optiplex' in n or 'thinkcentre' in n:
            socket = None                                    # OEM proprietary board
            confident = False
    else:
        confident = False

    return {
        'kind': 'cpu', 'socket': socket, 'ddr': ddr, 'igpu': igpu,
        'tdp_w': _search(n, _CPU_TDP, 65), 'gen': _cpu_gen(n, socket),
        'confident': confident,
    }


# Max CPU series/generation a chipset's stock (launch) BIOS supports without a
# firmware update — not a hard block (a BIOS flash resolves it), so the
# compatibility engine surfaces this as a 'warn', never a 'fail'.
_BIOS_GEN_CEILING = {
    'X670': 7000, 'B650': 7000, 'X870': 9000, 'B850': 9000, 'A620': 9000,
    'Z690': 12, 'B660': 12, 'H610': 12, 'Z790': 14, 'B760': 14, 'B860': 14, 'Z890': 14,
}


def _mobo_specs(name: str) -> dict:
    n = name.lower()
    socket = chipset = None
    ddr: list[str] = []
    confident = True

    if re.search(r'\b(x870)', n):
        socket, chipset, ddr = 'AM5', 'X870', ['DDR5']
    elif re.search(r'\b(x670)', n):
        socket, chipset, ddr = 'AM5', 'X670', ['DDR5']
    elif re.search(r'\b(b650|b850|a620)', n):
        socket, chipset, ddr = 'AM5', re.search(r'\b(b650|b850|a620)', n).group(1).upper(), ['DDR5']
    elif re.search(r'\b(b550|a520|x570|b450)', n):
        socket, chipset, ddr = 'AM4', re.search(r'\b(b550|a520|x570|b450)', n).group(1).upper(), ['DDR4']
    elif re.search(r'\b(b760|z790|h610|b660|z690|b860|z890)', n):
        socket = 'LGA1700'
        chipset = re.search(r'\b(b760|z790|h610|b660|z690|b860|z890)', n).group(1).upper()
        ddr = ['DDR4'] if 'ddr4' in n else (['DDR5'] if 'ddr5' in n else ['DDR4', 'DDR5'])
    else:
        confident = False

    # Form factor + capability tier from chipset class.
    if re.search(r'\bitx\b|mini-?itx', n):
        form = 'ITX'
    elif re.search(r'\bm-?atx\b|micro', n):
        form = 'mATX'
    else:
        form = 'ATX'
    high = chipset and re.match(r'(X|Z)', chipset)
    return {
        'kind': 'motherboard', 'socket': socket, 'chipset': chipset, 'ddr': ddr,
        'form_factor': form,
        'ram_slots': 4 if form != 'ITX' else 2,
        'max_ram_gb': 192 if ddr == ['DDR5'] else 128,
        'm2_slots': 3 if high else (2 if form != 'ITX' else 2),
        'sata_ports': 6 if high else 4,
        'pcie_gen': 5 if (high or chipset in ('B650', 'B850', 'X870')) else 4,
        'bios_gen_ceiling': _BIOS_GEN_CEILING.get(chipset),
        'confident': confident,
    }


def _ram_specs(name: str) -> dict:
    n = name.lower()
    ddr = 'DDR5' if 'ddr5' in n else ('DDR4' if 'ddr4' in n else None)
    cap = re.search(r'(\d{1,3})\s*gb', n)
    spd = re.search(r'(\d{4})\s*mhz', n)
    return {
        'kind': 'ram',
        'ddr': ddr,
        'capacity_gb': int(cap.group(1)) if cap else 16,
        'speed_mhz': int(spd.group(1)) if spd else (5200 if ddr == 'DDR5' else 3200),
        'modules': 2 if re.search(r'2\s*x|kit|\(2', n) else 1,
        'confident': ddr is not None,
    }


def _gpu_specs(name: str) -> dict:
    n = name.lower()
    length, tdp, psu, power, gen = _search(n, _GPU_TABLE, None) or _GPU_DEFAULT
    return {
        'kind': 'gpu', 'length_mm': length, 'tdp_w': tdp, 'min_psu_w': psu,
        'pcie_power': power, 'pcie_gen': gen,
        'confident': _search(n, _GPU_TABLE, None) is not None,
    }


def _psu_specs(name: str) -> dict:
    n = name.lower()
    w = re.search(r'(\d{3,4})\s*w\b', n)
    watts = int(w.group(1)) if w else None
    rating = None
    m = re.search(r'80\+?\s*(titanium|platinum|gold|silver|bronze|white)', n)
    if m:
        rating = '80+ ' + m.group(1).capitalize()
    elif watts:
        rating = '80+ (unrated)'           # generic OEM unit — no efficiency cert listed
    # Connector count scales with wattage class.
    if watts and watts >= 1000:
        conns = '4×8-pin PCIe + 16-pin'
    elif watts and watts >= 750:
        conns = '3×8-pin PCIe'
    elif watts and watts >= 550:
        conns = '2×8-pin PCIe'
    else:
        conns = '1×8-pin PCIe'
    return {
        'kind': 'psu', 'watts': watts, 'rating': rating,
        'pcie_connectors': conns, 'form_factor': 'SFX' if 'sfx' in n else 'ATX',
        'confident': watts is not None,
    }


def connector_count(spec_str: str | None) -> int:
    """Parse a '2×8-pin PCIe', '8-pin', or '16-pin (3×8-pin adapter)' style
    string into the number of 8-pin-equivalent PCIe power connectors it
    represents. Used to check a PSU's actual connectors against a GPU's
    stated requirement instead of just asserting a match. When a GPU lists
    more than one supported option ('8-pin / 16-pin'), the least demanding
    option is used, since satisfying either is enough to run the card."""
    if not spec_str:
        return 1
    counts = []
    for opt in re.split(r'\s*/\s*', spec_str):
        m = re.search(r'(\d+)\s*[x×]\s*8-pin', opt, re.I)
        if m:
            counts.append(int(m.group(1)))
        elif re.search(r'16-pin', opt, re.I):
            counts.append(4)   # bare native 16-pin, no adapter spec ⇒ needs an ATX3.0-class PSU
        elif re.search(r'8-pin', opt, re.I):
            counts.append(1)
    return min(counts) if counts else 1


def _case_specs(name: str) -> dict:
    n = name.lower()
    if re.search(r'mini-?itx|\bitx\b', n):
        form, clear, cooler_h = 'ITX', 330, 150
    elif re.search(r'full\s*tower', n):
        form, clear, cooler_h = 'ATX', 420, 180
    elif re.search(r'm-?atx|micro|compact', n):
        form, clear, cooler_h = 'mATX', 360, 159
    else:                                   # mid-tower / business / generic
        form, clear, cooler_h = 'ATX', 380, 165
    return {
        'kind': 'case', 'form_factor': form,
        'supported_form_factors': _CASE_FORM_SUPPORT[form],
        'gpu_clearance_mm': clear, 'cooler_height_mm': cooler_h, 'confident': True,
    }


def _cooler_specs(name: str) -> dict:
    n = name.lower()
    aio = re.search(r'(\d{3})\s*mm|aio|liquid', n)
    # Restrict supported sockets when the cooler name actually names a platform, so a
    # genuinely platform-specific cooler can fail the CPU↔cooler socket check. A
    # generic/OEM cooler with no platform in its name stays broadly compatible with
    # current mainstream sockets — avoids falsely failing unlabeled catalog coolers.
    sockets = []
    if re.search(r'lga\s*1700|lga1700', n):
        sockets.append('LGA1700')
    if re.search(r'\bam5\b', n):
        sockets.append('AM5')
    if re.search(r'\bam4\b', n):
        sockets.append('AM4')
    if not sockets:
        has_intel = bool(re.search(r'\bintel\b', n))
        has_amd = bool(re.search(r'\bamd\b', n))
        if has_intel and not has_amd:
            sockets = ['LGA1700']
        elif has_amd and not has_intel:
            sockets = ['AM4', 'AM5']
        else:
            sockets = ['AM4', 'AM5', 'LGA1700']   # generic OEM cooler
    return {
        'kind': 'cooler',
        'sockets': sockets,
        'tdp_rating_w': 220 if aio else 95,
        'height_mm': 60 if aio else 150,
        'confident': True,
    }


def _storage_specs(name: str) -> dict:
    n = name.lower()
    nvme = bool(re.search(r'nvme|m\.?2', n))
    cap = re.search(r'(\d+)\s*(tb|gb)', n)
    cap_gb = None
    if cap:
        cap_gb = int(cap.group(1)) * (1024 if cap.group(2).lower() == 'tb' else 1)
    gen = 4 if re.search(r'nv2|990\s*pro|sn770|980\s*pro|gen\s*4', n) else 3
    return {
        'kind': 'storage',
        'interface': 'NVMe' if nvme else 'SATA',
        'form_factor': 'M.2' if nvme else '2.5"',
        'pcie_gen': gen if nvme else None,
        'capacity_gb': cap_gb, 'confident': True,
    }


# Order matters: check the most specific name signals first so a "DDR4" board
# doesn't get parsed as RAM, an SSD filed under "Motherboard" stays storage, and a
# "Cooler Master ... Case" stays a case rather than a cooler. The chipset pattern
# allows a trailing letter (A520M, X670E, B650M, B760M) — those are boards, not RAM.
def classify(name: str) -> str:
    n = (name or '').lower()
    if re.search(r'(geforce|\brtx\b|\bgtx\b|radeon|\brx\s?\d|\barc\b)', n):
        return 'gpu'
    if re.search(r'(motherboard|mainboard|\b[bxhza]\d{3}[a-z]?\b|chipset)', n):
        return 'motherboard'
    if re.search(r'(power supply|\bpsu\b|\d{3,4}\s*w\b|80\+)', n):
        return 'psu'
    if re.search(r'(ssd|nvme|hdd|hard drive)', n):
        return 'storage'
    if re.search(r'(ddr4|ddr5|dimm|\bram\b|memory)', n):
        return 'ram'
    # Case BEFORE cooler so "Cooler Master ... Case" isn't caught by the brand name.
    if re.search(r'(case|tower|chassis|cabinet)', n):
        return 'case'
    if re.search(r'(cooler|cooling|aio|heatsink|fan)', n):
        return 'cooler'
    if re.search(r'(processor|ryzen|core\s?i|athlon|xeon|celeron|apu|cpu)', n):
        return 'cpu'
    return 'other'


_DERIVERS = {
    'cpu': _cpu_specs, 'gpu': _gpu_specs, 'motherboard': _mobo_specs,
    'ram': _ram_specs, 'psu': _psu_specs, 'case': _case_specs,
    'cooler': _cooler_specs, 'storage': _storage_specs,
}


def derive_specs(name: str, kind: str | None = None) -> dict:
    """Structured specs for a part name. `kind` overrides the auto-classifier when
    the caller already knows the slot (e.g. the recommender's CPU/GPU/… buckets)."""
    kind = kind or classify(name)
    fn = _DERIVERS.get(kind)
    if not fn:
        return {'kind': 'other', 'confident': False}
    out = fn(name)
    out['kind'] = kind
    return out
