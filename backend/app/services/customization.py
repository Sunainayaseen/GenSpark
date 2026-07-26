"""
Customization decision-support engine — the "Intelligent Decision Support System".

Phase 1 (compatibility.py) answers *"is this build electrically/physically valid?"*.
This layer answers the harder product question for a SINGLE user edit:

    Not just "can I?" but "should I, what will it cost, and what else must change?"

`evaluate_change(build, slot, new_part, purpose, budget)` runs the decision tree and
returns one of four levels:

    fully_compatible   ✅  valid AND worthwhile for the stated workload
    unnecessary        ⚠️  valid but overkill for the workload (minimal real gain)
    needs_adjustments  🔄  the part works, but supporting parts must change (PSU auto;
                            case/cooler recommended for the user to confirm)
    incompatible       ❌  a platform mismatch (socket / DDR gen / capacity) — blocked,
                            with concrete in-stock alternatives

Design decisions (confirmed with product owner):
  * Platform mismatches (socket, DDR generation, RAM-over-capacity) are ❌ — the part
    cannot work as-is; we never silently swap the board out from under the user.
  * The ONLY component auto-applied to resolve a 🔄 is the PSU. Case/cooler upgrades are
    surfaced as recommendations (auto_apply=False) for the user to accept.

Verdicts carry both a Beginner (plain) and Advanced (technical) explanation so the UI
can serve technical and non-technical users from one evaluation.
"""
from __future__ import annotations

import math

from . import build_intelligence as bi
from .compatibility import validate_build, specs_for, _RATING_RANK, _PSU_HEADROOM

# Failures that mean "the chosen part fundamentally won't work here" → hard block.
_HARD_RULES = {
    'CPU ↔ Motherboard socket', 'CPU ↔ Motherboard memory',
    'Motherboard ↔ RAM generation', 'Motherboard ↔ RAM capacity',
    'Motherboard ↔ Storage', 'Display output',
}
# Failures fixable by upgrading a SUPPORTING part → "compatible after adjustments".
_ADJUSTABLE_RULES = {
    'PSU capacity', 'PSU efficiency rating',
    'GPU ↔ Case clearance', 'Motherboard ↔ Case form factor',
    'CPU ↔ Cooler socket', 'CPU ↔ Cooler capacity',
}
# Slots the engine may auto-apply vs. recommend (product decision: PSU auto only).
_AUTO_APPLY_SLOTS = {'PSU'}

# Workload sufficiency: RAM (GB) and GPU/CPU performance tier (0-10) beyond which
# more brings little real-world benefit for that use case.
_RAM_SUFFICIENT_GB = {
    'office': 16, 'student': 16, 'programming': 32, 'gaming': 32,
    'editing': 64, 'content': 64, 'video': 64, 'render': 64,
    'ai': 128, 'workstation': 128,
}
_GPU_SUFFICIENT_TIER = {
    'office': 0, 'student': 2, 'programming': 4, 'gaming': 8,
    'editing': 7, 'content': 7, 'video': 7, 'render': 7,
    'ai': 9, 'workstation': 9,
}
_CPU_SUFFICIENT_TIER = {
    'office': 4, 'student': 4, 'programming': 7, 'gaming': 7,
    'editing': 9, 'content': 9, 'video': 9, 'render': 9,
    'ai': 9, 'workstation': 9,
}

_LEVEL_LABEL = {
    'fully_compatible': '✅ Fully Compatible',
    'unnecessary': '⚠️ Compatible but Unnecessary',
    'needs_adjustments': '🔄 Compatible After Adjustments',
    'incompatible': '❌ Incompatible',
}


def _price(c):
    return float(getattr(c, 'price', 0) or 0)


def _name(c):
    return getattr(c, 'name', '') or '?'


def _purpose_key(purpose, table, default):
    p = (purpose or '').lower()
    for key in table:
        if key in p:
            return table[key]
    return default


def _alt_lookup_from(cand_for):
    """Adapt a `cand_for(slot)->[Component]` provider into the validator's
    `alt_lookup(slot, predicate)`."""
    if not cand_for:
        return None

    def lookup(slot, predicate):
        return [c for c in (cand_for(slot) or []) if predicate(specs_for(c, slot.lower()))]
    return lookup


