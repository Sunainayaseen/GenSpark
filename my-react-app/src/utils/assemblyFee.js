// Assembly service fee — mirrors the backend rule in Dashboard/app/services/fees.py.
// Charged only when a build/cart is an assemble-able PC (a CPU + a motherboard
// present), never for lone accessories. Keep these regexes in sync with fees.py.
export const ASSEMBLY_FEE = 5000;

const CPU_PATTERN = /(processor|ryzen|core\s?i\d|\bcpu\b|athlon|xeon|core\s*ultra)/;
const MOBO_WORD_PATTERN = /(motherboard|mainboard)/;
// A bare "[B/X/H/Z/A]+3digits" token (e.g. B650, H510) is a real chipset name, but it
// is ALSO a real case-model pattern (e.g. NZXT H510, Cooler Master H500) — so on its
// own it is not reliable proof of a motherboard. Only trust it next to a brand that
// actually makes motherboards, never on the bare token alone.
// Optional trailing form-factor/tier letter (B660M, B650E, X670E, Z790I, …) — the
// far more common retail naming than the bare chipset code alone.
const MOBO_CHIPSET_PATTERN = /\b[bxhza]\d{3}[a-z]?\b/;
const MOBO_BRAND_PATTERN = /\b(asus|msi|gigabyte|aorus|asrock|biostar|evga|colorful)\b/;

function isMotherboardName(name) {
  const n = name || '';
  if (MOBO_WORD_PATTERN.test(n)) return true;
  return MOBO_BRAND_PATTERN.test(n) && MOBO_CHIPSET_PATTERN.test(n);
}

/** Whether a lowercase, pipe-joined blob of component names implies an assemble-able PC. */
export function textNeedsAssembly(blob) {
  const names = String(blob || '').split('|').map((s) => s.trim());
  return CPU_PATTERN.test(blob) && names.some(isMotherboardName);
}

/** Whether a list of cart/order items (each with component_name/title/name) needs assembly. */
export function cartNeedsAssembly(items) {
  const names = (items || []).map((i) => (i.component_name || i.title || i.name || '').toLowerCase());
  return CPU_PATTERN.test(names.join(' | ')) && names.some(isMotherboardName);
}
