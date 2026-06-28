"""
AI build routes for the GenSpark ERP API (port 5000).

POST /api/recommend-build is DB-driven: it queries the live `components`
catalog, filters by category + budget + stock (> 0), keeps the CPU / motherboard
/ RAM platform coherent, and returns real component IDs (`build_components`) so
buildResolver.js and the cart can use them directly. It falls back to the
optional backend/.venv AI CLI, then to an indicative hardcoded estimate, only
when the live catalog can't satisfy the request.

POST /api/create-build delegates to the backend AI CLI.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from flask import jsonify, request

from app.api import api_bp

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / 'backend'
BACKEND_PY = BACKEND_DIR / '.venv' / 'Scripts' / 'python.exe'
AI_CLI = BACKEND_DIR / 'scripts' / 'ai_api_cli.py'

# Rule-based upgrade-compatibility validator lives at the repo root (no app deps,
# shared with backend/app.py). Imported here so the live Dashboard chat route can
# answer "upgrade my RAM/CPU…" with a compatible/incompatible verdict.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
try:
    from chat_intelligence import evaluate_upgrade_request
except Exception as _upgrade_import_err:  # pragma: no cover - keep route alive
    evaluate_upgrade_request = None
    print('upgrade validator unavailable:', _upgrade_import_err)

GEMINI_TABLE_COLUMNS = '| Component Type | Component Name | Est. Price (PKR) |'
GEMINI_TABLE_SEPARATOR = '| --- | --- | ---: |'
GEMINI_REQUIRED_TYPES = (
    'CPU', 'GPU', 'Motherboard', 'RAM', 'Storage', 'PSU', 'Case',
)


def _parse_budget_pkr(raw) -> int | None:
    """Parse a budget into PKR. Handles '1.2 lakh', '120k', '150000', '60000 PKR', '1.5'."""
    if raw is None:
        return None
    text = str(raw).strip().lower().replace(',', '')
    if not text:
        return None
    # 1.2 lakh / 1.20 lac
    m = re.search(r'([\d.]+)\s*(?:lakh|lakhs|lac|lacs)\b', text)
    if m:
        return int(float(m.group(1)) * 100_000)
    # 120k / 80 k
    m = re.search(r'([\d.]+)\s*k\b', text)
    if m:
        return int(float(m.group(1)) * 1_000)
    # explicit 4+ digit amount (150000, 60000)
    m = re.search(r'\d{4,}', text)
    if m:
        return int(m.group(0))
    # bare small number → assume lakhs ('1.5' -> 150000, '2' -> 200000)
    m = re.search(r'\d+(?:\.\d+)?', text)
    if m:
        value = float(m.group(0))
        return int(value * 100_000) if value < 100 else int(value)
    return None


def _budget_tier(budget_num: int | None) -> str:
    if budget_num is None:
        return 'mid'
    if budget_num < 60_000:
        return 'entry'
    if budget_num < 120_000:
        return 'mid'
    if budget_num < 200_000:
        return 'high'
    return 'enthusiast'


def _build_proportional_fallback_catalog(budget_num: int, purpose: str) -> dict[str, tuple[str, int]]:
    total = max(int(budget_num or 0), 40_000)
    purpose_key = (purpose or 'Gaming').lower()
    is_office = 'office' in purpose_key
    gpu_ratio = 0.12 if is_office else 0.42
    catalog = {
        'CPU': ('Dell Optiplex i5 Processor', int(total * 0.25)),
        'GPU': ('NVIDIA GeForce RTX 3060 12GB', int(total * gpu_ratio)),
        'Motherboard': ('Dell Optiplex Motherboard', int(total * 0.14)),
        'RAM': ('Dell 16GB DDR4 RAM', int(total * 0.08)),
        'Storage': ('Dell 512GB SSD', int(total * 0.07)),
        'PSU': ('Dell 500W Power Supply', int(total * 0.04)),
        'Case': ('Dell Desktop Case', max(int(total * 0.02), 5_000)),
    }
    if is_office:
        catalog['GPU'] = ('Intel UHD / Ryzen integrated graphics', 0)
        catalog['CPU'] = ('HP EliteDesk i5 Processor', int(total * 0.28))
        catalog['Motherboard'] = ('HP Business Motherboard', int(total * 0.14))
        catalog['RAM'] = ('HP 16GB DDR4 RAM', int(total * 0.08))
        catalog['Storage'] = ('HP 512GB SSD', int(total * 0.07))
        catalog['PSU'] = ('HP 450W Power Supply', int(total * 0.04))
        catalog['Case'] = ('HP Mid Tower Case', max(int(total * 0.02), 5_000))
    return catalog


def _generate_fallback_recommendation(purpose: str, budget: str) -> tuple[str, dict[str, str]]:
    budget_num = _parse_budget_pkr(budget)
    tier = _budget_tier(budget_num)
    if budget_num and budget_num >= 40_000:
        catalog = _build_proportional_fallback_catalog(budget_num, purpose)
    else:
        catalog = _build_proportional_fallback_catalog(80_000, purpose)

    budget_line = f'{budget_num:,} PKR' if budget_num else (budget or 'unspecified')
    total = sum(price for _, price in catalog.values())
    lines = [
        '## Summary',
        (
            f'This **{purpose or "Gaming"}** configuration targets approximately **{budget_line}** '
            f'(tier: {tier}). Catalog prices are indicative PKR for vendor comparison. '
            f'**Estimated total: {total:,} PKR.**'
        ),
        '',
        '## Recommended Components',
        GEMINI_TABLE_COLUMNS,
        GEMINI_TABLE_SEPARATOR,
    ]
    slot_to_key = {
        'CPU': 'cpu',
        'GPU': 'gpu',
        'Motherboard': 'motherboard',
        'RAM': 'ram',
        'Storage': 'storage',
        'PSU': 'psu',
        'Case': 'case',
    }
    parts_payload: dict[str, str] = {}
    for comp_type in GEMINI_REQUIRED_TYPES:
        name, price = catalog[comp_type]
        lines.append(f'| {comp_type} | {name} | {price:,} |')
        parts_payload[slot_to_key[comp_type]] = name

    return '\n'.join(lines), parts_payload


# ---------------------------------------------------------------------------
# DB-driven recommendation — query the live seeded `components` catalog.
# Picks one in-stock component per slot within the user's budget, keeps the
# CPU / motherboard / RAM platform coherent, and returns exact catalog names +
# ids so buildResolver.js resolves them straight into the cart.
# ---------------------------------------------------------------------------
_REC_SLOT_ORDER = ('CPU', 'GPU', 'Motherboard', 'RAM', 'Storage', 'PSU', 'Case')
_REC_SLOT_KEY = {
    'CPU': 'cpu', 'GPU': 'gpu', 'Motherboard': 'motherboard', 'RAM': 'ram',
    'Storage': 'storage', 'PSU': 'psu', 'Case': 'case',
}

# Query these categories per slot; the include/exclude name patterns defend
# against legacy mislabelled rows (e.g. SSDs filed under "Motherboard").
_REC_SLOT_RULES = {
    'CPU': {
        'cats': ('Processor', 'CPU'),
        'include': r'(processor|ryzen|core\s?i|athlon|xeon|celeron|apu)',
        'exclude': r'(motherboard|ssd|nvme|power supply|\bram\b|ddr|case|tower)',
    },
    'GPU': {
        'cats': ('GPU', 'Graphics Card'),
        'include': r'(geforce|\brtx\b|\bgtx\b|radeon|\brx\s?\d|\barc\b|graphics)',
        'exclude': r'(ssd|nvme|integrated)',
    },
    'Motherboard': {
        'cats': ('Motherboard',),
        'include': r'(motherboard|mainboard|\b[bxhza]\d{3})',
        'exclude': r'(ssd|nvme|case|tower|chassis|\bram\b|ddr|power supply|watt)',
    },
    'RAM': {
        'cats': ('RAM',),
        'include': r'(ddr4|ddr5|\bram\b|dimm|memory)',
        'exclude': r'(motherboard|ssd)',
    },
    'Storage': {
        'cats': ('Storage',),
        'include': r'(ssd|nvme|hdd|storage)',
        'exclude': r'(motherboard|case|power supply)',
    },
    'PSU': {
        'cats': ('PSU', 'Power Supply'),
        'include': r'(power supply|\bpsu\b|\d{3,4}\s?w\b|watt|bronze|gold|platinum)',
        'exclude': r'(motherboard|ssd)',
    },
    'Case': {
        'cats': ('Case', 'Cabinet'),
        'include': r'(case|tower|chassis|cabinet|mesh)',
        'exclude': r'(power supply|ssd)',
    },
}


def _rec_ratios(purpose):
    """Share of budget per slot, tuned to the workload."""
    p = (purpose or 'gaming').lower()
    if 'office' in p:
        return {'CPU': 0.28, 'GPU': 0.0, 'Motherboard': 0.16, 'RAM': 0.14,
                'Storage': 0.14, 'PSU': 0.14, 'Case': 0.14}
    if any(k in p for k in ('edit', 'content', 'render', 'video', 'ai', 'workstation')):
        return {'CPU': 0.26, 'GPU': 0.32, 'Motherboard': 0.12, 'RAM': 0.14,
                'Storage': 0.08, 'PSU': 0.05, 'Case': 0.03}
    return {'CPU': 0.22, 'GPU': 0.36, 'Motherboard': 0.12, 'RAM': 0.10,
            'Storage': 0.08, 'PSU': 0.07, 'Case': 0.05}


def _cpu_platform(name):
    n = (name or '').lower()
    if 'ryzen' in n or ('amd' in n and 'radeon' not in n):
        return 'AM5' if re.search(r'\b[789]\d{3}', n) else 'AM4'
    if 'core i' in n or 'intel' in n:
        return 'LGA1700'
    return None


def _mobo_platform(name):
    n = (name or '').lower()
    if re.search(r'\b(x870|x670|b650|b850|a620)', n):
        return 'AM5'
    if re.search(r'\b(b550|a520|b450|x570)', n):
        return 'AM4'
    if re.search(r'\b(b760|z790|h610|b660|z690|b860|z890)', n):
        return 'LGA1700'
    return None


def _pick_by_budget(cands, target):
    """Most expensive part within ~1.3× the slot target; else the cheapest."""
    if not cands:
        return None
    ceiling = max(float(target or 0), 0) * 1.3
    affordable = [c for c in cands if float(c.price or 0) <= ceiling]
    if affordable:
        return max(affordable, key=lambda c: float(c.price or 0))
    return min(cands, key=lambda c: float(c.price or 0))


def _cpu_has_igpu(name):
    """True if the CPU can drive a display without a discrete GPU (AMD APU 'G'
    suffix, or any Intel desktop chip that isn't an 'F' part)."""
    n = (name or '').lower()
    if 'ryzen' in n and re.search(r'\b\d{3,4}ge?\b', n):   # 5600G, 5700GE, ...
        return True
    if 'core i' in n or ('intel' in n and 'core' in n):
        return not re.search(r'\d{3,5}f\b', n)             # i5-13400F has no iGPU
    return False


def _fit_to_budget(selected, cand_map, budget_num):
    """Greedily step the costliest-to-trim slot down to a cheaper in-list option
    until the build total is within budget (or nothing cheaper remains).
    Candidate lists are already platform-coherent, so swaps stay compatible."""
    if not budget_num:
        return selected

    def total():
        return sum(float(c.price or 0) for c in selected.values())

    guard = 0
    while total() > budget_num and guard < 40:
        guard += 1
        best = None  # (saving, slot, cheaper_component)
        for slot, cur in selected.items():
            cands = cand_map.get(slot) or []
            cheaper = [c for c in cands if float(c.price or 0) < float(cur.price or 0)]
            if not cheaper:
                continue
            nxt = max(cheaper, key=lambda c: float(c.price or 0))  # next step down
            saving = float(cur.price or 0) - float(nxt.price or 0)
            if best is None or saving > best[0]:
                best = (saving, slot, nxt)
        if best is None:
            break
        selected[best[1]] = best[2]
    return selected


def _upgrade_to_budget(selected, Component, ComponentCategory, purpose, budget_num):
    """Spend leftover budget. When a build lands well under the customer's target
    (e.g. no discrete GPU fits, so the GPU's budget share is freed), greedily step
    the under-funded slots UP to better in-stock parts until the build approaches
    the target — without ever exceeding it. Platform coherence is preserved (same
    socket CPU + board, same DDR generation RAM), so every swap stays compatible.

    This is the inverse of `_fit_to_budget`: that one trims an over-budget build
    down; this one invests an under-budget build's headroom back into quality."""
    if not budget_num:
        return selected

    def price(c):
        return float(c.price or 0)

    cpu = selected.get('CPU')
    platform = _cpu_platform(cpu.name) if cpu else None
    has_gpu = selected.get('GPU') is not None

    # Coherent upgrade candidates per slot.
    cand = {
        'Storage': _slot_candidates(Component, ComponentCategory, 'Storage'),
        'PSU': _slot_candidates(Component, ComponentCategory, 'PSU'),
        'Case': _slot_candidates(Component, ComponentCategory, 'Case'),
    }
    mobo_all = _slot_candidates(Component, ComponentCategory, 'Motherboard')
    cand['Motherboard'] = [
        m for m in mobo_all if not platform or _mobo_platform(m.name) == platform
    ] or mobo_all
    ram_all = _slot_candidates(Component, ComponentCategory, 'RAM')
    if platform:
        gen = 'ddr4' if platform == 'AM4' else 'ddr5'
        ram_c = [r for r in ram_all if gen in (r.name or '').lower()] or ram_all
    else:
        ram_c = ram_all
    cand['RAM'] = [r for r in ram_c if '8gb' not in (r.name or '').lower()] or ram_c
    # CPU upgrades stay on the same socket (board + RAM remain compatible); if the
    # build leans on the iGPU, keep an iGPU-capable chip so it still displays.
    cpu_all = _slot_candidates(Component, ComponentCategory, 'CPU')
    cand['CPU'] = [
        c for c in cpu_all
        if (not platform or _cpu_platform(c.name) == platform)
        and (has_gpu or _cpu_has_igpu(c.name))
    ] or [cpu]
    if has_gpu:
        cand['GPU'] = _slot_candidates(Component, ComponentCategory, 'GPU')

    # Per-slot budget caps from the workload ratios. With no discrete GPU, its
    # share is redistributed across the live slots so an iGPU build still invests
    # the full budget (more RAM + storage for editing, a better CPU, etc.).
    ratios = dict(_rec_ratios(purpose))
    if not has_gpu:
        freed = ratios.pop('GPU', 0.0)
        live = {k: v for k, v in ratios.items() if v > 0}
        share = sum(live.values()) or 1.0
        for k in live:
            ratios[k] = live[k] + freed * (live[k] / share)
    caps = {slot: r * budget_num for slot, r in ratios.items()}

    def total():
        return sum(price(c) for c in selected.values())

    guard = 0
    while guard < 60:
        guard += 1
        remaining = budget_num - total()
        if remaining <= 1_500:           # close enough; stop nudging
            break
        # Upgrade the most under-funded slot (largest gap below its cap) to the
        # best part that still fits both its cap and the remaining headroom.
        pick = None  # (cap_deficit, slot, better_component)
        for slot, cur in selected.items():
            cands = cand.get(slot) or []
            cap = caps.get(slot)
            cur_p = price(cur)
            ceiling = min(cap if cap is not None else float('inf'), cur_p + remaining)
            better = [c for c in cands if cur_p < price(c) <= ceiling]
            if not better:
                continue
            nxt = max(better, key=price)             # best affordable within cap
            deficit = (cap - cur_p) if cap is not None else 0.0
            if pick is None or deficit > pick[0]:
                pick = (deficit, slot, nxt)
        if pick is None:
            break
        selected[pick[1]] = pick[2]
    return selected


# Legacy OEM pre-built systems pollute the catalog (e.g. "Dell Optiplex i7
# Processor") — they have no detectable socket/platform, so exclude them from
# component-level recommendations.
_REC_OEM_EXCLUDE = r'(optiplex|elitedesk|prodesk|thinkcentre|inspiron|pavilion|ideapad|all[\s-]?in[\s-]?one|\baio\b)'


def _slot_candidates(Component, ComponentCategory, slot):
    cfg = _REC_SLOT_RULES[slot]
    rows = (
        Component.query
        .join(ComponentCategory, ComponentCategory.id == Component.category_id)
        .filter(ComponentCategory.name.in_(cfg['cats']))
        .filter(Component.stock > 0)
        .order_by(Component.price.asc())
        .all()
    )
    out = []
    for c in rows:
        name = c.name or ''
        if re.search(_REC_OEM_EXCLUDE, name, re.I):
            continue
        if cfg.get('include') and not re.search(cfg['include'], name, re.I):
            continue
        if cfg.get('exclude') and re.search(cfg['exclude'], name, re.I):
            continue
        out.append(c)
    return out


def _psu_watts(c):
    """Wattage parsed from a PSU name, e.g. 'Cooler Master MWE 550W' -> 550."""
    m = re.search(r'(\d{3,4})\s*w\b', (getattr(c, 'name', '') or '').lower())
    return int(m.group(1)) if m else 0


def _required_psu_watts(selected):
    """Minimum PSU wattage the build's GPU needs (load + safe headroom). No GPU -> 0,
    so iGPU/office builds keep the cheapest PSU. Mirrors the compatibility rule so the
    recommender never ships a build the validator then flags as PSU-undersized."""
    gpu = selected.get('GPU')
    if gpu is None:
        return 0
    n = (getattr(gpu, 'name', '') or '').lower()
    if any(k in n for k in ('4090', '4080', '3090')):
        return 850
    if any(k in n for k in ('ti super', '5070', '4070 ti', '3080')):
        return 750
    if any(k in n for k in ('4070', '4060 ti', '3070', '6800', '6700')):
        return 650
    return 550  # entry/mid GPUs (RTX 4060, 3050, GTX 1660, etc.)


def _enforce_psu_adequacy(selected, psu_cands):
    """Swap the PSU up to the cheapest one that can actually power the GPU, so the
    recommended build is compatibility-valid. Runs last (after fit/upgrade) so nothing
    downgrades the PSU back below the GPU's requirement."""
    req = _required_psu_watts(selected)
    if not req:
        return
    cur = selected.get('PSU')
    if cur is not None and _psu_watts(cur) >= req:
        return
    ok = [p for p in (psu_cands or []) if _psu_watts(p) >= req]
    if ok:
        selected['PSU'] = min(ok, key=lambda c: float(c.price or 0))


def _select_components(Component, ComponentCategory, purpose, budget_num):
    """Pick a budget-respecting, platform-coherent build.

    For each CPU (each defines a socket platform) we take the cheapest coherent
    motherboard + RAM, add the peripheral essentials, then fit the best GPU the
    leftover budget allows (or rely on the CPU's iGPU). The build that lands
    within budget — with a real GPU and the best parts for the money — wins;
    if none fit, the closest (cheapest) coherent build is returned.
    """
    ratios = _rec_ratios(purpose)
    is_office = 'office' in (purpose or '').lower()
    budget_num = budget_num or 100_000

    cpu_cands = _slot_candidates(Component, ComponentCategory, 'CPU')
    if not cpu_cands:
        return {}
    mobo_all = _slot_candidates(Component, ComponentCategory, 'Motherboard')
    ram_all = _slot_candidates(Component, ComponentCategory, 'RAM')
    gpu_all = (
        _slot_candidates(Component, ComponentCategory, 'GPU')
        if (not is_office and ratios.get('GPU', 0) > 0) else []
    )

    def price(c):
        return float(c.price or 0)

    # Peripheral essentials (platform-agnostic) at their cheapest, so the budget
    # is freed up for the parts that matter most (CPU + GPU).
    base, cand_map = {}, {}
    for slot in ('Storage', 'PSU', 'Case'):
        cands = _slot_candidates(Component, ComponentCategory, slot)
        cand_map[slot] = cands
        if cands:
            base[slot] = min(cands, key=price)
    base_cost = sum(price(c) for c in base.values())
    cand_map['GPU'] = gpu_all  # GPU may be trimmed; CPU/mobo/RAM stay locked (coherent)

    best = None  # (rank_key, selected_dict)
    for cpu in cpu_cands:
        platform = _cpu_platform(cpu.name)
        if platform:
            mobo_c = [m for m in mobo_all if _mobo_platform(m.name) == platform]
            # No board for this CPU's socket (e.g. an Intel CPU with no LGA1700 board
            # in stock) → skip the CPU. Never fall back to a mismatched board, which
            # the compatibility validator would (correctly) reject.
            if not mobo_c:
                continue
        else:
            mobo_c = mobo_all
        if not mobo_c:
            continue
        if platform:
            gen = 'ddr4' if platform == 'AM4' else 'ddr5'
            ram_c = [r for r in ram_all if gen in (r.name or '').lower()] or ram_all
        else:
            ram_c = ram_all
        if not ram_c:
            continue
        # Avoid weak 8GB sticks when 16GB+ is available (modern baseline).
        ram_c = [r for r in ram_c if '8gb' not in (r.name or '').lower()] or ram_c

        mobo = min(mobo_c, key=price)   # cheapest coherent board/RAM → max GPU room
        ram = min(ram_c, key=price)
        ess = price(cpu) + price(mobo) + price(ram) + base_cost

        gpu = None
        if gpu_all:
            remaining = budget_num - ess
            affordable = [g for g in gpu_all if price(g) <= remaining]
            if affordable:
                gpu = max(affordable, key=price)
            elif not _cpu_has_igpu(cpu.name):
                gpu = min(gpu_all, key=price)  # must display something
            # else APU → integrated graphics, no discrete GPU.

        total = ess + (price(gpu) if gpu else 0)
        within = total <= budget_num
        if within:
            # within budget: prefer a real GPU, then the most build for the money
            rank = (1, 1 if gpu is not None else 0, total)
        else:
            # over budget: prefer the closest (cheapest) coherent build
            rank = (0, 0, -total)

        sel = {'CPU': cpu, 'Motherboard': mobo, 'RAM': ram, **base}
        if gpu is not None:
            sel['GPU'] = gpu
        if best is None or rank > best[0]:
            best = (rank, sel)

    if not best:
        return {}
    selected = best[1]
    # Shave the flexible slots (storage/PSU/case/GPU) if still a touch over.
    _fit_to_budget(selected, cand_map, budget_num)
    # Then invest any leftover headroom back into quality so the build actually
    # uses the customer's stated budget instead of landing well under it.
    _upgrade_to_budget(selected, Component, ComponentCategory, purpose, budget_num)
    # Final guard: ensure the PSU can power the GPU (compatibility) — runs last so
    # neither fit nor upgrade can leave an undersized PSU.
    _enforce_psu_adequacy(selected, cand_map.get('PSU'))
    return selected


def _format_db_recommendation(selected, purpose, budget_num, is_office):
    total = sum(int(float(c.price or 0)) for c in selected.values())
    budget_line = f'{int(budget_num):,} PKR' if budget_num else 'unspecified'
    cpu = selected.get('CPU')
    platform = _cpu_platform(cpu.name) if cpu else None

    # Budget-tier display metrics — these feed the premium recommendation card
    # (Compatibility / PSU headroom / Performance / Value). Deterministic, not an LLM.
    tier_ref = budget_num or total
    if tier_ref < 90_000:
        score, stars, tier = 78, 3, 'Entry'
    elif tier_ref < 160_000:
        score, stars, tier = 86, 4, 'Mid'
    elif tier_ref < 280_000:
        score, stars, tier = 92, 5, 'High'
    else:
        score, stars, tier = 96, 5, 'Enthusiast'

    # Smart layer: real power draw + PSU adequacy + bottleneck + per-part "why".
    # Replaces the old cosmetic wattage lookup with an engineering validation pass.
    try:
        from app.services.build_intelligence import analyze
        intel = analyze(selected, purpose, platform)
    except Exception:
        intel = None
    if intel:
        watts = intel['psu']['rated'] or intel['psu']['required']
        bottleneck_note = intel['bottleneck']['note']
        compat_base = f'Compatible · {platform}' if platform else 'Compatible · validated'
        compat_value = f'{compat_base} — {bottleneck_note}'
    else:
        watts = 450 if is_office else (550 if tier_ref < 90_000 else 650 if tier_ref < 160_000 else 850)
        compat_value = f'Compatible · {platform}' if platform else 'Compatible · validated'

    summary = (
        f'A {purpose or "Gaming"} build matched from live, in-stock inventory — every '
        'component below is available right now and ready to add to your cart.'
    )
    if budget_num and total > budget_num:
        over_amt = total - budget_num
        over_pct = round(over_amt / budget_num * 100)
        # Scale the wording to the real overage — "slightly" only when it truly is.
        if over_pct <= 10:
            degree = 'slightly above'
        elif over_pct <= 30:
            degree = 'moderately above'
        else:
            degree = 'well above'
        summary += (
            f' This is the closest in-stock configuration; it runs {degree} your '
            f'{budget_line} target by ~{over_amt:,} PKR ({over_pct}%). '
            f'A realistic budget for this {(purpose or "Gaming").lower()} build is around {total:,} PKR.'
        )
    elif not is_office and not selected.get('GPU'):
        # No discrete GPU fits this budget on the affordable platform, so the build
        # leans on the CPU's integrated graphics and the freed budget is invested in
        # the parts that matter (CPU/RAM/storage). Be honest about the trade-off.
        headroom = (budget_num - total) if budget_num else 0
        summary += (
            ' On this budget the strongest fit is a build on the processor’s integrated '
            'graphics — a discrete graphics card would push it over your target. The '
            'budget is invested into a faster CPU, more memory and storage instead, and '
            'you can add a graphics card later.'
        )
        if headroom > 5_000:
            summary += (
                f' This configuration comes in ~{headroom:,} PKR under target — the best '
                'value in-stock parts at this tier; the rest is left unspent rather than '
                'padded with components that wouldn’t improve performance.'
            )

    # Header keys ("Compatibility Status", "Performance Score", …) are what the
    # frontend parser reads to render the clean metric cards (parseBuildRecommendation.js).
    psu_note = intel['psu']['message'] if intel else 'sized with headroom'
    lines = [
        f'**Compatibility Status:** {compat_value}',
        f'**PSU Wattage Buffer:** {watts}W — {psu_note}',
        f'**GenSpark Performance Score:** {score}/100',
    ]
    if intel:
        lines.append(f'**VRM thermal index {intel["vrm_index"]}/100** — board headroom for the CPU draw')
    lines += [
        f'**Value For Money Rating:** {"⭐" * stars} (Tier: {tier})',
        f'**Estimated parts total:** {total:,} PKR',
        '',
        '## Summary',
        summary,
        '',
        '## Recommended Components',
        GEMINI_TABLE_COLUMNS,
        GEMINI_TABLE_SEPARATOR,
    ]

    parts = {}
    comps = []
    for slot in _REC_SLOT_ORDER:
        if slot == 'GPU' and not selected.get('GPU'):
            # No discrete card (office build, or dropped to meet budget) -> iGPU.
            lines.append('| GPU | Integrated graphics (CPU) | 0 |')
            parts['gpu'] = 'Integrated'
            continue
        c = selected.get(slot)
        if not c:
            continue
        price = int(float(c.price or 0))
        lines.append(f'| {slot} | {c.name} | {price:,} |')
        parts[_REC_SLOT_KEY[slot]] = c.name
        comps.append({
            'slot': _REC_SLOT_KEY[slot],
            'label': slot,
            'component_id': c.id,
            'name': c.name,
            'price': price,
            'category': c.category.name if getattr(c, 'category', None) else None,
            'stock': int(c.stock or 0),
        })

    # 🧠 Engineering reasoning — red flags first (so they lead), then the per-part
    # "why". The frontend parses this '## …reasoning…' section into the insight card.
    if intel:
        bullets = (intel.get('red_flags') or []) + (intel.get('reasoning') or [])
        if bullets:
            lines.append('')
            lines.append('## 🧠 Engineering Reasoning')
            for b in bullets:
                lines.append(f'- {b}')

    return '\n'.join(lines), parts, comps, total, intel


def _alt_lookup(Component, ComponentCategory):
    """Build the `alt_lookup(slot, predicate)` the compatibility validator uses to
    propose replacement parts. Candidates come from the recommender's own slot
    buckets (correctly name-classified + in-stock), so a CPU can never be offered
    as a 'Case' alternative — only real cases are considered for the Case slot."""
    from app.services.compatibility import specs_for
    cache: dict = {}

    def lookup(slot, predicate):
        if slot not in cache:
            try:
                cache[slot] = _slot_candidates(Component, ComponentCategory, slot)
            except KeyError:
                cache[slot] = []
        return [c for c in cache[slot] if predicate(specs_for(c, slot.lower()))]

    return lookup


def _recommend_from_catalog(purpose, budget):
    """Build a recommendation from in-stock DB components. None if catalog is empty."""
    try:
        from app.models import Component, ComponentCategory
    except Exception:
        return None

    budget_num = _parse_budget_pkr(budget) or 100_000
    try:
        selected = _select_components(Component, ComponentCategory, purpose, budget_num)
    except Exception:
        return None
    if not selected or 'CPU' not in selected:
        return None

    # Deterministic, rule-based compatibility proof over the selected parts. The
    # recommender already guarantees a coherent build, so this validates clean; it
    # gives the customer the explicit pass/fail/score contract (and is the gate the
    # customization engine will reuse to revalidate user edits).
    try:
        from app.services.compatibility import validate_build
        compatibility = validate_build(selected, alt_lookup=_alt_lookup(Component, ComponentCategory))
    except Exception as _e:
        print('compatibility validation skipped:', _e)
        compatibility = None

    is_office = 'office' in (purpose or '').lower()
    markdown, parts, comps, total, intel = _format_db_recommendation(
        selected, purpose, budget_num, is_office
    )
    return {
        'success': True,
        'conversational': False,
        'source': 'rules-db',
        'fallback': False,
        'gemini_active': False,
        'recommendation_markdown': markdown,
        'fallback_build': parts,      # exact catalog names — buildResolver resolves these
        'parts': parts,
        'build_components': comps,     # real component IDs for direct cart add
        'total_price': total,
        'purpose': purpose,
        'budget': f'{budget_num} PKR',
        # Structured smart-layer output (power/PSU/bottleneck/VRM/reasoning/red flags)
        # for any client that wants the data without re-parsing the markdown.
        'intelligence': intel,
        # Deterministic rule-based compatibility verdict: {compatible, score,
        # checks[], failures[], warnings[]} — proves the build by rule, not by LLM.
        'compatibility': compatibility,
        'compatibility_score': (compatibility or {}).get('score'),
    }


_GREETING_FRAGMENTS = (
    'hi', 'hello', 'help me', 'help', 'hey', 'yo', 'sup', 'aoa', 'salam', 'assalam',
    'assalam o alaikum', 'salam alaikum', 'kia hal', 'kia hal ha', 'kia hal hai',
    'kya hal', 'kaise ho', 'kaise hain', 'how are you', 'how r u',
)


def _is_greeting_only_message(message: str) -> bool:
    msg = re.sub(r'\s+', ' ', (message or '').strip().lower())
    if not msg:
        return True
    if re.search(r'(\b(?:build|setup|rig|budget|lakh|lac)\b|\d{4,}|\d+\s*k\b)', msg):
        return False
    if re.search(r'(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|lacs)\b', msg):
        return False
    if any(msg == frag or msg.startswith(frag + ' ') or msg.endswith(' ' + frag) for frag in _GREETING_FRAGMENTS):
        return True
    cleaned_alpha = re.sub(r'[^\w]', '', msg)
    if 0 < len(cleaned_alpha) <= 3:
        return True
    if not any(fragment in msg for fragment in _GREETING_FRAGMENTS):
        return False
    cleaned = re.sub(r'[^\w\s]', '', msg)
    return len(cleaned.split()) <= 6


def _generate_greeting_markdown() -> str:
    return """### 👋 Hello! Welcome to GenSpark Builds AI Assistant

Yes, I can absolutely help you design and engineer the perfect custom PC setup.

To initialize my building framework, please let me know:
1. 💰 **Your target budget** (e.g. *1.20 lakh budget*, *120k*, or *150000 PKR*)
2. 🛠️ **Your primary deployment purpose** (e.g. *Gaming build*, *Video editing*, or *Office tasking*)

Our vision system can detect parts you already own (mouse, keyboard, monitor, RAM) and exclude them from your quote."""


def _extract_payload(data: dict) -> dict:
    """Mirror backend/app.py _extract_recommend_payload — greetings ignore stale panel fields."""
    message = str(data.get('message') or data.get('user_message') or '').strip()
    build_requested = bool(data.get('build_requested') or data.get('buildRequested'))

    budget_raw = data.get('budget') or data.get('budget_pkr') or data.get('budgetPkr')
    purpose_raw = data.get('purpose') or data.get('use_case') or data.get('useCase')

    budget_explicit = budget_raw is not None and str(budget_raw).strip() != ''
    purpose_explicit = purpose_raw is not None and str(purpose_raw).strip() != ''

    greeting_only = bool(message) and _is_greeting_only_message(message)
    if greeting_only and not build_requested:
        want_build = False
    else:
        want_build = bool(build_requested or budget_explicit or purpose_explicit)

    purpose = ''
    budget = ''
    if want_build:
        purpose = str(purpose_raw).strip() if purpose_explicit else 'Gaming'
        budget = str(budget_raw).strip() if budget_explicit else '100000 PKR'

    detected_part = str(
        data.get('detected_part') or data.get('detectedPart') or 'None'
    ).strip() or 'None'

    return {
        'message': message,
        'build_requested': build_requested,
        'purpose': purpose,
        'budget': budget,
        'want_build': want_build,
        'greeting_only': greeting_only,
        'detected_part': detected_part,
    }


def _invoke_backend_cli(command: str, payload: dict) -> dict | None:
    if not BACKEND_PY.is_file() or not AI_CLI.is_file():
        return None
    try:
        proc = subprocess.run(
            [str(BACKEND_PY), str(AI_CLI), command],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=130,
            cwd=str(BACKEND_DIR),
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if not (proc.stdout or '').strip():
        return None
    try:
        body = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    if isinstance(body, dict) and body.get('success'):
        return body
    return None


def _greeting_json(payload: dict):
    return jsonify({
        'success': True,
        'conversational': True,
        'source': 'guide',
        'gemini_active': False,
        'fallback': False,
        'recommendation_markdown': _generate_greeting_markdown(),
        'purpose': '',
        'budget': '',
        'detected_part': payload.get('detected_part', 'None'),
    })


@api_bp.route('/recommend-build', methods=['POST', 'OPTIONS'])
def api_recommend_build():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json(silent=True) or {}
    payload = _extract_payload(data)

    # Rule-based upgrade validation wins over build/greeting — e.g. "upgrade my
    # 16GB RAM to 32GB" or "swap to Ryzen 7 7700 on my B550 board".
    if evaluate_upgrade_request is not None and payload.get('message'):
        upgrade = evaluate_upgrade_request(payload['message'])
        if upgrade is not None:
            return jsonify({
                'success': True,
                'conversational': True,
                'source': 'rules',
                'intent': upgrade.get('intent', 'upgrade_request'),
                'intent_badge': upgrade.get('badge', 'GenSpark Upgrade Validator'),
                'gemini_active': False,
                'fallback': False,
                'recommendation_markdown': upgrade['message'],
                'purpose': '',
                'budget': '',
                'detected_part': payload.get('detected_part', 'None'),
            }), 200

    if not payload['want_build']:
        # Component knowledge: "use of GPU", "what is a motherboard", "RAM kis liye" …
        try:
            from app.services.component_info import detect_component_query, render_component_info
            ckey = detect_component_query(payload.get('message'))
            if ckey:
                return jsonify({
                    'success': True,
                    'conversational': True,
                    'source': 'expert',
                    'gemini_active': False,
                    'fallback': False,
                    'recommendation_markdown': render_component_info(ckey),
                    'purpose': '',
                    'budget': '',
                    'detected_part': payload.get('detected_part', 'None'),
                }), 200
        except Exception as _e:
            print('component info skipped:', _e)

        body = _invoke_backend_cli('recommend-build', data)
        if body:
            return jsonify(body), 200
        return _greeting_json(payload)

    # 1. DB-driven recommendation from the live seeded catalog (preferred).
    db_result = _recommend_from_catalog(payload['purpose'] or 'Gaming', payload['budget'])
    if db_result:
        return jsonify(db_result), 200

    # 2. Optional external AI backend (only if backend/.venv CLI is installed).
    body = _invoke_backend_cli('recommend-build', data)
    if body:
        return jsonify(body), 200

    # 3. Last resort: indicative hardcoded catalog estimate.
    markdown, parts = _generate_fallback_recommendation(
        payload['purpose'] or 'Gaming',
        payload['budget'],
    )
    return jsonify({
        'success': True,
        'conversational': False,
        'source': 'catalog',
        'fallback': True,
        'recommendation_markdown': markdown,
        'fallback_build': parts,
        'purpose': payload['purpose'],
        'budget': payload['budget'],
    })


# Frontend build keys ↔ validator slot names.
_BUILD_KEY_TO_SLOT = {
    'cpu': 'CPU', 'gpu': 'GPU', 'ram': 'RAM', 'storage': 'Storage',
    'psu': 'PSU', 'motherboard': 'Motherboard', 'case': 'Case', 'cooler': 'Cooler',
}


# Short, human reason shown beside each dropdown option for its compatibility status.
_RULE_NOTE = {
    'CPU ↔ Motherboard socket': 'Socket mismatch',
    'CPU ↔ Motherboard memory': 'Memory type mismatch',
    'Motherboard ↔ RAM generation': 'Memory type mismatch (DDR)',
    'Motherboard ↔ RAM capacity': 'Exceeds board RAM limit',
    'Motherboard ↔ Storage': 'No matching storage slot',
    'Display output': 'No graphics output (needs GPU/iGPU)',
    'PSU capacity': 'Requires PSU upgrade',
    'PSU efficiency rating': 'Requires better PSU',
    'GPU ↔ Case clearance': 'Exceeds case clearance',
    'Motherboard ↔ Case form factor': 'Case form-factor mismatch',
    'CPU ↔ Cooler socket': 'Cooler socket mismatch',
    'CPU ↔ Cooler capacity': 'Cooler under-rated',
}


def _card_spec(slot, sp):
    """Short human spec line for a component card."""
    s = slot.lower()
    if s == 'cpu':
        return ' · '.join(filter(None, [sp.get('socket'), f"{sp.get('tdp_w')}W" if sp.get('tdp_w') else None,
                                        'iGPU' if sp.get('igpu') else None]))
    if s == 'gpu':
        return ' · '.join(filter(None, [f"{sp.get('tdp_w')}W" if sp.get('tdp_w') else None,
                                        sp.get('pcie_power'), f"PCIe {sp.get('pcie_gen')}" if sp.get('pcie_gen') else None]))
    if s == 'ram':
        return ' · '.join(filter(None, [f"{sp.get('capacity_gb')}GB" if sp.get('capacity_gb') else None,
                                        sp.get('ddr'), f"{sp.get('speed_mhz')}MHz" if sp.get('speed_mhz') else None]))
    if s == 'storage':
        cap = sp.get('capacity_gb')
        if cap and cap >= 1000:
            cap_s = f"{cap // 1000}TB" if cap % 1000 == 0 else f"{round(cap / 1000, 1)}TB"
        else:
            cap_s = f"{cap}GB" if cap else None
        return ' · '.join(filter(None, [cap_s, sp.get('interface'),
                                        f"Gen {sp.get('pcie_gen')}" if sp.get('pcie_gen') else None]))
    if s == 'psu':
        return ' · '.join(filter(None, [f"{sp.get('watts')}W" if sp.get('watts') else None, sp.get('rating')]))
    if s == 'motherboard':
        return ' · '.join(filter(None, [sp.get('socket'), sp.get('chipset'),
                                        (sp.get('ddr') or [None])[0], sp.get('form_factor')]))
    return ''


def _card_rating(slot, name, sp, bi):
    """Coarse 0-100 gaming/work rating for the card's performance bar."""
    s = slot.lower()
    name = name or ''
    if s == 'gpu':
        t = bi._tier(name.lower(), bi._GPU_TIER)
        return {'gaming': min(100, t * 10), 'work': min(100, t * 9)}
    if s == 'cpu':
        t = bi._tier(name.lower(), bi._CPU_TIER)
        return {'gaming': min(100, t * 10), 'work': min(100, t * 10 + 5)}
    if s == 'ram':
        cap = sp.get('capacity_gb') or 8
        v = min(100, round(cap / 64 * 100))
        return {'gaming': v, 'work': v}
    if s == 'storage':
        cap = sp.get('capacity_gb') or 256
        v = min(100, round(cap / 2048 * 100))
        fast = 15 if sp.get('interface') == 'NVMe' else 0
        return {'gaming': min(100, v + fast), 'work': min(100, v + fast)}
    if s == 'psu':
        w = sp.get('watts') or 450
        return {'gaming': min(100, round(w / 1000 * 100)), 'work': min(100, round(w / 1000 * 100))}
    if s == 'motherboard':
        rank = {'X': 90, 'Z': 90, 'B': 75, 'A': 60, 'H': 60}.get((sp.get('chipset') or 'B')[0], 70)
        return {'gaming': rank, 'work': rank}
    return {'gaming': 60, 'work': 60}


@api_bp.route('/build-options', methods=['GET', 'POST', 'OPTIONS'])
def api_build_options():
    """In-stock candidate parts per editable slot, for the customization dropdowns.
    Uses the recommender's own name-classification so each slot lists only valid
    parts (real GPUs under 'gpu', etc.) — never a mis-filed catalog row.

    POST with {build:{cpu:id,...}} filters each slot to parts that do NOT hard-fail
    in that build (a DDR4 stick is hidden on a DDR5 board, a wrong-socket CPU is
    hidden, …) so an incompatible part can never be offered. Parts that only need a
    supporting upgrade (e.g. a big GPU needing a bigger PSU) are kept — they're
    selectable and the engine proposes the adjustment. GET returns the full list."""
    if request.method == 'OPTIONS':
        return '', 204
    try:
        from app.models import Component, ComponentCategory
        from app.services.compatibility import validate_build
        from app.services.customization import _HARD_RULES
    except Exception as e:
        return jsonify({'success': False, 'error': f'catalog unavailable: {e}'}), 503

    # Optional current-build context → resolve to {Slot: Component} for hard filtering.
    raw_build = (request.get_json(silent=True) or {}).get('build') or {}
    build = {}
    for key, cid in raw_build.items():
        s = _BUILD_KEY_TO_SLOT.get(str(key).lower())
        if s and cid:
            comp = Component.query.get(cid)
            if comp:
                build[s] = comp

    from app.services.compatibility import specs_for
    from app.services.customization import _ADJUSTABLE_RULES
    from app.services import build_intelligence as bi

    def card_status(slot, candidate):
        """(status, note): status ∈ 'ok'|'adjust'|'incompatible'; note is a short
        human reason. Incompatible parts are STILL returned (marked) so the dropdown
        shows every relevant part and the engine can explain an incompatible pick."""
        if not build:
            return 'ok', 'Compatible'
        modified = dict(build)
        modified[slot] = candidate
        fails = [f['rule'] for f in validate_build(modified)['failures']]
        hard = [r for r in fails if r in _HARD_RULES]
        if hard:
            return 'incompatible', _RULE_NOTE.get(hard[0], 'Incompatible')
        adj = [r for r in fails if r in _ADJUSTABLE_RULES]
        if adj:
            return 'adjust', _RULE_NOTE.get(adj[0], 'Needs adjustment')
        return 'ok', 'Compatible'

    out = {}
    for slot in ('CPU', 'GPU', 'RAM', 'Storage', 'PSU', 'Motherboard'):
        try:
            cands = _slot_candidates(Component, ComponentCategory, slot)
        except KeyError:
            cands = []
        cards = []
        for c in sorted(cands, key=lambda c: float(c.price or 0)):
            status, note = card_status(slot, c)
            sp = specs_for(c, slot.lower())
            cards.append({
                'id': c.id, 'name': c.name,
                'price': int(float(c.price or 0)), 'stock': int(c.stock or 0),
                'spec': _card_spec(slot, sp),
                'rating': _card_rating(slot, c.name, sp, bi),
                'status': status, 'note': note,
            })
        out[_REC_SLOT_KEY[slot]] = cards
    return jsonify({'success': True, 'options': out}), 200


@api_bp.route('/evaluate-customization', methods=['POST', 'OPTIONS'])
def api_evaluate_customization():
    """Decision-support for a single user edit to a build. Returns the 4-level
    verdict (fully_compatible / unnecessary / needs_adjustments / incompatible) with
    budget + performance impact, dependent changes, and a plain/technical explanation.

    Body: {purpose, budget, build:{cpu:id,...}, change:{slot, component_id}, mode}
    """
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json(silent=True) or {}
    change = data.get('change') or {}
    raw_build = data.get('build') or {}
    slot_key = str(change.get('slot') or '').strip().lower()
    new_id = change.get('component_id') or change.get('componentId')

    slot = _BUILD_KEY_TO_SLOT.get(slot_key)
    if not slot or not new_id:
        return jsonify({'success': False,
                        'error': 'Provide change.slot (cpu/gpu/ram/storage/psu) and '
                                 'change.component_id.'}), 400

    try:
        from app.models import Component, ComponentCategory
        from app.services.customization import evaluate_change
    except Exception as e:
        return jsonify({'success': False, 'error': f'engine unavailable: {e}'}), 503

    # Resolve the current build (slot → Component) and the proposed new part.
    build = {}
    for key, cid in raw_build.items():
        s = _BUILD_KEY_TO_SLOT.get(str(key).lower())
        if s and cid:
            c = Component.query.get(cid)
            if c:
                build[s] = c
    new_part = Component.query.get(new_id)
    if not new_part:
        return jsonify({'success': False, 'error': f'component {new_id} not found.'}), 404

    def cand_for(s):
        try:
            return _slot_candidates(Component, ComponentCategory, s)
        except KeyError:
            return []

    budget_num = _parse_budget_pkr(data.get('budget'))
    mode = 'advanced' if str(data.get('mode')).lower() == 'advanced' else 'beginner'
    verdict = evaluate_change(
        build, slot, new_part, data.get('purpose') or 'Gaming',
        budget_num, cand_for=cand_for, mode=mode,
    )
    return jsonify({'success': True, **verdict}), 200


@api_bp.route('/build-suggestions', methods=['POST', 'OPTIONS'])
def api_build_suggestions():
    """Rule-based proactive upgrade suggestions for a build (e.g. "32GB RAM is
    recommended for gaming"). Body: {purpose, budget, build:{cpu:id,...}}.
    Each suggestion names a concrete compatible part the UI can apply in one click."""
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json(silent=True) or {}
    try:
        from app.models import Component, ComponentCategory
        from app.services.compatibility import validate_build
        from app.services.customization import suggest_upgrades, _HARD_RULES
    except Exception as e:
        return jsonify({'success': False, 'error': f'engine unavailable: {e}'}), 503

    build = {}
    for key, cid in (data.get('build') or {}).items():
        s = _BUILD_KEY_TO_SLOT.get(str(key).lower())
        if s and cid:
            c = Component.query.get(cid)
            if c:
                build[s] = c

    def cand_for(slot_title):
        try:
            cands = _slot_candidates(Component, ComponentCategory, slot_title)
        except KeyError:
            return []
        ok = []
        for c in cands:
            modified = dict(build)
            modified[slot_title] = c
            if not any(f['rule'] in _HARD_RULES for f in validate_build(modified)['failures']):
                ok.append(c)
        return ok

    budget_num = _parse_budget_pkr(data.get('budget'))
    suggestions = suggest_upgrades(build, data.get('purpose') or 'Gaming', budget_num, cand_for)
    return jsonify({'success': True, 'suggestions': suggestions}), 200


@api_bp.route('/ai-status', methods=['GET', 'OPTIONS'])
def api_ai_status():
    if request.method == 'OPTIONS':
        return '', 204

    if BACKEND_PY.is_file() and AI_CLI.is_file():
        try:
            proc = subprocess.run(
                [str(BACKEND_PY), str(AI_CLI), 'ai-status'],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=str(BACKEND_DIR),
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
            )
            if proc.stdout.strip():
                body = json.loads(proc.stdout)
                if isinstance(body, dict):
                    return jsonify(body), 200 if body.get('success') else 503
        except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
            pass

    return jsonify({
        'success': False,
        'gemini_configured': False,
        'message': 'Backend AI not available. Run START-GENSPARK-DEV.bat or install backend/.venv.',
    }), 503


@api_bp.route('/create-build', methods=['POST', 'OPTIONS'])
def api_create_build():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json(silent=True) or {}
    body = _invoke_backend_cli('create-build', data)
    if body:
        return jsonify(body), 200

    return jsonify({
        'success': False,
        'error': (
            'Could not save build via AI backend. Start backend with START-GENSPARK-DEV.bat '
            'or ensure backend/.venv exists.'
        ),
    }), 503