# --------------------------------------------------------------------------- #
# Relevance — is the upgrade worthwhile for the workload, or overkill?
# --------------------------------------------------------------------------- #
def _assess_relevance(slot, old_c, new_c, purpose):
    s = slot.upper()
    if s == 'RAM':
        ns = specs_for(new_c, 'ram')
        cap = (ns.get('capacity_gb') or 0) * (ns.get('modules') or 1)
        enough = _purpose_key(purpose, _RAM_SUFFICIENT_GB, 16)
        if cap > enough * 2:
            return {'suitable': False,
                    'note': f'{cap}GB is supported, but {enough}GB already covers a '
                            f'{(purpose or "general").lower()} workload — the extra capacity '
                            f'adds little real-world benefit.',
                    'suggested': f'{enough}GB (or {enough * 2}GB for headroom)'}
        return {'suitable': True,
                'note': f'{cap}GB suits a {(purpose or "general").lower()} workload.',
                'suggested': None}
    if s == 'GPU':
        tier = bi._tier(bi._name(new_c), bi._GPU_TIER)
        enough = _purpose_key(purpose, _GPU_SUFFICIENT_TIER, 5)
        if tier > enough + 2:
            return {'suitable': False,
                    'note': f'This GPU (tier {tier}/10) far exceeds what a '
                            f'{(purpose or "general").lower()} workload uses (≈{enough}/10); '
                            f'the spend won\'t translate into matching real-world gain.',
                    'suggested': 'a GPU around tier '
                                 f'{min(10, enough + 1)}/10 for the same workload'}
        return {'suitable': True, 'note': 'GPU class matches the workload.', 'suggested': None}
    if s == 'CPU':
        tier = bi._tier(bi._name(new_c), bi._CPU_TIER)
        enough = _purpose_key(purpose, _CPU_SUFFICIENT_TIER, 5)
        if tier > enough + 2:
            return {'suitable': False,
                    'note': f'This CPU (tier {tier}/10) is heavier than a '
                            f'{(purpose or "general").lower()} workload needs (≈{enough}/10).',
                    'suggested': f'a CPU around tier {min(10, enough + 1)}/10'}
        return {'suitable': True, 'note': 'CPU class matches the workload.', 'suggested': None}
    # Storage / PSU / others: more is not "harmful overkill" — treat as suitable.
    return {'suitable': True, 'note': 'Selection is appropriate for the build.', 'suggested': None}


# --------------------------------------------------------------------------- #
# Performance impact of the change (minimal | moderate | significant)
# --------------------------------------------------------------------------- #
def _assess_performance(slot, old_c, new_c, level):
    s = slot.upper()
    if level == 'unnecessary':
        return {'impact': 'minimal', 'detail': 'Little measurable gain for this workload.'}

    def ram_gb(c):
        sp = specs_for(c, 'ram')
        return (sp.get('capacity_gb') or 0) * (sp.get('modules') or 1)

    if s == 'RAM' and old_c and new_c:
        o, n = ram_gb(old_c), ram_gb(new_c)
        if n <= o:
            return {'impact': 'none', 'detail': f'{n}GB is not an increase over {o}GB.'}
        ratio = n / max(o, 1)
        impact = 'significant' if ratio >= 2 else 'moderate'
        return {'impact': impact, 'detail': f'{o}GB → {n}GB.'}
    if s in ('GPU', 'CPU') and new_c:
        table = bi._GPU_TIER if s == 'GPU' else bi._CPU_TIER
        n = bi._tier(bi._name(new_c), table)
        o = bi._tier(bi._name(old_c), table) if old_c else 0
        if n <= o:
            return {'impact': 'none', 'detail': f'No tier increase ({o}/10 → {n}/10).'}
        diff = n - o
        impact = 'significant' if diff >= 3 else 'moderate' if diff >= 1 else 'minimal'
        return {'impact': impact, 'detail': f'Performance tier {o}/10 → {n}/10.'}
    if s == 'STORAGE':
        return {'impact': 'moderate', 'detail': 'More/faster storage capacity.'}
    return {'impact': 'moderate', 'detail': 'Component updated.'}


