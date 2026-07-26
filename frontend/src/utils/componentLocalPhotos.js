/**
 * Maps catalog component names → photos in /public/component-photos/
 * (copied from repo backend/assets/Components/).
 */

const PHOTO_BASE = '/component-photos';

/** All slugified filenames in public/component-photos */
const PHOTO_FILES = [
  'dell-22inch-monitor.png',
  'dell-24-inch-monitor.png',
  'dell-256gb-ssd.jpg',
  'dell-500w-power-supply.png',
  'dell-512gb-ssd.png',
  'dell-8gb-ddr4-ram.jpg',
  'dell-16-gb-ddr4-ram.avif',
  'dell-cpu-cooling-fan.png',
  'dell-desktop-case.png',
  'dell-multimedia-keyboard.jpg',
  'dell-optiplex-i5-processor.png',
  'dell-optiplex-i7-processor.jfif',
  'dell-optiplex-i7-processor.webp',
  'dell-optiplex-motherboard.jpg',
  'dell-usb-mouse.jpg',
  'hp-16gb-dd4-ram.jpg',
  'hp-22inch-monitor.png',
  'hp-24-inch-monitor.jfif',
  'hp-256gb-ssd.png',
  'hp-256gb-ssd-2-jo-sai-lage-laga-lo.webp',
  'hp-450w-power-supply.png',
  'hp-512gb-ssd.jpg',
  'hp-8gb-ddr4-ram.jpg',
  'hp-business-motherboard.png',
  'hp-cpu-cooling-fan.jpg',
  'hp-elitedesk-i5-processor.jfif',
  'hp-elitedesk-i7-processor.jfif',
  'hp-mid-tower-case.png',
  'hp-optical-mouse.jpg',
  'hp-usb-keyboard.jpg',
  'lenovo-16gb-ddr4-ram.jpg',
  'lenovo-22inch-monitor.png',
  'lenovo-24inch-monitor.jfif',
  'lenovo-256gn-ssd.jpg',
  'lenovo-500w-power-supply.png',
  'lenovo-512gb-ssd.webp',
  'lenovo-8gb-ddr4-ram.jpg',
  'lenovo-cpu-cooling-fan.jpg',
  'lenovo-optical-mouse.jpg',
  'lenovo-thinkcenter-i5-processor.png',
  'lenovo-thinkcenter-i7-processor.jfif',
  'lenovo-thinkcenter-motherboard.png',
  'lenovo-thinkcentre-i7-processor.png',
  'lenovo-wired-keyboard.jpg',
];

/** Exact catalog name → preferred file (wins over fuzzy match). */
const EXACT_NAME_TO_FILE = {
  'hp elitedesk i5 processor': 'hp-elitedesk-i5-processor.jfif',
  'hp elitedesk i7 processor': 'hp-elitedesk-i7-processor.jfif',
  'dell optiplex i5 processor': 'dell-optiplex-i5-processor.png',
  'dell optiplex i7 processor': 'dell-optiplex-i7-processor.jfif',
  'lenovo thinkcentre i5 processor': 'lenovo-thinkcenter-i5-processor.png',
  'lenovo thinkcentre i7 processor': 'lenovo-thinkcenter-i7-processor.jfif',
  'hp business motherboard': 'hp-business-motherboard.png',
  'dell optiplex motherboard': 'dell-optiplex-motherboard.jpg',
  'lenovo thinkcentre motherboard': 'lenovo-thinkcenter-motherboard.png',
  'hp 8gb ddr4 ram': 'hp-8gb-ddr4-ram.jpg',
  'hp 16gb ddr4 ram': 'hp-16gb-dd4-ram.jpg',
  'dell 8gb ddr4 ram': 'dell-8gb-ddr4-ram.jpg',
  'dell 16gb ddr4 ram': 'dell-16-gb-ddr4-ram.avif',
  'lenovo 8gb ddr4 ram': 'lenovo-8gb-ddr4-ram.jpg',
  'lenovo 16gb ddr4 ram': 'lenovo-16gb-ddr4-ram.jpg',
  'hp 256gb ssd': 'hp-256gb-ssd.png',
  'hp 512gb ssd': 'hp-512gb-ssd.jpg',
  'dell 256gb ssd': 'dell-256gb-ssd.jpg',
  'dell 512gb ssd': 'dell-512gb-ssd.png',
  'lenovo 256gb ssd': 'lenovo-256gn-ssd.jpg',
  'lenovo 512gb ssd': 'lenovo-512gb-ssd.webp',
  'hp 22 inch monitor': 'hp-22inch-monitor.png',
  'hp 24 inch monitor': 'hp-24-inch-monitor.jfif',
  'dell 22 inch monitor': 'dell-22inch-monitor.png',
  'dell 24 inch monitor': 'dell-24-inch-monitor.png',
  'lenovo 22 inch monitor': 'lenovo-22inch-monitor.png',
  'lenovo 24 inch monitor': 'lenovo-24inch-monitor.jfif',
  'hp usb keyboard': 'hp-usb-keyboard.jpg',
  'dell multimedia keyboard': 'dell-multimedia-keyboard.jpg',
  'lenovo wired keyboard': 'lenovo-wired-keyboard.jpg',
  'hp optical mouse': 'hp-optical-mouse.jpg',
  'dell usb mouse': 'dell-usb-mouse.jpg',
  'lenovo optical mouse': 'lenovo-optical-mouse.jpg',
  'hp 450w power supply': 'hp-450w-power-supply.png',
  'dell 500w power supply': 'dell-500w-power-supply.png',
  'lenovo 500w power supply': 'lenovo-500w-power-supply.png',
  'hp mid tower case': 'hp-mid-tower-case.png',
  'dell desktop case': 'dell-desktop-case.png',
  'hp cpu cooling fan': 'hp-cpu-cooling-fan.jpg',
  'dell cooling fan': 'dell-cpu-cooling-fan.png',
  'lenovo cpu cooling fan': 'lenovo-cpu-cooling-fan.jpg',
};

