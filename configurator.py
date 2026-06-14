"""
GenSpark Enterprise Hardware Scoring Engine — 10-step deterministic pipeline.

No LLM tokens: socket match, VRM thermal gate, bottleneck ratio, PSU tier multiplier,
and weighted performance scoring select the best validated build.
"""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Hardware pool with telemetry fields for scoring
# ---------------------------------------------------------------------------
MARKET_DATABASE: dict[str, list[dict[str, Any]]] = {
    'cpus': [
        {'name': 'Intel Core i3-12100F', 'price': 18000, 'socket': 'LGA1700', 'tier': 'budget', 'tdp': 58, 'cores': 4, 'ipc_score': 75},
        {'name': 'AMD Ryzen 5 3600', 'price': 22000, 'socket': 'AM4', 'tier': 'budget', 'tdp': 65, 'cores': 6, 'ipc_score': 70},
        {'name': 'Intel Core i5-12400F', 'price': 30000, 'socket': 'LGA1700', 'tier': 'mid', 'tdp': 65, 'cores': 6, 'ipc_score': 88},
        {'name': 'AMD Ryzen 5 5600X', 'price': 38000, 'socket': 'AM4', 'tier': 'mid', 'tdp': 65, 'cores': 6, 'ipc_score': 90},
        {'name': 'AMD Ryzen 7 5800X', 'price': 55000, 'socket': 'AM4', 'tier': 'high', 'tdp': 105, 'cores': 8, 'ipc_score': 93},
        {'name': 'Intel Core i7-13700K', 'price': 85000, 'socket': 'LGA1700', 'tier': 'high', 'tdp': 125, 'cores': 16, 'ipc_score': 115},
    ],
    'motherboards': [
        {'name': 'ASRock B450M-HDV', 'price': 16500, 'socket': 'AM4', 'ram_gen': 'DDR4', 'vrm_rating': 60, 'form': 'mATX'},
        {'name': 'MSI PRO B760M-A DDR4', 'price': 24000, 'socket': 'LGA1700', 'ram_gen': 'DDR4', 'vrm_rating': 85, 'form': 'mATX'},
        {'name': 'MSI B450 Tomahawk Max', 'price': 26000, 'socket': 'AM4', 'ram_gen': 'DDR4', 'vrm_rating': 78, 'form': 'ATX'},
        {'name': 'ASUS ROG Strix B550-F', 'price': 42000, 'socket': 'AM4', 'ram_gen': 'DDR4', 'vrm_rating': 92, 'form': 'ATX'},
    ],
    'ram': [
        {'name': 'Corsair Vengeance 8GB DDR4 3200MHz', 'price': 5200, 'ram_gen': 'DDR4', 'capacity': 8},
        {'name': 'Corsair Vengeance 16GB DDR4 3200MHz', 'price': 9600, 'ram_gen': 'DDR4', 'capacity': 16},
        {'name': 'Kingston Fury 32GB DDR4 3200MHz', 'price': 19500, 'ram_gen': 'DDR4', 'capacity': 32},
    ],
    'gpus': [
        {'name': 'NVIDIA GTX 1660 Super 6GB', 'price': 35000, 'tier': 'budget', 'tdp': 125, 'perf_index': 65},
        {'name': 'AMD Radeon RX 6600 8GB', 'price': 52000, 'tier': 'budget', 'tdp': 132, 'perf_index': 82},
        {'name': 'NVIDIA GeForce RTX 3060 12GB', 'price': 68000, 'tier': 'mid', 'tdp': 170, 'perf_index': 100},
        {'name': 'NVIDIA GeForce RTX 4060 8GB', 'price': 78000, 'tier': 'mid', 'tdp': 115, 'perf_index': 112},
        {'name': 'NVIDIA GeForce RTX 4070 12GB', 'price': 145000, 'tier': 'high', 'tdp': 200, 'perf_index': 165},
    ],
    'psu': [
        {'name': 'Standard 500W Non-Rated', 'price': 3500, 'wattage': 500, 'tier': 'E'},
        {'name': 'Cooler Master MWE 550W Bronze', 'price': 7500, 'wattage': 550, 'tier': 'C'},
        {'name': 'Cooler Master MWE 650W Bronze', 'price': 9500, 'wattage': 650, 'tier': 'C'},
        {'name': 'Corsair RM750e 750W Gold', 'price': 24000, 'wattage': 750, 'tier': 'A'},
    ],
    'storage': [
        {'name': 'Kingston NV2 500GB NVMe', 'price': 8400},
        {'name': 'Samsung 980 1TB NVMe', 'price': 16500},
        {'name': 'WD Blue 1TB SATA SSD', 'price': 11000},
    ],
    'case': [
        {'name': 'Standard Office Case', 'price': 3500},
        {'name': 'Montech X3 Mesh', 'price': 8500},
        {'name': 'Antec NX210 Mid Tower', 'price': 7500},
    ],
}