# --------------------------------------------------------------------------- #
# Resolve a 🔄 case: find supporting-part upgrades that make the build valid
# --------------------------------------------------------------------------- #
def _resolve_adjustments(modified, adjustable_failures, purpose, cand_for):
    """Return (changes, fully_resolved). `changes` are {slot, from, to, reason,
    price_delta, auto_apply}. PSU is auto-applied; case/cooler are recommendations."""
    changes = []
    rules = {f['rule'] for f in adjustable_failures}
    draw = None

    # PSU — upgrade to the cheapest in-stock unit clearing draw+20% at ≥ 80+ Bronze.
    if {'PSU capacity', 'PSU efficiency rating'} & rules:
        sp = {slot: specs_for(c, slot.lower()) for slot, c in modified.items() if c}
        from .compatibility import estimate_draw
        draw = estimate_draw(sp)
        required = math.ceil(draw * _PSU_HEADROOM)
        gpu_min = sp.get('GPU', {}).get('min_psu_w')
        if gpu_min:
            required = max(required, gpu_min)
        cur = modified.get('PSU')
        cands = [c for c in (cand_for('PSU') or [])
                 if (specs_for(c, 'psu').get('watts') or 0) >= required
                 and _RATING_RANK.get((specs_for(c, 'psu').get('rating') or '').lower(), 0) >= 1]
        if cands:
            best = min(cands, key=_price)
            changes.append({
                'slot': 'PSU', 'from': _name(cur) if cur else None, 'to': _name(best),
                'to_id': getattr(best, 'id', None),
                'reason': f'~{draw}W load needs ≥ {required}W (80+ Bronze+).',
                'price_delta': int(_price(best) - (_price(cur) if cur else 0)),
                'auto_apply': True,
            })
            modified['PSU'] = best

    # Case — recommend (not auto) the cheapest case that fits the GPU + board.
    if {'GPU ↔ Case clearance', 'Motherboard ↔ Case form factor'} & rules:
        gpu = modified.get('GPU')
        mobo = modified.get('Motherboard')
        glen = specs_for(gpu, 'gpu').get('length_mm') if gpu else 0
        mform = specs_for(mobo, 'motherboard').get('form_factor') if mobo else None
        cur = modified.get('Case')
        cands = []
        for c in (cand_for('Case') or []):
            cs = specs_for(c, 'case')
            if (cs.get('gpu_clearance_mm') or 0) >= (glen or 0) and \
               (not mform or mform in (cs.get('supported_form_factors') or [])):
                cands.append(c)
        if cands:
            best = min(cands, key=_price)
            changes.append({
                'slot': 'Case', 'from': _name(cur) if cur else None, 'to': _name(best),
                'to_id': getattr(best, 'id', None),
                'reason': f'Needs ≥ {glen}mm GPU clearance'
                          + (f' and {mform} support.' if mform else '.'),
                'price_delta': int(_price(best) - (_price(cur) if cur else 0)),
                'auto_apply': False,
            })
            modified['Case'] = best

    # Cooler — recommend a cooler rated for the CPU's draw (catalog coolers are generic).
    if {'CPU ↔ Cooler socket', 'CPU ↔ Cooler capacity'} & rules:
        cpu = modified.get('CPU')
        c_sock = specs_for(cpu, 'cpu').get('socket') if cpu else None
        need_w = specs_for(cpu, 'cpu').get('tdp_w') if cpu else 0
        cur = modified.get('Cooler')
        cands = []
        for c in (cand_for('Cooler') or []):
            cs = specs_for(c, 'cooler')
            if (not c_sock or c_sock in (cs.get('sockets') or [])) and \
               (cs.get('tdp_rating_w') or 0) >= (need_w or 0):
                cands.append(c)
        if cands:
            best = min(cands, key=_price)
            changes.append({
                'slot': 'Cooler', 'from': _name(cur) if cur else None, 'to': _name(best),
                'to_id': getattr(best, 'id', None),
                'reason': f'Cooler must support {c_sock} and ≥ {need_w}W.',
                'price_delta': int(_price(best) - (_price(cur) if cur else 0)),
                'auto_apply': False,
            })
            modified['Cooler'] = best

    # Did the adjustments actually clear every adjustable failure?
    recheck = validate_build(modified, _alt_lookup_from(cand_for))
    still = [f for f in recheck['failures'] if f['rule'] in _ADJUSTABLE_RULES]
    return changes, (len(still) == 0 and len(changes) > 0)