function normalizeNameKey(name, brand) {
  return `${brand || ''} ${name || ''}`
    .toLowerCase()
    .replace(/\bthinkcenter\b/g, 'thinkcentre')
    .replace(/\s+/g, ' ')
    .trim();
}

function compactAlphanumeric(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '');
}

function tokenSet(value) {
  return new Set(
    String(value || '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, ' ')
      .split(/\s+/)
      .filter((t) => t.length > 1),
  );
}

function scorePhotoMatch(nameKey, file) {
  const slug = file.replace(/\.[^.]+$/, '');
  const compactName = compactAlphanumeric(nameKey);
  const compactSlug = compactAlphanumeric(slug);

  if (compactName && compactName === compactSlug) return 1000;

  const nameTokens = tokenSet(nameKey);
  const slugTokens = tokenSet(slug.replace(/-/g, ' '));
  let overlap = 0;
  nameTokens.forEach((t) => {
    if (slugTokens.has(t)) overlap += 3;
    else if ([...slugTokens].some((s) => s.includes(t) || t.includes(s))) overlap += 1;
  });

  if (compactSlug.includes(compactName) || compactName.includes(compactSlug)) {
    overlap += 8;
  }

  return overlap;
}

/**
 * @returns {string|null} Public URL e.g. /component-photos/dell-22inch-monitor.png
 */
export function getLocalComponentPhotoUrl(component) {
  const name = component?.name || '';
  const brand = component?.brand || '';
  const key = normalizeNameKey(name, brand);

  if (!key) return null;

  const exactFile = EXACT_NAME_TO_FILE[key];
  if (exactFile && PHOTO_FILES.includes(exactFile)) {
    return `${PHOTO_BASE}/${exactFile}`;
  }

  let bestFile = null;
  let bestScore = 0;

  for (const file of PHOTO_FILES) {
    const score = scorePhotoMatch(key, file);
    if (score > bestScore) {
      bestScore = score;
      bestFile = file;
    }
  }

  if (bestScore >= 6 && bestFile) {
    return `${PHOTO_BASE}/${bestFile}`;
  }

  return null;
}

export function isLocalComponentPhotoUrl(url) {
  return typeof url === 'string' && url.startsWith(`${PHOTO_BASE}/`);
}

/** Hero strip — variety of real product shots */
export const COMPONENT_HERO_PHOTOS = [
  'dell-optiplex-i5-processor.png',
  'hp-8gb-ddr4-ram.jpg',
  'lenovo-512gb-ssd.webp',
  'hp-22inch-monitor.png',
  'dell-usb-mouse.jpg',
  'hp-450w-power-supply.png',
].map((f) => `${PHOTO_BASE}/${f}`);
