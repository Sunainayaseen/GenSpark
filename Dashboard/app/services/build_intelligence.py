"""
Build Intelligence — the "smart" layer on top of the rules-based recommender.

`ai_build_routes._select_components` already guarantees a *coherent* build (CPU
socket ↔ chipset ↔ DDR generation, in-stock, within budget). This module adds
the engineering judgement on top of that selection:

  * estimate_system_watts()  — real load-power estimate from the actual parts
  * psu_check()              — is the SELECTED PSU big enough? (red-flag if not)
  * bottleneck()             — CPU↔GPU balance read for the target workload
  * vrm_index()              — board/VRM thermal comfort for the CPU's draw
  * reasoning_bullets()      — per-component expert "why" + synergy notes
  * red_flags()              — bold warnings the UI surfaces before the parts

All deterministic heuristics — no LLM. Power/perf are read from the model name
(the catalog stores names like "NVIDIA GeForce RTX 5070 Ti 16GB"), with safe
class-based fallbacks so unknown parts degrade gracefully instead of crashing.
The output feeds fields the React parser ALREADY understands (bottleneck on the
Compatibility line, "VRM thermal index", a 🧠 Reasoning list) — no UI change.
"""
from __future__ import annotations

import re

# --- Whole-card load draw (W) by GPU family. Guidance figures incl. transient
#     headroom, not exact TGP. Longer patterns first so "5070 ti" beats "5070". ---
_GPU_WATTS = (
    (r'rtx\s*5090', 500), (r'rtx\s*5080', 360), (r'rtx\s*5070\s*ti', 300),
    (r'rtx\s*5070', 250), (r'rtx\s*5060\s*ti', 200), (r'rtx\s*5060', 170),
    (r'rtx\s*4090', 450), (r'rtx\s*4080', 320), (r'rtx\s*4070\s*ti', 285),
    (r'rtx\s*4070', 200), (r'rtx\s*4060\s*ti', 165), (r'rtx\s*4060', 115),
    (r'rtx\s*3090', 350), (r'rtx\s*3080', 320), (r'rtx\s*3070', 220),
    (r'rtx\s*3060\s*ti', 200), (r'rtx\s*3060', 170), (r'rtx\s*3050', 130),
    (r'gtx\s*16\d0', 120), (r'gtx\s*10\d0', 120),
    (r'rx\s*7900', 320), (r'rx\s*7800', 263), (r'rx\s*7700', 245),
    (r'rx\s*7600', 165), (r'rx\s*6[89]\d0', 250), (r'rx\s*6[67]\d0', 180),
    (r'arc\s*a7\d0', 190), (r'arc\s*a5\d0', 130),
)
_GPU_DEFAULT_W = 200

# --- CPU load draw (W) by class. ---
_CPU_WATTS = (
    (r'(i9|ryzen\s*9|core\s*ultra\s*9)', 170),
    (r'(i7|ryzen\s*7|core\s*ultra\s*7)', 125),
    (r'(i5|ryzen\s*5|core\s*ultra\s*5)', 95),
    (r'(i3|ryzen\s*3)', 65),
)
_CPU_DEFAULT_W = 95

# Everything that isn't CPU/GPU: board + RAM + NVMe + fans/AIO pump + drives.
_BASE_SYSTEM_W = 90

# Standard ATX PSU rungs we'd actually recommend.
_PSU_RUNGS = (450, 550, 650, 750, 850, 1000, 1200, 1600)

# Performance ladders (0-10) for the bottleneck read.
_GPU_TIER = (
    (r'rtx\s*5090', 10), (r'rtx\s*4090', 10), (r'rtx\s*5080', 9), (r'rtx\s*4080', 9),
    (r'rtx\s*5070\s*ti', 8), (r'rtx\s*4070\s*ti', 8), (r'rx\s*7900', 8),
    (r'rtx\s*5070', 7), (r'rtx\s*4070', 7), (r'rx\s*7800', 7),
    (r'rtx\s*3080', 7), (r'rtx\s*5060\s*ti', 6), (r'rx\s*7700', 6), (r'rtx\s*3070', 6),
    (r'rtx\s*4060', 5), (r'rtx\s*5060', 5), (r'rx\s*7600', 5), (r'rtx\s*3060', 4),
    (r'gtx\s*16', 3), (r'rtx\s*3050', 3),
)
_CPU_TIER = (
    (r'(i9|ryzen\s*9)', 9), (r'(i7|ryzen\s*7)', 7),
    (r'(i5|ryzen\s*5)', 5), (r'(i3|ryzen\s*3)', 3),
)