# --------------------------------------------------------------------------- #
# Explanations — Beginner (plain) and Advanced (technical)
# --------------------------------------------------------------------------- #
def _explain(level, slot, new_c, relevance, perf, budget_delta, changes, failures):
    cost = (f'+ Rs. {budget_delta:,}' if budget_delta > 0
            else (f'– Rs. {abs(budget_delta):,}' if budget_delta < 0 else 'No change'))
    if level == 'fully_compatible':
        beginner = (f'Works perfectly. This {slot.lower()} upgrade suits your needs.\n'
                    f'Additional cost: {cost}.')
        advanced = (f'{_name(new_c)} validated against the build. '
                    f'Performance impact: {perf["impact"]} ({perf["detail"]}). Cost: {cost}.')
    elif level == 'unnecessary':
        beginner = (f'This works, but it may be more than you need.\n{relevance["note"]}\n'
                    f'Extra cost: {cost}. Suggested: {relevance.get("suggested") or "a lower tier"}.')
        advanced = (f'Compatible, but workload-relevance check flags overkill: '
                    f'{relevance["note"]} Marginal performance gain ({perf["impact"]}). Cost: {cost}.')
    elif level == 'needs_adjustments':
        lines = [f'• {c["slot"]}: {c["from"] or "—"} → {c["to"]} '
                 f'({"auto" if c["auto_apply"] else "recommended"}, '
                 f'{"+Rs. %d" % c["price_delta"] if c["price_delta"] >= 0 else "-Rs. %d" % abs(c["price_delta"])})'
                 for c in changes]
        joined = '\n'.join(lines)
        beginner = (f'This works, but a few parts need to change to support it:\n{joined}\n'
                    f'Total additional cost: {cost}.\nApply these automatically?')
        advanced = (f'{_name(new_c)} is electrically valid; dependent parts must be updated to '
                    f'meet power/clearance rules:\n{joined}\nNet cost: {cost}.')
    else:  # incompatible
        reasons = '; '.join(f['detail'] for f in failures) or 'platform mismatch'
        alts = []
        for f in failures:
            alts.extend(f.get('suggestions') or [])
        alt_txt = '\n'.join(f'✓ {a}' for a in list(dict.fromkeys(alts))[:4]) if alts else '—'
        beginner = (f'This part won\'t work with your current build.\nReason: {reasons}\n'
                    f'Supported alternatives:\n{alt_txt}')
        advanced = (f'Hard compatibility failure: {reasons}. The selection cannot be used '
                    f'without a platform change. Alternatives:\n{alt_txt}')
    return {'beginner': beginner, 'advanced': advanced}


