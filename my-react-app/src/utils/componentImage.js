/**
 * Resolve component image_url from admin DB for display (handles absolute URLs and Flask paths).
 */
export function resolveComponentImageUrl(imageUrl, apiBase) {
  const raw = imageUrl != null ? String(imageUrl).trim() : '';
  if (!raw) return null;
  if (/^https?:\/\//i.test(raw) || raw.startsWith('//')) return raw;
  if (raw.startsWith('/') && apiBase) {
    return `${String(apiBase).replace(/\/$/, '')}${raw}`;
  }
  return raw;
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
  const fromCat = kindFromCategoryLabel(category);
  if (fromCat) return fromCat;

  const s = `${category || ''} ${name || ''}`.toLowerCase();
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
  return `/component-images/${k}.svg`;
}

/** Thematic stock photos (Unsplash) per kind — used when DB has no image_url or it fails. */
const UNSPLASH_STOCK_QUERY = 'auto=format&fit=crop&w=800&q=80';

const STOCK_PHOTO_BY_KIND = {
  cpu: 'photo-1686195165991-74af7c2918d5',
  gpu: 'photo-1591488320449-011701bb6704',
  ram: 'photo-1541029071515-84cc54f84dc5',
  storage: 'photo-1760623227551-2eae8f9cb675',
  motherboard: 'photo-1650526573230-8f8dfb89e509',
  psu: 'photo-1756576170672-1123237f1d77',
  case: 'photo-1573053986275-840ffc7cc685',
  cooling: 'photo-1754821130717-60c970da55dc',
  monitor: 'photo-1593640408182-31c70c8268f5',
  peripheral: 'photo-1632078056157-f7eb9c54e9cc',
  generic: 'photo-1518770660439-4636190af475',
};

export function getCategoryStockPhotoUrl(kind) {
  const k = kind && typeof kind === 'string' ? kind : 'generic';
  const id = STOCK_PHOTO_BY_KIND[k] ?? STOCK_PHOTO_BY_KIND.generic;
  return `https://images.unsplash.com/${id}?${UNSPLASH_STOCK_QUERY}`;
}