def _name(c):
    return (getattr(c, 'name', '') or '').lower()


def _match(name, table, default):
    for pat, val in table:
        if re.search(pat, name, re.I):
            return val
    return default


def _gpu_watts(name):
    return _match(name, _GPU_WATTS, _GPU_DEFAULT_W)


def _cpu_watts(name):
    return _match(name, _CPU_WATTS, _CPU_DEFAULT_W)


def estimate_system_watts(selected: dict) -> int:
    """Estimated sustained load draw (W) for the selected build."""
    cpu = selected.get('CPU')
    gpu = selected.get('GPU')
    watts = _BASE_SYSTEM_W
    if cpu:
        watts += _cpu_watts(_name(cpu))
    if gpu:
        watts += _gpu_watts(_name(gpu))   # no GPU key ⇒ iGPU ⇒ no card draw
    return int(watts)


def recommended_psu_watts(draw: int) -> int:
    """Smallest standard PSU that keeps the build at ~70% load (≈30% headroom).
    The per-GPU draw figures already pad for transients, so 0.7 (not 0.6) avoids
    double-counting and lands on the wattage a builder would actually buy."""
    target = draw / 0.7
    for rung in _PSU_RUNGS:
        if rung >= target:
            return rung
    return _PSU_RUNGS[-1]


def _psu_rated_watts(name):
    m = re.search(r'(\d{3,4})\s*w\b', name or '', re.I)
    return int(m.group(1)) if m else None


def psu_check(selected: dict, draw: int) -> dict:
    """Validate the SELECTED PSU against the build's real draw. This is the check
    the old cosmetic 'tier wattage' could never do."""
    required = recommended_psu_watts(draw)
    psu = selected.get('PSU')
    rated = _psu_rated_watts(_name(psu)) if psu else None
    if rated is None:
        return {
            'draw': draw, 'required': required, 'rated': None, 'ok': True,
            'headroom_pct': None, 'red_flag': False,
            'message': (f'~{draw}W load → {required}W recommended '
                        f'(PSU wattage not listed; verify it is ≥ {required}W).'),
        }
    headroom = round((rated - draw) / draw * 100) if draw else 0
    if rated < draw * 1.1:
        return {
            'draw': draw, 'required': required, 'rated': rated, 'ok': False,
            'headroom_pct': headroom, 'red_flag': True,
            'message': (f'Selected {rated}W PSU is UNDER-SPEC for a ~{draw}W load — '
                        f'upgrade to at least {required}W.'),
        }
    if rated < required:
        return {
            'draw': draw, 'required': required, 'rated': rated, 'ok': True,
            'headroom_pct': headroom, 'red_flag': False,
            'message': (f'{rated}W PSU runs the ~{draw}W build with {headroom}% headroom — '
                        f'adequate, though {required}W is the comfortable target.'),
        }
    return {
        'draw': draw, 'required': required, 'rated': rated, 'ok': True,
        'headroom_pct': headroom, 'red_flag': False,
        'message': f'{rated}W PSU gives {headroom}% headroom over the ~{draw}W load — healthy.',
    }


def _tier(name, table):
    return _match(name, table, 5)


def bottleneck(selected: dict, purpose: str) -> dict:
    """CPU↔GPU balance read for the workload. Returns {'note', 'red_flag'}."""
    p = (purpose or '').lower()
    cpu = selected.get('CPU')
    gpu = selected.get('GPU')
    if 'office' in p or not gpu:
        return {'note': 'Integrated graphics — balanced for office/productivity', 'red_flag': False}

    g = _tier(_name(gpu), _GPU_TIER)
    c = _tier(_name(cpu), _CPU_TIER)
    creative = any(k in p for k in ('edit', 'content', 'render', 'video', 'ai', 'workstation'))

    if g - c >= 3:
        return {'note': f'⚠️ CPU may bottleneck this GPU (CPU {c}/10 vs GPU {g}/10) at lower resolutions',
                'red_flag': True}
    if creative and c - g >= 3:
        return {'note': f'GPU is light for this CPU on creative loads (CPU {c}/10 vs GPU {g}/10)',
                'red_flag': False}
    if g >= 8:
        return {'note': 'GPU-bound at 4K (healthy — the GPU is meant to lead here)', 'red_flag': False}
    return {'note': 'Balanced — no significant CPU/GPU bottleneck', 'red_flag': False}