# --------------------------------------------------------------------------- #
# Proactive smart suggestions (rule-based — same workload thresholds as above)
# --------------------------------------------------------------------------- #
def suggest_upgrades(build: dict, purpose: str, budget_num: int | None, cand_for=None) -> list:
    """Rule-based proactive upgrade suggestions for the CURRENT build (the
    "chatbot suggests RAM upgrade" behaviour). Each suggestion names a concrete,
    compatible, in-stock part the user can apply in one click. Deterministic — it
    reuses the workload sufficiency thresholds, never an LLM.

    `cand_for(slot)` must return parts already compatible with the build (the
    endpoint passes the hard-filtered candidate lists)."""
    out = []

    def cheapest_at_least(slot, metric, minimum, current):
        cands = [
            c for c in (cand_for(slot) if cand_for else []) or []
            if (specs_for(c, slot.lower()).get(metric) or 0) >= minimum and _price(c) > _price(current)
        ]
        return min(cands, key=_price) if cands else None

    # RAM below the workload's recommended capacity → suggest the cheapest kit that meets it.
    ram = build.get('RAM')
    if ram:
        sp = specs_for(ram, 'ram')
        cap = (sp.get('capacity_gb') or 0) * (sp.get('modules') or 1)
        need = _purpose_key(purpose, _RAM_SUFFICIENT_GB, 16)
        if cap and cap < need:
            best = cheapest_at_least('RAM', 'capacity_gb', need, ram)
            if best:
                out.append({
                    'slot': 'ram', 'title': f'Upgrade to {need}GB RAM',
                    'detail': f'{cap}GB is light for {(purpose or "this").lower()} use — '
                              f'{need}GB gives smoother multitasking and future headroom.',
                    'to': {'id': best.id, 'name': best.name, 'price': int(_price(best))},
                    'price_delta': int(_price(best) - _price(ram)),
                })

    # Storage under 1TB → suggest the cheapest 1TB+ drive.
    st = build.get('Storage')
    if st:
        cap = specs_for(st, 'storage').get('capacity_gb') or 0
        if cap and cap < 1024:
            best = cheapest_at_least('Storage', 'capacity_gb', 1024, st)
            if best:
                out.append({
                    'slot': 'storage', 'title': 'Add a 1TB+ SSD',
                    'detail': f'{cap}GB fills up fast — a 1TB+ NVMe drive gives room for more '
                              'games/projects with no speed loss.',
                    'to': {'id': best.id, 'name': best.name, 'price': int(_price(best))},
                    'price_delta': int(_price(best) - _price(st)),
                })

    # PSU under the build's real requirement → suggest a bigger, rated unit.
    psu = build.get('PSU')
    if psu:
        sp_all = {s: specs_for(c, s.lower()) for s, c in build.items() if c}
        from .compatibility import estimate_draw
        draw = estimate_draw(sp_all)
        gpu_min = sp_all.get('GPU', {}).get('min_psu_w') or 0
        required = max(int(draw * _PSU_HEADROOM), gpu_min)
        rated = specs_for(psu, 'psu').get('watts') or 0
        if rated and rated < required:
            best = cheapest_at_least('PSU', 'watts', required, psu)
            if best:
                out.append({
                    'slot': 'psu', 'title': f'Upgrade PSU to ≥ {required}W',
                    'detail': f'The {rated}W unit is below the ~{draw}W load + 20% margin — '
                              f'a {required}W+ PSU runs the build safely.',
                    'to': {'id': best.id, 'name': best.name, 'price': int(_price(best))},
                    'price_delta': int(_price(best) - _price(psu)),
                })

    # CPU/GPU bottleneck — informational (no one-click part to apply).
    try:
        from . import build_intelligence as bi
        bn = bi.bottleneck(build, purpose)
        if bn.get('red_flag'):
            out.append({'slot': None, 'title': 'Balance warning', 'detail': bn['note'],
                        'to': None, 'price_delta': 0})
    except Exception:
        pass

    return out