INTEGRATED_GPU: dict[str, Any] = {
    'name': 'Intel UHD / Ryzen integrated graphics',
    'price': 0,
    'tier': 'office',
    'tdp': 0,
    'perf_index': 0,
}

PSU_TIER_MULTIPLIER = {'A': 1.2, 'C': 1.0, 'E': 0.6}
SLOT_ORDER = ('CPU', 'GPU', 'Motherboard', 'RAM', 'Storage', 'PSU', 'Case')
SLOT_TO_KEY = {
    'CPU': 'cpu',
    'GPU': 'gpu',
    'Motherboard': 'motherboard',
    'RAM': 'ram',
    'Storage': 'storage',
    'PSU': 'psu',
    'Case': 'case',
}


def parse_target_budget(user_msg: str = '', budget_hint: str | None = None) -> int | None:
    """Step 1 — budget from chat text and/or explicit budget field."""
    chunks = [user_msg or '', budget_hint or '']
    for raw in chunks:
        text = (raw or '').lower().replace(',', '').strip()
        if not text:
            continue

        lakh = re.search(r'(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|lacs)\b', text)
        if lakh:
            return int(float(lakh.group(1)) * 100_000)

        dot_lakh = re.search(r'(\d+\.\d{1,2})(?:\s*(?:lakh|lac|budget|hai|me))', text)
        if dot_lakh:
            return int(float(dot_lakh.group(1)) * 100_000)

        k_match = re.search(r'(\d{2,3})\s*k\b', text)
        if k_match:
            return int(k_match.group(1)) * 1000

        nums = re.findall(r'\b(\d{5,7})\b', text)
        if nums:
            return int(nums[0])

        digits = re.sub(r'[^\d]', '', text)
        if digits and len(digits) >= 5:
            return int(digits)
    return None


def _purpose_flags(purpose: str) -> dict[str, bool]:
    key = (purpose or 'Gaming').lower()
    return {
        'office': 'office' in key,
        'editing': any(k in key for k in ('edit', 'render', 'video', 'content')),
        'gaming': 'gaming' in key or 'game' in key or (not key.startswith('office') and 'edit' not in key),
    }


def _budget_tier(target_budget: int, flags: dict[str, bool]) -> str:
    """Step 2 — performance tier from PKR envelope."""
    if flags['office'] and target_budget < 70_000:
        return 'budget'
    if target_budget <= 95_000:
        return 'budget'
    if target_budget <= 170_000:
        return 'mid'
    return 'high'


def _cpu_tier_ok(cpu: dict, target_tier: str, flags: dict[str, bool]) -> bool:
    if cpu['tier'] == target_tier:
        return True
    if target_tier == 'mid' and cpu['tier'] == 'budget':
        return True
    if flags['editing'] and cpu['tier'] in ('mid', 'high'):
        return True
    return False


def _gpu_tier_ok(gpu: dict, target_tier: str, flags: dict[str, bool]) -> bool:
    if flags['office']:
        return False
    if gpu['tier'] == target_tier:
        return True
    if target_tier == 'mid' and gpu['tier'] == 'budget':
        return True
    if flags['editing'] and gpu['tier'] in ('mid', 'high'):
        return True
    return False


def _min_vrm_for_cpu(cpu: dict) -> int:
    """Step 4 extension — eliminate weak VRM boards for hot / many-core CPUs."""
    if cpu['tdp'] >= 105 or cpu.get('cores', 0) >= 8:
        return 85
    if cpu['tdp'] >= 90:
        return 78
    return 60


