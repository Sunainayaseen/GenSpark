import { getLocalComponentPhotoUrl } from './componentLocalPhotos';

/**
 * Resolve component image_url from admin DB for display (handles absolute URLs and Flask paths).
 */
function catalogAssetOrigin(apiBase) {
  if (import.meta.env.DEV) {
    return 'http://127.0.0.1:5000';
  }
  const base = (apiBase || '').replace(/\/$/, '');
  if (base) return base;
  if (typeof window !== 'undefined') return window.location.origin.replace(/\/$/, '');
  return '';
}

/** True when DB category/URL clearly does not match product name (e.g. mouse listed as Cabinet). */
export function isMismatchedCatalogImage(component, dbUrl) {
  const name = (component?.name || '').toLowerCase();
  const category = (component?.category || '').toLowerCase();
  const url = (dbUrl || '').toLowerCase();
  if (!name) return false;

  const isMouse = /\bmouse\b|mice\b|optical mouse/.test(name);
  const isKeyboard = /keyboard|keypad/.test(name);
  const isMonitor = /\bmonitor\b/.test(name);
  const isRam = /\bram\b|memory|ddr/.test(name);

  if (!(isMouse || isKeyboard || isMonitor || isRam)) return false;

  const catWrong =
    (isMouse && /cabinet|case|chassis|psu|processor|cpu|gpu|motherboard/.test(category)) ||
    (isKeyboard && /cabinet|case|chassis|psu|mouse|processor|cpu|gpu/.test(category)) ||
    (isMonitor && /cabinet|case|psu|mouse|keyboard/.test(category));

  const urlWrong = /cabinet|chassis|pc-case|hero-build|gs-logo|\/case\//.test(url);

  return catWrong || urlWrong;
}

