"""
Deterministic PC-build compatibility validator (rule-based, no LLM, no guessing).

Given a selected build (slot → Component), `validate_build` runs every hard
compatibility rule from the engine spec and returns a structured verdict:

    {
      'compatible': bool,             # True only if NO hard rule fails
      'score': int,                   # 100 when clean; drops per failed rule
      'checks':  [ {rule, status, detail}, ... ],   # status: pass | fail | warn | skip
      'failures': [ {rule, detail, suggestions:[...]} ],
      'warnings': [str, ...],
    }

Rules implemented:
    CPU ↔ Motherboard   socket match · chipset family · DDR generation
    Motherboard ↔ RAM   DDR generation · capacity ≤ board max
    GPU ↔ PSU           wattage + 20% headroom · PCIe power connectors present
    GPU ↔ Case          card length ≤ case clearance
    CPU ↔ Cooler        socket support · cooler TDP ≥ CPU TDP
    Motherboard ↔ Storage  NVMe M.2 slot / SATA availability · PCIe gen
    PSU                 ≥ 80+ Bronze · whole-system draw + 20% margin

Specs come from Component.specs when seeded, else `hardware_specs.derive_specs`
as a live fallback, so the validator works even before the seeder runs.
A check whose inputs aren't confidently known is `skip`ped (never silently
passed) — the verdict says what could and could not be proven.
"""
from __future__ import annotations

from .hardware_specs import derive_specs, connector_count

# Whole-system non-CPU/GPU draw (board + RAM + drives + fans), watts.
_BASE_SYSTEM_W = 90
_PSU_HEADROOM = 1.20          # spec: total system power + 20% safety margin
_MIN_PSU_RATING_RANK = 1      # 80+ Bronze; ranks below reject


_RATING_RANK = {
    '80+ (unrated)': 0, '80+ white': 0, '80+ bronze': 1, '80+ silver': 2,
    '80+ gold': 3, '80+ platinum': 4, '80+ titanium': 5,
}


def specs_for(component, kind: str | None = None) -> dict:
    """Stored specs if present and structured, else derive from the name. When the
    caller passes a slot `kind` (the recommender knows the role) it wins over a
    stale stored kind, so a board mis-seeded as RAM still validates as a board."""
    raw = getattr(component, 'specs', None)
    if isinstance(raw, dict) and raw.get('kind') and (kind is None or raw['kind'] == kind):
        return raw
    return derive_specs(getattr(component, 'name', '') or '', kind)


def _name(c):
    return getattr(c, 'name', '') or '?'


def _cpu_load_w(cpu_specs):
    return cpu_specs.get('tdp_w') or 65


def _gpu_load_w(gpu_specs):
    return gpu_specs.get('tdp_w') or 0


def estimate_draw(slot_specs: dict) -> int:
    draw = _BASE_SYSTEM_W
    if slot_specs.get('CPU'):
        draw += _cpu_load_w(slot_specs['CPU'])
    if slot_specs.get('GPU'):
        draw += _gpu_load_w(slot_specs['GPU'])
    return int(draw)