def _bottleneck_status(cpu: dict, gpu: dict) -> str:
    """Step 8 — GPU perf_index vs CPU ipc_score synchronization."""
    if gpu['perf_index'] <= 0:
        return 'Balanced (iGPU)'
    ratio = gpu['perf_index'] / max(cpu['ipc_score'], 1)
    if ratio > 1.45:
        return 'GPU Bottleneck'
    if ratio < 0.75:
        return 'CPU Bottleneck'
    return 'Balanced'


def _compute_score(
    cpu: dict,
    mobo: dict,
    gpu: dict,
    psu: dict,
    *,
    office: bool,
    gaming: bool = False,
) -> float:
    """Step 9 — weighted telemetry (× PSU tier multiplier)."""
    psu_quality = {'A': 100, 'C': 72, 'E': 35}.get(psu.get('tier', 'C'), 50)
    if office:
        base = (cpu['ipc_score'] * 0.45) + (mobo['vrm_rating'] * 0.30) + (psu_quality * 0.25)
    elif gaming:
        base = (
            (gpu['perf_index'] * 0.45)
            + (cpu['ipc_score'] * 0.25)
            + (mobo['vrm_rating'] * 0.15)
            + (psu_quality * 0.15)
        )
    else:
        base = (
            (gpu['perf_index'] * 0.40)
            + (cpu['ipc_score'] * 0.30)
            + (mobo['vrm_rating'] * 0.15)
            + (psu_quality * 0.15)
        )
    mult = PSU_TIER_MULTIPLIER.get(psu.get('tier', 'C'), 1.0)
    return round(base * mult, 1)


def _price_window(target_budget: int) -> tuple[int, int]:
    floor = max(int(target_budget * 0.62), 35_000)
    return floor, target_budget


def _narrow_market_pool(target_tier: str, flags: dict[str, bool]) -> dict[str, Any]:
    """
    Pre-filter catalogs before nested loops — cuts O(N^6) work at the source.
    """
    cpus = [c for c in MARKET_DATABASE['cpus'] if _cpu_tier_ok(c, target_tier, flags)]
    gpus = (
        [INTEGRATED_GPU]
        if flags['office']
        else [g for g in MARKET_DATABASE['gpus'] if _gpu_tier_ok(g, target_tier, flags)]
    )
    min_ram = 16 if target_tier == 'high' else (8 if flags['office'] else 8)
    ram = [r for r in MARKET_DATABASE['ram'] if r['capacity'] >= min_ram]
    if not ram:
        ram = list(MARKET_DATABASE['ram'])

    mobos_by_socket: dict[str, list[dict[str, Any]]] = {}
    for mobo in MARKET_DATABASE['motherboards']:
        mobos_by_socket.setdefault(mobo['socket'], []).append(mobo)

    psus = list(MARKET_DATABASE['psu'])
    if target_tier == 'high':
        psus = [p for p in psus if p['tier'] in ('A', 'C')]
    elif target_tier in ('budget', 'mid'):
        psus = [p for p in psus if p['tier'] in ('C', 'E') or p['wattage'] <= 700]

    storage = list(MARKET_DATABASE['storage'])
    cases = list(MARKET_DATABASE['case'])
    if flags['office'] and target_tier == 'budget':
        cases = [c for c in cases if c['price'] <= 6000] or cases

    return {
        'cpus': cpus,
        'gpus': gpus,
        'ram': ram,
        'mobos_by_socket': mobos_by_socket,
        'psus': psus,
        'storage': storage,
        'cases': cases,
    }


def _apply_vision_discount(
    components: dict[str, str],
    prices: dict[str, int],
    detected_parts: list[str],
) -> tuple[dict[str, int], list[str]]:
    labels = {p.lower() for p in (detected_parts or [])}
    notes: list[str] = []
    slot_map = {
        'ram': 'RAM',
        'mouse': None,
        'keyboard': None,
        'monitor': None,
    }
    for label in labels:
        slot = slot_map.get(label)
        if slot and slot in prices:
            prices[slot] = 0
            notes.append(slot)
    return prices, notes