# --------------------------------------------------------------------------- #
# The decision tree
# --------------------------------------------------------------------------- #
def evaluate_change(build: dict, slot: str, new_part, purpose: str,
                    budget_num: int | None = None, cand_for=None, mode: str = 'beginner') -> dict:
    """Evaluate replacing build[slot] with new_part. `build` is {Slot: Component}
    (title-case slots: CPU/GPU/RAM/Storage/PSU/Motherboard/Case/Cooler). `cand_for`
    (slot)->[Component] supplies in-stock candidates for alternatives/adjustments."""
    slot = slot.strip().title() if slot.lower() != 'cpu' else 'CPU'
    slot = {'Cpu': 'CPU', 'Gpu': 'GPU', 'Ram': 'RAM', 'Psu': 'PSU'}.get(slot, slot)
    old_part = build.get(slot)

    modified = dict(build)
    modified[slot] = new_part

    old_total = sum(_price(c) for c in build.values() if c)
    new_total_base = sum(_price(c) for c in modified.values() if c)

    alt_lookup = _alt_lookup_from(cand_for)
    result = validate_build(modified, alt_lookup)
    hard = [f for f in result['failures'] if f['rule'] in _HARD_RULES]
    adjustable = [f for f in result['failures'] if f['rule'] in _ADJUSTABLE_RULES]

    # Single-vendor-per-build: assembly is done by the supplying vendor, so a swap
    # that leaves no single vendor able to supply the whole build is a hard block —
    # takes priority over hardware compatibility, never silently allowed through.
    #
    # Must check against the vendor ALREADY locked to the current (pre-swap) build,
    # not re-derive a fresh "best" vendor for the modified combination — otherwise
    # this can pass by picking a different vendor than the one actually supplying
    # the rest of the cart, while /api/build-options' dropdown ✗ marker (which
    # checks the same locked vendor) correctly flags the part as unavailable from
    # it. That mismatch showed as "Fully Compatible" under a ✗-marked selection.
    from .vendor_coverage import (
        check_build_vendor_consistency, is_build_component, VENDOR_CONFLICT_MESSAGE,
    )
    orig_check, orig_vendor = check_build_vendor_consistency(build)
    if orig_vendor and is_build_component(new_part):
        from app.models import VendorComponent
        vc = VendorComponent.query.filter_by(
            vendor_id=orig_vendor['id'], component_id=new_part.id,
        ).first()
        if vc and int(vc.quantity or 0) >= 1:
            vendor_check = {
                'rule': 'Vendor consistency', 'status': 'pass',
                'detail': f"All parts available from {orig_vendor['shop_name']}.",
                'conflicting_slots': [],
            }
        else:
            vendor_check = {
                'rule': 'Vendor consistency', 'status': 'fail',
                'detail': VENDOR_CONFLICT_MESSAGE,
                'conflicting_slots': [slot],
            }
    else:
        vendor_check, _vendor = check_build_vendor_consistency(modified)
    result['checks'].append(vendor_check)
    if vendor_check['status'] == 'fail':
        vendor_failure = {'rule': vendor_check['rule'], 'detail': vendor_check['detail'],
                           'suggestions': []}
        result['failures'].append(vendor_failure)
        hard = hard + [vendor_failure]

    changes = []
    relevance = {'suitable': True, 'note': '', 'suggested': None}

    if hard:
        level = 'incompatible'
    elif adjustable:
        changes, resolved = _resolve_adjustments(modified, adjustable, purpose, cand_for)
        level = 'needs_adjustments' if resolved else 'incompatible'
        if not resolved:
            # Couldn't fix with supporting swaps → treat remaining as hard for messaging.
            hard = adjustable
    else:
        relevance = _assess_relevance(slot, old_part, new_part, purpose)
        level = 'fully_compatible' if relevance['suitable'] else 'unnecessary'

    perf = _assess_performance(slot, old_part, new_part, level)
    adj_delta = sum(c['price_delta'] for c in changes)
    new_total = new_total_base + adj_delta
    budget_delta = int(new_total - old_total)
    within_budget = (budget_num is None) or (new_total <= budget_num)

    explanation = _explain(level, slot, new_part, relevance, perf, budget_delta,
                           changes, hard if level == 'incompatible' else result['failures'])

    return {
        'level': level,
        'status_label': _LEVEL_LABEL[level],
        'slot': slot,
        'from': _name(old_part) if old_part else None,
        'to': _name(new_part),
        'compatible': level != 'incompatible',
        'requirement_suitable': relevance['suitable'],
        'relevance_note': relevance['note'],
        'performance_impact': perf['impact'],
        'performance_detail': perf['detail'],
        'dependent_changes': changes,
        'budget': {
            'old_total': int(old_total), 'new_total': int(new_total),
            'delta': budget_delta, 'within_budget': within_budget,
        },
        'technical': result,
        'explanation': explanation['advanced'] if mode == 'advanced' else explanation['beginner'],
        'explanations': explanation,
    }