export function resolveComponentImageUrl(imageUrl, apiBase) {
  const raw = imageUrl != null ? String(imageUrl).trim() : '';
  if (!raw) return null;
  if (/^https?:\/\//i.test(raw) || raw.startsWith('//')) return raw;
  if (raw.startsWith('/uploads') || raw.startsWith('/static/uploads')) {
    const origin = catalogAssetOrigin(apiBase);
    return origin ? `${origin}${raw}` : raw;
  }
  if (raw.startsWith('/') && apiBase) {
    return `${String(apiBase).replace(/\/$/, '')}${raw}`;
  }
  return raw;
}

const DISPLAY_CATEGORY = {
  mouse: 'Mouse',
  keyboard: 'Keyboard',
  monitor: 'Monitor',
  ram: 'RAM',
  cpu: 'Processor',
  gpu: 'Graphics card',
  storage: 'Storage',
  motherboard: 'Motherboard',
  psu: 'Power supply',
  case: 'PC case',
  cooling: 'Cooling',
  peripheral: 'Peripheral',
  generic: 'Component',
};

/** Badge label: product name wins over wrong DB category (e.g. Mouse not Cabinet). */
export function getDisplayCategory(category, name) {
  const kind = getComponentPlaceholderKind(category, name);
  return DISPLAY_CATEGORY[kind] || category || 'Part';
}

/**
 * Map admin category labels (DB component_categories.name) → visual kind.
 */
function kindFromCategoryLabel(category) {
  const c = (category || '').trim().toLowerCase();
  if (!c) return null;
  if (/(^|[^a-z])(processor|cpu)([^a-z]|$)/.test(c) || c === 'cpu') return 'cpu';
  if (/graphics|gpu|video card|vga/.test(c)) return 'gpu';
  if (/memory|ram\b|ddr|dimm/.test(c)) return 'ram';
  if (/storage|ssd|hdd|nvme|drive|disk/.test(c)) return 'storage';
  if (/motherboard|mainboard|mobo|board/.test(c)) return 'motherboard';
  if (/psu|power supply|power unit/.test(c)) return 'psu';
  if (/case|chassis|cabinet|tower/.test(c)) return 'case';
  if (/cooling|cooler|fan|aio|liquid/.test(c)) return 'cooling';
  if (/monitor|display|screen/.test(c)) return 'monitor';
  if (/keyboard|mouse|peripheral|headset|audio|speaker/.test(c)) return 'peripheral';
  return null;
}

/**
 * Pick a placeholder "kind" for stock SVG + inline art when no image exists or load fails.
 */
export function getComponentPlaceholderKind(category, name) {
  const s = `${category || ''} ${name || ''}`.toLowerCase();
  if (/\bmouse\b|mice\b|optical mouse|wireless mouse/.test(s)) return 'mouse';
  if (/keyboard|keypad|mechanical keyboard/.test(s)) return 'keyboard';

  const fromCat = kindFromCategoryLabel(category);
  if (fromCat) return fromCat;
  if (/gpu|graphics|video card|geforce|radeon|rtx|gtx|\brx\s*\d/.test(s)) {
    return 'gpu';
  }
  if (/cpu|processor|ryzen|threadripper|core\s*i\d|intel\s*\d|celeron|pentium|athlon/.test(s)) {
    return 'cpu';
  }
  if (/ram|memory|ddr|dimm|so-dimm/.test(s)) {
    return 'ram';
  }
  if (/ssd|hdd|storage|nvme|hard\s*drive|disk/.test(s)) {
    return 'storage';
  }
  if (/motherboard|mainboard|b\d{3,4}|chipset|socket/.test(s)) {
    return 'motherboard';
  }
  if (/psu|power\s*supply|watt|80\+/.test(s)) {
    return 'psu';
  }
  if (/case|chassis|tower|cabinet/.test(s)) {
    return 'case';
  }
  if (/cooler|fan|aio|liquid/.test(s)) {
    return 'cooling';
  }
  if (/monitor|display|\bscreen\b|144hz|ips|oled/.test(s)) {
    return 'monitor';
  }
  if (/keyboard|mouse|headset|webcam|speaker/.test(s)) {
    return 'peripheral';
  }
  return 'generic';
}

/** Static image under /public/component-images/{kind}.svg — last fallback when remote photos fail. */
export function getCategoryStockImagePath(kind) {
  const k = kind && typeof kind === 'string' ? kind : 'generic';
  const file = k === 'mouse' || k === 'keyboard' ? 'peripheral' : k;
  return `/component-images/${file}.svg`;
}

/** Square crop — fills catalog frames consistently. */
const UNSPLASH_STOCK_QUERY = 'auto=format&fit=crop&w=720&h=720&crop=center&q=85';

const STOCK_PHOTO_BY_KIND = {
  cpu: 'photo-1686195165991-74af7c2918d5',
  gpu: 'photo-1591488320449-011701bb6704',
  ram: 'photo-1541029071515-84cc54f84dc5',
  storage: 'photo-1760623227551-2eae8f9cb675',
  // Circuit-board / PCB closeup reads as a motherboard far better than the prior
  // cooler-on-board shot.
  motherboard: 'photo-1518770660439-4636190af475',
  psu: 'photo-1756576170672-1123237f1d77',
  case: 'photo-1573053986275-840ffc7cc685',
  cooling: 'photo-1754821130717-60c970da55dc',
  monitor: 'photo-1593640408182-31c70c8268f5',
  mouse: 'photo-1527864550417-7fd91fc51a46',
  keyboard: 'photo-1632078056157-f7eb9c54e9cc',
  peripheral: 'photo-1632078056157-f7eb9c54e9cc',
  generic: 'photo-1518770660439-4636190af475',
};

export function getCategoryStockPhotoUrl(kind) {
  const k = kind && typeof kind === 'string' ? kind : 'generic';
  const id = STOCK_PHOTO_BY_KIND[k] ?? STOCK_PHOTO_BY_KIND.generic;
  return `https://images.unsplash.com/${id}?${UNSPLASH_STOCK_QUERY}`;
}

/**
 * Uniform catalog look: lead with the per-category stock photo so every part in a
 * category shows the same clean image (no brand-to-brand visual jumble). Admin uploads,
 * local brand photos, and the category SVG stay as ordered fallbacks if the stock CDN
 * photo fails to load.
 */
export function getComponentImageCandidates(component, apiBase) {
  const kind = getComponentPlaceholderKind(component?.category, component?.name);
  const dbUrl = resolveComponentImageUrl(component?.image_url, apiBase);
  const localUrl = getLocalComponentPhotoUrl(component);
  const list = [];
  list.push(getCategoryStockPhotoUrl(kind));
  if (dbUrl && !isMismatchedCatalogImage(component, dbUrl)) {
    list.push(dbUrl);
  }
  if (localUrl) {
    list.push(localUrl);
  }
  list.push(getCategoryStockImagePath(kind));
  return [...new Set(list.filter(Boolean))];
}

export { getLocalComponentPhotoUrl, isLocalComponentPhotoUrl } from './componentLocalPhotos';
