/**
 * buildResolver.js — turn a static prebuilt (PREBUILT_SHOWCASE) into a
 * database-driven build using the Dashboard ERP catalog (source of truth).
 *
 * Why this exists:
 *   Prebuilt builds in src/data/prebuiltShowcase.js carry generic part *names*
 *   ("AMD Ryzen 7 9800X3D", "1TB NVMe SSD"). To run a real
 *   Configure → Cart → Vendor → Checkout flow we must resolve each name to an
 *   actual `components` row in the ERP (real id, price, stock, vendor availability).
 *
 * Backend (ERP, port 5000 dev / Railway prod — see flaskBase.js):
 *   GET  /api/components/search?q=&limit=&vendor_summary=1   (dashboardGet)
 *   POST /api/add-to-cart  (via CartContext.addToCart)
 *
 * Deliberately ERP-native: it does NOT call /components/resolve or
 * /cart/add-build-parts (those live only in the standalone app.py, port 5001,
 * and 404 through the Vite proxy). buildPartMatcher.js is the legacy path.
 */

import { dashboardGet } from '../api/dashboardApi';

/** Prebuilt part label ("CPU") → catalog slot key. */
const SLOT_FROM_LABEL = {
  CPU: 'cpu',
  GPU: 'gpu',
  'Graphics Card': 'gpu',
  Motherboard: 'motherboard',
  Mobo: 'motherboard',
  RAM: 'ram',
  Memory: 'ram',
  Storage: 'storage',
  SSD: 'storage',
  PSU: 'psu',
  'Power Supply': 'psu',
  Case: 'case',
  Chassis: 'case',
};

const SLOT_ORDER = ['cpu', 'gpu', 'motherboard', 'ram', 'storage', 'psu', 'case'];

/** Values that should never become a cart line (e.g. iGPU, placeholder). */
const SKIP_VALUE_RE = /^(integrated|onboard|igpu|none|n\/a|na|—|-+|tbd)$/i;

/** Leading vendor/brand words to strip when the full-name search misses. */
const BRAND_PREFIX_RE =
  /^(amd|intel|nvidia|asus|msi|gigabyte|asrock|corsair|kingston|crucial|gskill|g\.skill|samsung|western digital|wd|seagate|cooler master|coolermaster|nzxt|antec|thermaltake|deepcool|lian li|be quiet!?|evga|zotac|palit|gainward|sapphire|powercolor|xfx|montech)\s+/i;

const STOPWORDS = new Set(['gb', 'tb', 'mhz', 'the', 'for', 'with', 'and', 'mid', 'tower']);

/** Broad per-slot search terms — used only when name-based queries find nothing. */
const SLOT_FALLBACK_QUERIES = {
  cpu: ['ryzen', 'core', 'processor'],
  gpu: ['geforce', 'radeon', 'rtx'],
  motherboard: ['motherboard'],
  ram: ['ddr'],
  storage: ['ssd'],
  psu: ['power supply'],
  case: ['case', 'tower'],
};

const MAX_CANDIDATES = 12;
const MIN_MATCH_SCORE = 8;

function lower(value) {
  return String(value || '').trim().toLowerCase();
}

/** Map a prebuilt part {name,value} to its slot key. */
export function slotForPart(part) {
  const label = String(part?.name || '').trim();
  if (SLOT_FROM_LABEL[label]) return SLOT_FROM_LABEL[label];
  const key = lower(label);
  const direct = Object.entries(SLOT_FROM_LABEL).find(([k]) => k.toLowerCase() === key);
  return direct ? direct[1] : key;
}

export function partShouldSkip(part) {
  const value = lower(part?.value);
  return !value || SKIP_VALUE_RE.test(value);
}

function tokenize(name) {
  const out = [];
  for (const raw of lower(name).split(/[^a-z0-9]+/)) {
    if (raw.length >= 2 && !STOPWORDS.has(raw) && !out.includes(raw)) out.push(raw);
  }
  return out.slice(0, 6);
}