def validate_build(selected: dict, alt_lookup=None) -> dict:
    """Validate a {slot: Component} build. `alt_lookup(slot, predicate)` (optional)
    returns candidate replacement Components for building the suggestion lists."""
    sp = {slot: specs_for(c, slot.lower()) for slot, c in selected.items() if c}
    parts = {slot: c for slot, c in selected.items() if c}
    checks: list[dict] = []
    failures: list[dict] = []
    warnings: list[str] = []

    def add(rule, status, detail, suggestions=None):
        checks.append({'rule': rule, 'status': status, 'detail': detail})
        if status == 'fail':
            failures.append({'rule': rule, 'detail': detail, 'suggestions': suggestions or []})
        elif status == 'warn':
            warnings.append(detail)

    cpu, mobo, ram = sp.get('CPU'), sp.get('Motherboard'), sp.get('RAM')
    gpu, psu, case = sp.get('GPU'), sp.get('PSU'), sp.get('Case')
    cooler, storage = sp.get('Cooler'), sp.get('Storage')

    # ---- CPU ↔ Motherboard -------------------------------------------------
    if cpu and mobo:
        c_sock, m_sock = cpu.get('socket'), mobo.get('socket')
        if not c_sock or not m_sock:
            add('CPU ↔ Motherboard socket', 'skip',
                'Socket not confidently known for one part — cannot prove the match.')
        elif c_sock == m_sock:
            add('CPU ↔ Motherboard socket', 'pass',
                f'Both use the {c_sock} socket.')
        else:
            add('CPU ↔ Motherboard socket', 'fail',
                f'CPU socket {c_sock} does not fit the {m_sock} motherboard.',
                _suggest_socket(alt_lookup, 'Motherboard', c_sock))
        # DDR generation agreement (CPU memory controller ↔ board).
        if cpu.get('ddr') and mobo.get('ddr'):
            if set(cpu['ddr']) & set(mobo['ddr']):
                add('CPU ↔ Motherboard memory', 'pass',
                    f'Memory generation matches ({"/".join(mobo["ddr"])}).')
            else:
                add('CPU ↔ Motherboard memory', 'fail',
                    f'CPU supports {"/".join(cpu["ddr"])} but board is {"/".join(mobo["ddr"])}.')
        # BIOS/firmware support: a newer CPU on an older same-socket chipset may
        # need a BIOS update before it will even boot. This is solvable without
        # any hardware change, so it is a 'warn' — never a hard 'fail' like a
        # true socket mismatch.
        if c_sock and m_sock and c_sock == m_sock and cpu.get('gen') and mobo.get('bios_gen_ceiling'):
            if cpu['gen'] > mobo['bios_gen_ceiling']:
                add('CPU ↔ Motherboard BIOS support', 'warn',
                    'This board\'s stock BIOS may predate this CPU — update the BIOS '
                    f'before first boot (board ships supporting up to the '
                    f'{mobo["bios_gen_ceiling"]} series/generation on this chipset).')
            else:
                add('CPU ↔ Motherboard BIOS support', 'pass',
                    'CPU generation is within this board\'s stock BIOS support.')
    elif cpu or mobo:
        add('CPU ↔ Motherboard socket', 'skip', 'CPU or motherboard missing from build.')

    # ---- Motherboard ↔ RAM -------------------------------------------------
    if mobo and ram:
        if ram.get('ddr') and mobo.get('ddr'):
            if ram['ddr'] in mobo['ddr']:
                add('Motherboard ↔ RAM generation', 'pass',
                    f'{ram["ddr"]} RAM matches the board.')
            else:
                add('Motherboard ↔ RAM generation', 'fail',
                    f'{ram["ddr"]} RAM cannot run on a {"/".join(mobo["ddr"])} board.',
                    _suggest_ram(alt_lookup, mobo['ddr']))
        else:
            add('Motherboard ↔ RAM generation', 'skip', 'RAM/board DDR generation unknown.')
        cap = (ram.get('capacity_gb') or 0) * (ram.get('modules') or 1)
        if mobo.get('max_ram_gb') and cap > mobo['max_ram_gb']:
            add('Motherboard ↔ RAM capacity', 'fail',
                f'{cap}GB exceeds the board limit of {mobo["max_ram_gb"]}GB.')
        elif cap:
            add('Motherboard ↔ RAM capacity', 'pass',
                f'{cap}GB is within the board limit ({mobo.get("max_ram_gb", "n/a")}GB).')

    # ---- GPU ↔ PSU + PSU rating + whole-system headroom --------------------
    draw = estimate_draw(sp)
    if psu:
        rated = psu.get('watts')
        rating = (psu.get('rating') or '').lower()
        rank = _RATING_RANK.get(rating, 0)
        # Required = the larger of (load + 20% margin) and the GPU vendor's stated
        # minimum PSU — a 4090 wants 850W even though its average draw + 20% is less.
        required = int(draw * _PSU_HEADROOM)
        if gpu and gpu.get('min_psu_w'):
            required = max(required, gpu['min_psu_w'])
        if rated is None:
            add('PSU capacity', 'skip', 'PSU wattage not listed — verify it is ≥ '
                f'{required}W for the ~{draw}W build.')
        elif rated < required:
            add('PSU capacity', 'fail',
                f'{rated}W PSU is under the ~{draw}W load + 20% margin ({required}W).',
                _suggest_psu(alt_lookup, required))
        else:
            add('PSU capacity', 'pass',
                f'{rated}W covers the ~{draw}W load with 20% margin ({required}W needed).')
        if rank < _MIN_PSU_RATING_RANK:
            add('PSU efficiency rating', 'fail' if rated else 'warn',
                f'PSU is below the 80+ Bronze minimum (rated "{psu.get("rating") or "unrated"}").',
                _suggest_psu(alt_lookup, int(draw * _PSU_HEADROOM)))
        else:
            add('PSU efficiency rating', 'pass', f'{psu.get("rating")} meets the 80+ Bronze minimum.')
        # PCIe power connector presence for a discrete card — an actual
        # comparison of what the PSU provides vs. what the GPU needs (previously
        # this only printed both values and unconditionally reported 'pass').
        if gpu and gpu.get('pcie_power') and psu.get('pcie_connectors'):
            conn_needed = connector_count(gpu['pcie_power'])
            conn_available = connector_count(psu['pcie_connectors'])
            if conn_available >= conn_needed:
                add('GPU ↔ PSU connectors', 'pass',
                    f'PSU\'s {psu["pcie_connectors"]} covers the GPU\'s {gpu["pcie_power"]} requirement.')
            else:
                add('GPU ↔ PSU connectors', 'fail',
                    f'PSU only provides {psu["pcie_connectors"]} — not enough for the GPU\'s '
                    f'{gpu["pcie_power"]} requirement.',
                    _suggest_psu(alt_lookup, required))

    # ---- GPU ↔ Case clearance ---------------------------------------------
    if gpu and case:
        glen, clear = gpu.get('length_mm'), case.get('gpu_clearance_mm')
        if glen and clear:
            if glen <= clear:
                add('GPU ↔ Case clearance', 'pass',
                    f'{glen}mm card fits the {clear}mm case clearance.')
            else:
                add('GPU ↔ Case clearance', 'fail',
                    f'{glen}mm card exceeds the {clear}mm case clearance.',
                    _suggest_case(alt_lookup, glen))

    # ---- GPU ↔ Motherboard / Storage ↔ Motherboard PCIe generation ---------
    # PCIe is backward/forward compatible — a slower board never blocks a build,
    # it only caps bandwidth. So a generation mismatch is a 'warn', never a
    # 'fail'; this was previously computed on both sides but never compared.
    if mobo and gpu and mobo.get('pcie_gen') and gpu.get('pcie_gen'):
        if gpu['pcie_gen'] <= mobo['pcie_gen']:
            add('GPU ↔ Motherboard PCIe generation', 'pass',
                f'PCIe Gen{gpu["pcie_gen"]} card runs at full speed on this Gen{mobo["pcie_gen"]} board.')
        else:
            add('GPU ↔ Motherboard PCIe generation', 'warn',
                f'PCIe Gen{gpu["pcie_gen"]} card will run at Gen{mobo["pcie_gen"]} speed on this '
                'board — it still works, just with capped bandwidth.')
    if mobo and storage and storage.get('pcie_gen') and mobo.get('pcie_gen'):
        if storage['pcie_gen'] <= mobo['pcie_gen']:
            add('Storage ↔ Motherboard PCIe generation', 'pass',
                f'PCIe Gen{storage["pcie_gen"]} drive runs at full speed on this Gen{mobo["pcie_gen"]} board.')
        else:
            add('Storage ↔ Motherboard PCIe generation', 'warn',
                f'PCIe Gen{storage["pcie_gen"]} drive will run at Gen{mobo["pcie_gen"]} speed on this '
                'board — it still works, just with capped bandwidth.')

    # ---- Cooler ↔ Case clearance -------------------------------------------
    if cooler and case:
        ch, cc = cooler.get('height_mm'), case.get('cooler_height_mm')
        if ch and cc:
            if ch <= cc:
                add('Cooler ↔ Case clearance', 'pass',
                    f'{ch}mm cooler fits the {cc}mm case clearance.')
            else:
                add('Cooler ↔ Case clearance', 'fail',
                    f'{ch}mm cooler exceeds the {cc}mm case clearance.',
                    [f'Use a case with ≥ {ch}mm cooler clearance, or pick a low-profile/AIO cooler.'])

    # ---- Motherboard ↔ Case form factor -----------------------------------
    if mobo and case:
        mf, supported = mobo.get('form_factor'), case.get('supported_form_factors') or []
        if mf and supported:
            if mf in supported:
                add('Motherboard ↔ Case form factor', 'pass',
                    f'{mf} board fits a case that takes {", ".join(supported)}.')
            else:
                add('Motherboard ↔ Case form factor', 'fail',
                    f'{mf} board does not fit this case ({", ".join(supported)} only).')

    # ---- CPU ↔ Cooler ------------------------------------------------------
    if cpu and cooler:
        c_sock = cpu.get('socket')
        socks = cooler.get('sockets') or []
        if c_sock and socks:
            if c_sock in socks:
                add('CPU ↔ Cooler socket', 'pass', f'Cooler supports {c_sock}.')
            else:
                add('CPU ↔ Cooler socket', 'fail',
                    f'Cooler does not list the {c_sock} socket.')
        if cooler.get('tdp_rating_w') and cpu.get('tdp_w'):
            if cooler['tdp_rating_w'] >= cpu['tdp_w']:
                add('CPU ↔ Cooler capacity', 'pass',
                    f'Cooler ({cooler["tdp_rating_w"]}W) handles the CPU\'s {cpu["tdp_w"]}W.')
            else:
                add('CPU ↔ Cooler capacity', 'warn',
                    f'Cooler ({cooler["tdp_rating_w"]}W) is light for the CPU\'s {cpu["tdp_w"]}W draw.')

    # ---- Motherboard ↔ Storage --------------------------------------------
    if mobo and storage:
        iface = storage.get('interface')
        if iface == 'NVMe':
            if (mobo.get('m2_slots') or 0) >= 1:
                add('Motherboard ↔ Storage', 'pass',
                    f'Board has {mobo["m2_slots"]} M.2 slot(s) for the NVMe drive.')
            else:
                add('Motherboard ↔ Storage', 'fail', 'No M.2 slot for this NVMe drive.')
        elif iface == 'SATA':
            if (mobo.get('sata_ports') or 0) >= 1:
                add('Motherboard ↔ Storage', 'pass',
                    f'Board has {mobo["sata_ports"]} SATA port(s) for the drive.')
            else:
                add('Motherboard ↔ Storage', 'fail', 'No SATA port for this drive.')

    # No discrete GPU → integrated graphics requires an iGPU-capable CPU.
    if not gpu and cpu:
        if cpu.get('igpu'):
            add('Display output', 'pass', 'CPU has integrated graphics — no discrete card required.')
        else:
            add('Display output', 'fail',
                f'No GPU and {_name(parts.get("CPU"))} has no integrated graphics — '
                'add a discrete card or pick an iGPU CPU.')

    n_fail = len(failures)
    n_warn = len(warnings)
    score = max(0, 100 - n_fail * 25 - n_warn * 5)
    return {
        'compatible': n_fail == 0,
        'score': 100 if (n_fail == 0 and n_warn == 0) else score,
        'estimated_draw_w': draw,
        'checks': checks,
        'failures': failures,
        'warnings': warnings,
    }