def vrm_index(selected: dict) -> int:
    """0-100 comfort score for the board's VRM handling the CPU's draw. Higher =
    cooler/more stable. Heuristic: premium chipsets shrug off high-draw CPUs."""
    cpu = selected.get('CPU')
    mobo = selected.get('Motherboard')
    draw = _cpu_watts(_name(cpu)) if cpu else _CPU_DEFAULT_W
    board = _name(mobo)
    if re.search(r'\b(x870|x670|z790|z890|x570)', board):
        base = 95
    elif re.search(r'\b(b650|b850|b760|b660|b550)', board):
        base = 85
    else:
        base = 75
    # High-draw CPU on a modest board eats into the margin.
    penalty = max(0, (draw - 95)) // 10 * 3
    return max(55, min(99, base - penalty))


def reasoning_bullets(selected: dict, purpose: str, draw: int, platform, psu) -> list:
    """Per-component expert 'why' + synergy notes for the 🧠 Reasoning card."""
    p = (purpose or 'Gaming')
    bullets = []
    cpu = selected.get('CPU')
    gpu = selected.get('GPU')
    ram = selected.get('RAM')
    mobo = selected.get('Motherboard')
    storage = selected.get('Storage')

    if cpu:
        bullets.append(
            f'**CPU** — {cpu.name}: chosen as the {p.lower()} workhorse; its {platform or "socket"} '
            f'platform fixes the board + memory generation for guaranteed compatibility.'
        )
    if mobo and platform:
        gen = 'DDR4' if platform == 'AM4' else 'DDR5'
        bullets.append(
            f'**Motherboard** — {mobo.name}: matched to the {platform} socket and {gen}, so the '
            f'CPU/RAM drop in without a BIOS or voltage mismatch.'
        )
    if gpu:
        bullets.append(
            f'**GPU** — {gpu.name}: the primary performance driver for {p.lower()}; budget was '
            f'steered here after locking a coherent CPU/board base.'
        )
    else:
        bullets.append(
            '**GPU** — using the processor’s integrated graphics to stay in budget; a discrete '
            'card can be added later on the same board/PSU.'
        )
    if ram:
        bullets.append(
            f'**RAM** — {ram.name}: capacity/speed picked for {p.lower()} multitasking headroom; '
            f'enable the XMP/EXPO profile in BIOS to hit rated speed.'
        )
    if storage:
        bullets.append(
            f'**Storage** — {storage.name}: NVMe for fast boot/load and quick asset access.'
        )
    if psu:
        bullets.append(
            f'**Power** — {psu.get("message")}'
        )
    return bullets


def red_flags(selected: dict, psu: dict, bneck: dict) -> list:
    """Bold warnings to surface BEFORE the parts list (empty = clean build)."""
    flags = []
    if psu.get('red_flag'):
        flags.append(f'**🚩 PSU:** {psu.get("message")}')
    if bneck.get('red_flag'):
        flags.append(f'**🚩 Bottleneck:** {bneck.get("note")}')
    # RAM sanity: warn if a high-tier GPU is paired with only 8GB system RAM.
    ram = selected.get('RAM')
    gpu = selected.get('GPU')
    if ram and gpu and '8gb' in _name(ram) and _tier(_name(gpu), _GPU_TIER) >= 6:
        flags.append('**🚩 Memory:** 8GB system RAM is light for this GPU class — 16GB+ recommended.')
    return flags


def analyze(selected: dict, purpose: str, platform) -> dict:
    """One call → everything the formatter needs to render a smart recommendation."""
    draw = estimate_system_watts(selected)
    psu = psu_check(selected, draw)
    bneck = bottleneck(selected, purpose)
    return {
        'draw': draw,
        'psu': psu,
        'bottleneck': bneck,
        'vrm_index': vrm_index(selected),
        'reasoning': reasoning_bullets(selected, purpose, draw, platform, psu),
        'red_flags': red_flags(selected, psu, bneck),
    }