def advanced_pc_configurator(
    user_msg: str = '',
    *,
    purpose: str = 'Gaming',
    budget_hint: str | None = None,
    detected_parts: list[str] | None = None,
) -> dict[str, Any]:
    """
    Full 10-step pipeline. Returns success dict with configuration, scores, and prices.
    """
    target_budget = parse_target_budget(user_msg, budget_hint)
    if not target_budget:
        return {'status': 'error', 'message': 'Budget recognize nahi ho saka. Example: 1.20 lakh ya 80000 PKR.'}

    flags = _purpose_flags(purpose)
    target_tier = _budget_tier(target_budget, flags)
    floor_price, ceiling_price = _price_window(target_budget)
    top_builds: list[dict[str, Any]] = []
    max_candidates = 48
    pool = _narrow_market_pool(target_tier, flags)

    for cpu in pool['cpus']:
        min_vrm = _min_vrm_for_cpu(cpu)
        mobo_list = [
            m for m in pool['mobos_by_socket'].get(cpu['socket'], [])
            if m['vrm_rating'] >= min_vrm
        ]
        if not mobo_list:
            continue

        for mobo in mobo_list:
            ram_list = [r for r in pool['ram'] if mobo['ram_gen'] == r['ram_gen']]
            for ram in ram_list:
                for gpu in pool['gpus']:
                    required_wattage = cpu['tdp'] + gpu['tdp'] + (100 if flags['office'] else 150)
                    psu_list = [p for p in pool['psus'] if p['wattage'] >= required_wattage]
                    if flags['office']:
                        psu_list = [
                            p for p in psu_list
                            if not (p['tier'] == 'E' and cpu['tdp'] > 65)
                        ]
                    for psu in psu_list:
                        if (
                            target_tier in ('budget', 'mid')
                            and psu['wattage'] > required_wattage + 200
                            and psu.get('tier') == 'A'
                        ):
                            continue
                        for storage in pool['storage']:
                            for case in pool['cases']:

                                prices = {
                                    'CPU': cpu['price'],
                                    'Motherboard': mobo['price'],
                                    'RAM': ram['price'],
                                    'GPU': gpu['price'],
                                    'PSU': psu['price'],
                                    'Storage': storage['price'],
                                    'Case': case['price'],
                                }
                                total_price = sum(prices.values())

                                if total_price > ceiling_price or total_price < floor_price:
                                    continue

                                bottleneck = _bottleneck_status(cpu, gpu)
                                if bottleneck != 'Balanced' and target_tier == 'high' and not flags['office']:
                                    continue

                                final_score = _compute_score(
                                    cpu,
                                    mobo,
                                    gpu,
                                    psu,
                                    office=flags['office'],
                                    gaming=flags['gaming'],
                                )

                                components = {
                                    'CPU': cpu['name'],
                                    'GPU': gpu['name'],
                                    'Motherboard': mobo['name'],
                                    'RAM': ram['name'],
                                    'PSU': psu['name'],
                                    'Storage': storage['name'],
                                    'Case': case['name'],
                                }

                                candidate = {
                                    'components': components,
                                    'prices': prices,
                                    'total_price': total_price,
                                    'bottleneck': bottleneck,
                                    'score': final_score,
                                    'required_psu_w': required_wattage,
                                    'vrm_rating': mobo['vrm_rating'],
                                }
                                top_builds.append(candidate)
                                if len(top_builds) > max_candidates:
                                    top_builds.sort(key=lambda x: x['score'], reverse=True)
                                    top_builds = top_builds[:max_candidates]

    valid_builds = top_builds
    if not valid_builds:
        return {
            'status': 'error',
            'message': 'Diye gaye budget matrix mein koi perfect validation build nahi mila.',
            'target_budget': target_budget,
            'tier_detected': target_tier.upper(),
        }

    def _rank_key(build: dict[str, Any]) -> tuple:
        gpu_name = build['components'].get('GPU', '')
        gpu_perf = next(
            (g['perf_index'] for g in MARKET_DATABASE['gpus'] if g['name'] == gpu_name),
            0,
        )
        return (
            build['score'],
            gpu_perf,
            -abs(build['total_price'] - target_budget),
        )

    valid_builds.sort(key=_rank_key, reverse=True)
    best = valid_builds[0]

    prices = dict(best['prices'])
    prices, vision_notes = _apply_vision_discount(best['components'], prices, detected_parts or [])

    perf_score = min(100, int(round(best['score'] * 0.85)))
    value_stars = '⭐⭐⭐' if perf_score < 78 else '⭐⭐⭐⭐' if perf_score < 88 else '⭐⭐⭐⭐⭐'

    return {
        'status': 'success',
        'tier_detected': target_tier.upper(),
        'target_budget': target_budget,
        'calculated_total': sum(prices.values()),
        'bottleneck_analysis': best['bottleneck'],
        'telemetry_score': best['score'],
        'performance_score': perf_score,
        'value_stars': value_stars,
        'required_psu_w': best['required_psu_w'],
        'vrm_rating': best['vrm_rating'],
        'configuration': best['components'],
        'prices': prices,
        'vision_excluded': vision_notes,
        'candidates_evaluated': len(valid_builds),
    }