# --- Structured alternative suggestions (best-effort; need an alt_lookup) ----

def _suggest_socket(alt_lookup, slot, socket):
    if not alt_lookup or not socket:
        return [f'Replace the motherboard with a {socket} board.']
    rows = alt_lookup(slot, lambda s: s.get('socket') == socket) or []
    return [f'{_name(c)}' for c in rows[:3]] or [f'Replace with a {socket} motherboard.']


def _suggest_ram(alt_lookup, ddr_list):
    gen = ddr_list[0] if ddr_list else 'matching'
    if not alt_lookup:
        return [f'Use a {gen} memory kit.']
    rows = alt_lookup('RAM', lambda s: s.get('ddr') in ddr_list) or []
    return [_name(c) for c in rows[:3]] or [f'Use a {gen} memory kit.']


def _suggest_psu(alt_lookup, required_w):
    if not alt_lookup:
        return [f'Use a PSU rated ≥ {required_w}W, 80+ Bronze or better.']
    rows = alt_lookup('PSU', lambda s: (s.get('watts') or 0) >= required_w
                      and _RATING_RANK.get((s.get('rating') or '').lower(), 0) >= 1) or []
    return [_name(c) for c in rows[:3]] or [f'Use a PSU ≥ {required_w}W (80+ Bronze+).']


def _suggest_case(alt_lookup, gpu_len):
    if not alt_lookup:
        return [f'Use a case with ≥ {gpu_len}mm GPU clearance.']
    rows = alt_lookup('Case', lambda s: (s.get('gpu_clearance_mm') or 0) >= gpu_len) or []
    return [_name(c) for c in rows[:3]] or [f'Use a case with ≥ {gpu_len}mm GPU clearance.']