/** Heuristic: does this catalog name plausibly belong to the given slot? */
export function nameFitsSlot(name, slot) {
  const n = ` ${lower(name)} `;
  switch (slot) {
    case 'gpu':
      return /(geforce|\brtx\b|\bgtx\b|radeon|graphics|\barc\b|\brx\s?\d)/.test(n) && !n.includes('ssd');
    case 'storage':
      return /(ssd|nvme|hdd|storage|\bdrive\b|m\.2|sata)/.test(n);
    case 'psu':
      return /(psu|power supply|smps|bronze|gold|platinum|\d{3,4}\s?w\b|watt)/.test(n);
    case 'case':
      return /(case|tower|cabinet|chassis|mesh)/.test(n);
    case 'cpu':
      return (
        /(processor|core\s?i[3579]|ryzen|xeon|celeron|athlon|\bcpu\b)/.test(n) &&
        !n.includes('motherboard') &&
        !n.includes('ssd')
      );
    case 'motherboard':
      return /(motherboard|mainboard|mobo|\b[bxhza]\d{3}\b)/.test(n);
    case 'ram':
      return /(\bram\b|ddr4|ddr5|dimm|memory)/.test(n) && !n.includes('motherboard');
    default:
      return false;
  }
}

function scoreCandidate(requested, slot, row) {
  let score = 0;
  const rn = lower(row?.name);
  const sn = lower(requested);
  if (nameFitsSlot(rn, slot)) score += 12;
  if (sn && rn.includes(sn)) score += 24;
  if (sn && sn.includes(rn) && rn.length >= 4) score += 14;
  for (const token of tokenize(requested)) {
    if (rn.includes(token)) score += 4;
  }
  if (Number(row?.stock) > 0) score += 6;
  if (row?.has_vendor_stock) score += 4;
  return score;
}

/**
 * Progressive search terms: full value → brand stripped → strongest model token.
 * The ERP search is a single `%q%` ILIKE, so a shorter high-signal term is more
 * forgiving when DB naming differs slightly from the showcase label.
 */
function searchQueriesFor(value) {
  const full = String(value || '').trim();
  const queries = [];
  const push = (q) => {
    const t = (q || '').trim();
    if (t && t.length >= 2 && !queries.some((x) => x.toLowerCase() === t.toLowerCase())) {
      queries.push(t);
    }
  };
  push(full);
  push(full.replace(BRAND_PREFIX_RE, ''));
  const modelToken = tokenize(full).find((t) => /\d/.test(t) && t.length >= 3);
  push(modelToken);
  return queries;
}

async function searchCandidates(value, slot) {
  // Name-derived queries first; broad slot queries only as a last resort so a
  // vague showcase value ("Mid-tower airflow") still resolves to a real part.
  const queries = [...searchQueriesFor(value), ...(SLOT_FALLBACK_QUERIES[slot] || [])];
  for (const q of queries) {
    try {
      const res = await dashboardGet(
        `/components/search?q=${encodeURIComponent(q)}&limit=${MAX_CANDIDATES}&vendor_summary=1`
      );
      const rows = Array.isArray(res?.components) ? res.components : [];
      if (rows.length) return rows;
    } catch {
      // try next, narrower query
    }
  }
  return [];
}

/**
 * Resolve a single prebuilt part to a catalog component.
 * @param {{name:string,value:string}} part
 * @param {Set<number>} [usedIds] ids already claimed by another slot (avoid dupes)
 * @returns {Promise<{slot:string,label:string,requested:string,status:string,component:object|null}>}
 */
export async function resolvePart(part, usedIds = new Set()) {
  const slot = slotForPart(part);
  const label = String(part?.name || slot).trim();
  const requested = String(part?.value || '').trim();

  if (partShouldSkip(part)) {
    return { slot, label, requested, status: 'skipped', component: null };
  }

  const candidates = await searchCandidates(requested, slot);
  let best = null;
  let bestScore = -1;
  for (const row of candidates) {
    if (usedIds.has(row.id)) continue;
    const s = scoreCandidate(requested, slot, row);
    if (s > bestScore) {
      bestScore = s;
      best = row;
    }
  }

  if (!best || bestScore < MIN_MATCH_SCORE) {
    return { slot, label, requested, status: 'not_found', component: null };
  }

  usedIds.add(best.id);
  const component = {
    id: best.id,
    name: best.name,
    category: best.category,
    brand: best.brand,
    // Use the cheapest-vendor (effective) price so the estimate equals what the cart
    // actually charges — the backend assigns the lowest-priced in-stock vendor.
    price: Number(best.effective_price ?? best.price ?? 0),
    catalogPrice: Number(best.price || 0),
    stock: Number(best.stock || 0),
    image_url: best.image_url,
    has_vendor_stock: Boolean(best.has_vendor_stock),
    vendors_with_stock: Number(best.vendors_with_stock || 0),
  };
  const inStock = component.stock > 0 || component.has_vendor_stock;
  return {
    slot,
    label,
    requested,
    status: inStock ? 'resolved' : 'out_of_stock',
    component,
  };
}

