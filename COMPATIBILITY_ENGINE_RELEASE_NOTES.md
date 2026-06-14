# GenSpark — Rule-Based Compatibility & Customization Engine

**Release notes (FYP submission)** · branch `feat/genspark-build-flow`

A deterministic, **rule-based** (no-LLM) compatibility and decision-support engine for the
GenSpark PC builder. The system guarantees hardware compatibility by rule and evaluates
whether each customization is *worthwhile* for the user's workload — not just whether it
*fits*.

> Academic framing: the system guarantees **rule-based hardware compatibility**, while
> recommendation *relevance* is determined from user requirements and predefined decision
> rules. It does not claim 100% recommendation suitability — only 100% compatibility.

---

## Phase 0 — Budget-fill fix (recommender)
The recommender previously left builds well under the stated budget (e.g. an *Editing under
150K* build landed at PKR 97,500 on integrated graphics — 35% unspent).

- Added `_upgrade_to_budget()` in `Dashboard/app/api/ai_build_routes.py` — the inverse of
  the existing trim pass: it reinvests leftover budget into coherent, higher-tier parts up
  to sensible per-slot caps, and when no discrete GPU fits it redistributes the GPU's
  budget share across the remaining slots.
- Result: GPU-buildable budgets now use 88–100% of target; platform-limited iGPU builds use
  ~70% (the realistic ceiling for that catalog). "Balanced" fill — never pads a slot just to
  hit the number.

## Phase 1 — Data-driven compatibility core
The catalog stored parts as free-text names with an **empty** `specs` column; every
compatibility decision was name-regex guesswork. Phase 1 makes it deterministic.

- **`app/services/hardware_specs.py`** — `derive_specs(name)` parses a part name into
  structured specs (socket, chipset, DDR generation, TDP, iGPU, GPU length/TDP/min-PSU/
  connectors, PSU watts/rating, case clearance + form factor, cooler sockets/TDP, storage
  interface). Classifies by name, not the (corrupt) `category_id`.
- **`app/services/compatibility.py`** — `validate_build()` returns
  `{compatible, score, checks[], failures[], warnings[]}`. Rules: CPU↔motherboard socket +
  DDR generation, motherboard↔RAM generation + capacity, GPU↔PSU wattage (load + 20% margin
  **and** the GPU's vendor-stated minimum) + connectors, GPU↔case clearance, motherboard↔
  case form factor, CPU↔cooler socket + TDP, motherboard↔storage slots, PSU 80+ Bronze
  minimum, and iGPU-required-when-no-GPU. Unknown inputs are **skipped**, never silently
  passed.
- **`seed_component_specs.py`** — one-time seeder; populated `specs` for all 88 components
  (`--dry-run` / `--force` supported).
- Wired into `/api/recommend-build`: responses now carry `compatibility` +
  `compatibility_score`.

## Phase 2 — Customization decision-support
- **`app/services/customization.py`** — `evaluate_change(build, slot, new_part, purpose,
  budget)` runs a 4-level decision tree:
  - ✅ **Fully Compatible** — valid and worthwhile.
  - ⚠️ **Compatible but Unnecessary** — valid but overkill for the workload (minimal gain).
  - 🔄 **Compatible After Adjustments** — works, but supporting parts must change.
  - ❌ **Incompatible** — platform mismatch (socket / DDR / capacity); blocked, with
    concrete in-stock alternatives.
- Returns budget delta, performance impact, dependent changes, and **both** Beginner and
  Advanced explanations.
- Product rules: platform mismatches are ❌ (the board is never silently swapped); only the
  **PSU** is auto-applied for 🔄 — case/cooler upgrades are surfaced as recommendations.
- Endpoints: `POST /api/evaluate-customization`, `GET|POST /api/build-options` (slot
  candidates; POST with the current build hides hard-incompatible parts).

## Phase 3 — User interface
- **`BuildRecommendationCard.jsx`** now renders the backend's deterministic verdict (score,
  pass/fail/warn/skip checks, failure alternatives) instead of a client-side name heuristic.
- **`BuildCustomizer.jsx`** — per-slot dropdowns → live evaluation → colored 4-level verdict
  panel with a Beginner/Advanced toggle, budget old→new, dependent-change list, and Apply.
  Apply swaps the slot + dependent changes (PSU auto) into the live build, which flows to
  the cart. Dropdowns are filtered so an incompatible part is never offered.
- `builderApi.js` — `getBuildOptions()` and `postEvaluateCustomization()` helpers.

---

## QA summary
Verified via backend rule-engine tests (live MySQL `genspark_erp`), HTTP endpoint tests,
frontend code review, `npm run build`, and ESLint.

- **Passed:** all 4 verdict levels apply/block correctly; cart dedupes by id and matches the
  modified build; budget math exact incl. negative deltas; alternatives are real and
  compatible; dropdowns exclude hard-incompatible parts; defensive handling for missing IDs
  (400), bad slot (400), nonexistent component (404), empty build (200), deleted records
  (graceful), and API/network errors.
- **Fixed during QA:** stale build state leaked across chat sessions (`handleNewChat` now
  resets it); dropdowns no longer list hard-incompatible parts.

## Known limitations (non-critical)
1. After an edit, the recommendation *table* still shows original parts (renders from static
   markdown); the customizer + cart reflect the change correctly.
2. Cross-platform CPU/RAM swaps aren't offered in dropdowns (by design); start a new
   recommendation to change platform.
3. Edited builds are client-state only — they reach the cart but aren't persisted as a saved
   build across reloads.
4. No CPU Cooler slot in the recommender yet; brand/performance-level/resolution inputs not
   yet collected.

## Architecture note
The catalog's `category_id` data is unreliable (duplicate category rows; SSDs filed under
*Motherboard*, a PSU under *Processor*). All classification and validation therefore work
from the component **name**, never `category_id`.