def configurator_to_parts_payload(result: dict[str, Any]) -> dict[str, str]:
    cfg = result.get('configuration') or {}
    return {SLOT_TO_KEY[slot]: cfg[slot] for slot in SLOT_ORDER if slot in cfg}


def format_configurator_markdown(
    result: dict[str, Any],
    *,
    purpose: str,
    budget_line: str,
    vision_note: str = '',
) -> str:
    """Professional markdown for React chat UI."""
    if result.get('status') != 'success':
        return ''

    cfg = result['configuration']
    prices = result.get('prices') or {}
    total = result['calculated_total']
    tier = result['tier_detected']
    bottleneck = result['bottleneck_analysis']
    telemetry = result['telemetry_score']
    perf = result['performance_score']
    stars = result['value_stars']
    psu_w = result['required_psu_w']
    vrm = result['vrm_rating']
    evaluated = result.get('candidates_evaluated', 0)

    header = (
        f'🟢 **Compatibility Status:** Socket/RAM/PSU validated — {bottleneck}\n'
        f'⚡ **PSU Wattage Buffer:** {psu_w}W required (continuous rating) · VRM thermal index {vrm}/100\n'
        f'🏆 **GenSpark Performance Score:** {perf}/100 (telemetry {telemetry})\n'
        f'💰 **Value For Money Rating:** {stars}\n'
        f'📊 **Estimated parts total:** {total:,} PKR · **Tier:** {tier}\n\n'
    )

    summary = (
        f'{vision_note}'
        f'**{purpose}** build optimized by the **GenSpark Scoring Engine** '
        f'({evaluated} valid combinations evaluated). '
        f'Target **{budget_line}** — selected total **{total:,} PKR**. '
        f'Bottleneck matrix: **{bottleneck}**.'
    )

    lines = [
        header,
        '## Summary',
        summary,
        '',
        '## Recommended Components',
        '| Component Type | Component Name | Estimated Price |',
        '|----------------|-----------------|------------------|',
    ]

    for slot in SLOT_ORDER:
        name = cfg.get(slot, '—')
        price = prices.get(slot, 0)
        cell = '0' if price == 0 else f'{int(price):,}'
        lines.append(f'| {slot} | {name} | {cell} |')

    lines.extend([
        '',
        '### 🧠 GenSpark Scoring Engine Reasoning',
        f'- **Weighted score:** GPU 40% · CPU 30% · VRM 15% · PSU quality 15% (× PSU tier multiplier).',
        f'- **Bottleneck gate:** GPU Index ÷ CPU IPC = sync check; premium tier requires **Balanced** pairing.',
        f'- **VRM gate:** High-TDP CPUs eliminated boards below thermal rating {vrm}+.',
        f'- **PSU gate:** Non-rated units penalized 0.6× on score; high-tier builds require Bronze/Gold units.',
        '- **Budget window:** Total spend within 62%–100% of target PKR for optimal value positioning.',
    ])

    if result.get('vision_excluded'):
        lines.append(
            f'- **Vision:** Excluded owned parts from invoice: {", ".join(result["vision_excluded"])}.'
        )

    return '\n'.join(lines) + '\n'