/**
 * Resolve every part of a prebuilt build against the ERP catalog.
 * @param {Array<{name:string,value:string}>} parts
 * @returns {Promise<{slots:Array, summary:object}>}
 */
export async function resolveBuildParts(parts) {
  const list = Array.isArray(parts) ? parts : [];
  const usedIds = new Set();

  // Resolve sequentially so usedIds dedupe is deterministic across slots.
  const slots = [];
  for (const part of list) {
    slots.push(await resolvePart(part, usedIds));
  }

  slots.sort(
    (a, b) =>
      (SLOT_ORDER.indexOf(a.slot) + 1 || 99) - (SLOT_ORDER.indexOf(b.slot) + 1 || 99)
  );

  return { slots, summary: summarizeResolution(slots) };
}

/** Roll up resolution into totals + actionable gaps. */
export function summarizeResolution(slots) {
  const list = Array.isArray(slots) ? slots : [];
  const resolved = list.filter((s) => s.status === 'resolved');
  const outOfStock = list.filter((s) => s.status === 'out_of_stock');
  const missing = list.filter((s) => s.status === 'not_found');
  // Skipped slots are intentionally part-less (e.g. an iGPU build's GPU = "Integrated").
  // They need no catalog match, so they must NOT count against the in-stock tally.
  const skipped = list.filter((s) => s.status === 'skipped');
  const total = [...resolved, ...outOfStock].reduce(
    (sum, s) => sum + (s.component?.price || 0),
    0
  );
  // Only in-stock resolved parts are actually added to the cart (see
  // addResolvedBuildToCart), so this is the price the customer is really charged for
  // parts. `total` stays as the indicative all-parts figure used elsewhere (e.g. the
  // prebuilt "from" price).
  const addableTotal = resolved.reduce((sum, s) => sum + (s.component?.price || 0), 0);
  return {
    total,
    addableTotal,
    resolvedCount: resolved.length,
    addableCount: resolved.length,
    outOfStockCount: outOfStock.length,
    missingCount: missing.length,
    skippedCount: skipped.length,
    // Parts that actually need a catalog match (integrated/none slots excluded) —
    // the correct denominator for the "X/Y in stock" indicator.
    applicableCount: resolved.length + outOfStock.length + missing.length,
    missingLabels: missing.map((s) => s.label),
    outOfStockLabels: outOfStock.map((s) => s.label),
    fullyResolved: missing.length === 0 && outOfStock.length === 0 && resolved.length > 0,
  };
}

/**
 * Add all in-stock resolved components to the ERP cart.
 * @param {Array} slots resolution from resolveBuildParts().slots
 * @param {(product:object, qty?:number, opts?:object)=>Promise<boolean>} addToCart from useCart()
 * @param {{silent?:boolean}} [opts] forwarded to addToCart (e.g. silent for bulk adds)
 * @returns {Promise<{added:number, failed:Array<string>}>}
 */
export async function addResolvedBuildToCart(slots, addToCart, opts = {}) {
  if (typeof addToCart !== 'function') {
    throw new Error('addToCart from useCart() is required.');
  }
  const addable = (Array.isArray(slots) ? slots : []).filter(
    (s) => s.status === 'resolved' && s.component?.id
  );
  let added = 0;
  const failed = [];
  for (const s of addable) {
    const ok = await addToCart(
      { id: s.component.id, item_type: 'component', vendor_id: null },
      1,
      opts
    );
    if (ok) added += 1;
    else failed.push(s.label);
  }
  return { added, failed };
}

/** Convenience: resolve a prebuilt then add everything addable to the cart. */
export async function resolveAndAddBuild(parts, addToCart, opts = {}) {
  const { slots, summary } = await resolveBuildParts(parts);
  const { added, failed } = await addResolvedBuildToCart(slots, addToCart, opts);
  return { slots, summary, added, failed };
}
