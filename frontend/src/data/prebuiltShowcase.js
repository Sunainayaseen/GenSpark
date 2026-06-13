/**
 * Featured predefined / prebuilt PCs (/builds catalog + detail pages).
 * heroImage: showcase hero (Unsplash, optimized width).
 */

const U = (photoId, w = 1600) =>
  `https://images.unsplash.com/${photoId}?auto=format&fit=crop&w=${w}&q=85`;

export const PREBUILT_SHOWCASE = [
  {
    id: 101,
    quickKey: 'gaming',
    cardClass: 'build-card-gaming',
    category: 'Gaming',
    title: 'Gaming Beast',
    desc: 'Dominate every game at ultra settings with ray tracing.',
    specs: 'RTX 5070 Ti • Ryzen 7 9800X3D • 32GB DDR5',
    price: 189000,
    performanceScore: 94,
    wattage: 750,
    vendorETA: '3–5 days',
    heroImage: U('photo-1591488320449-011701bb6704'),
    parts: [
      { name: 'CPU', value: 'AMD Ryzen 7 9800X3D' },
      { name: 'GPU', value: 'NVIDIA RTX 5070 Ti' },
      { name: 'Motherboard', value: 'X870 / B650 (ATX)' },
      { name: 'RAM', value: '32GB DDR5' },
      { name: 'Storage', value: '1TB NVMe SSD' },
      { name: 'PSU', value: '850W 80+ Gold' },
      { name: 'Case', value: 'Mid-tower airflow' },
    ],
  },
  {
    id: 102,
    quickKey: 'budget',
    cardClass: 'build-card-office',
    category: 'Office',
    title: 'Pro Workstation',
    desc: 'Reliable performance for work, browsing, and everyday tasks.',
    specs: 'Ryzen 5 5600G • 16GB DDR4 • 512GB SSD',
    price: 55000,
    performanceScore: 72,
    wattage: 400,
    vendorETA: '2–4 days',
    heroImage: U('photo-1496181131886-712bab890577'),
    parts: [
      { name: 'CPU', value: 'AMD Ryzen 5 5600G' },
      { name: 'GPU', value: 'Integrated' },
      { name: 'Motherboard', value: 'A520M / B550M' },
      { name: 'RAM', value: '16GB DDR4' },
      { name: 'Storage', value: '512GB NVMe SSD' },
      { name: 'PSU', value: '450W 80+ Bronze' },
      { name: 'Case', value: 'Compact mATX' },
    ],
  },
  {
    id: 103,
    quickKey: 'content',
    cardClass: 'build-card-editing',
    category: 'Editing',
    title: 'Creator Studio',
    desc: '4K editing, 3D rendering, and heavy multitasking.',
    specs: 'RTX 4070 • Ryzen 7 7700X • 32GB DDR5',
    price: 145000,
    performanceScore: 88,
    wattage: 650,
    vendorETA: '3–5 days',
    heroImage: U('photo-1529333161038-ca7003c6b16e'),
    parts: [
      { name: 'CPU', value: 'AMD Ryzen 7 7700X' },
      { name: 'GPU', value: 'NVIDIA RTX 4070' },
      { name: 'Motherboard', value: 'B650 (ATX)' },
      { name: 'RAM', value: '32GB DDR5' },
      { name: 'Storage', value: '1TB NVMe SSD' },
      { name: 'PSU', value: '750W 80+ Gold' },
      { name: 'Case', value: 'Mid-tower' },
    ],
  },
  {
    id: 104,
    quickKey: 'ai',
    cardClass: 'build-card-ai',
    category: 'AI Workstation',
    title: 'AI Powerhouse',
    desc: 'Run AI models, ML workloads, and intensive compute.',
    specs: 'RTX 4090 • Ryzen 9 7950X3D • 64GB DDR5',
    price: 420000,
    performanceScore: 98,
    wattage: 850,
    vendorETA: '4–7 days',
    heroImage: U('photo-1620712943544-bce3048c6287'),
    parts: [
      { name: 'CPU', value: 'AMD Ryzen 9 7950X3D' },
      { name: 'GPU', value: 'NVIDIA RTX 4090' },
      { name: 'Motherboard', value: 'X670E (ATX)' },
      { name: 'RAM', value: '64GB DDR5' },
      { name: 'Storage', value: '2TB NVMe SSD' },
      { name: 'PSU', value: '1000W 80+ Gold' },
      { name: 'Case', value: 'Full tower' },
    ],
  },
  {
    id: 105,
    quickKey: 'streaming',
    cardClass: 'build-card-streaming',
    category: 'Streaming',
    title: 'Stream Studio',
    desc: 'NVENC encoding, dual-monitor ready, smooth 1080p/1440p capture.',
    specs: 'RTX 4060 Ti 16GB • Ryzen 7 7700 • 32GB DDR5',
    price: 138000,
    performanceScore: 86,
    wattage: 620,
    vendorETA: '3–5 days',
    heroImage: U('photo-1573164713714-d95e436ab8d6'),
    parts: [
      { name: 'CPU', value: 'AMD Ryzen 7 7700' },
      { name: 'GPU', value: 'NVIDIA RTX 4060 Ti 16GB' },
      { name: 'Motherboard', value: 'B650 (mATX)' },
      { name: 'RAM', value: '32GB DDR5' },
      { name: 'Storage', value: '1TB NVMe SSD' },
      { name: 'PSU', value: '650W 80+ Gold' },
      { name: 'Case', value: 'Mid-tower (good airflow)' },
    ],
  },
  {
    id: 106,
    quickKey: 'entry',
    cardClass: 'build-card-entry',
    category: 'Esports',
    title: '1080p Elite',
    desc: 'High frame rates for competitive titles without breaking the bank.',
    specs: 'RTX 4060 • Ryzen 5 7500F • 16GB DDR5',
    price: 92000,
    performanceScore: 76,
    wattage: 500,
    vendorETA: '2–4 days',
    heroImage: U('photo-1542751371-adc38448a05e'),
    parts: [
      { name: 'CPU', value: 'AMD Ryzen 5 7500F' },
      { name: 'GPU', value: 'NVIDIA RTX 4060' },
      { name: 'Motherboard', value: 'B650 (mATX)' },
      { name: 'RAM', value: '16GB DDR5' },
      { name: 'Storage', value: '1TB NVMe SSD' },
      { name: 'PSU', value: '550W 80+ Bronze' },
      { name: 'Case', value: 'Mid-tower mesh' },
    ],
  },
  {
    id: 107,
    quickKey: 'compact',
    cardClass: 'build-card-sff',
    category: 'Compact',
    title: 'Desk Mini Pro',
    desc: 'Small-footprint SFF—ideal for tight desks and clean setups.',
    specs: 'RTX 4060 • Ryzen 5 7600 • 16GB DDR5 • ITX',
    price: 79500,
    performanceScore: 74,
    wattage: 480,
    vendorETA: '3–6 days',
    heroImage: U('photo-1597872200969-2b65d56bd16b'),
    parts: [
      { name: 'CPU', value: 'AMD Ryzen 5 7600' },
      { name: 'GPU', value: 'NVIDIA RTX 4060' },
      { name: 'Motherboard', value: 'B650 ITX' },
      { name: 'RAM', value: '16GB DDR5' },
      { name: 'Storage', value: '1TB NVMe SSD' },
      { name: 'PSU', value: 'SFX 650W 80+ Gold' },
      { name: 'Case', value: 'Mini-ITX tower' },
    ],
  },
  {
    id: 108,
    quickKey: 'developer',
    cardClass: 'build-card-dev',
    category: 'Developer',
    title: 'Code Forge',
    desc: 'Heavy IDEs, Docker, and compile workloads with room to grow.',
    specs: 'Ryzen 9 7900 • RTX 4060 • 32GB DDR5 • 2TB SSD',
    price: 168000,
    performanceScore: 90,
    wattage: 580,
    vendorETA: '3–5 days',
    heroImage: U('photo-1461749280684-dccba630e2f6'),
    parts: [
      { name: 'CPU', value: 'AMD Ryzen 9 7900' },
      { name: 'GPU', value: 'NVIDIA RTX 4060' },
      { name: 'Motherboard', value: 'B650 (ATX)' },
      { name: 'RAM', value: '32GB DDR5' },
      { name: 'Storage', value: '2TB NVMe SSD' },
      { name: 'PSU', value: '750W 80+ Gold' },
      { name: 'Case', value: 'Mid-tower silent' },
    ],
  },
];

export const QUICK_REQUIREMENTS = {
  budget: { purpose: 'Office', budget: '50000', preferences: 'Budget-focused' },
  gaming: { purpose: 'Gaming', budget: '100000', preferences: 'Performance-focused' },
  content: { purpose: 'Content Creation', budget: '150000', preferences: 'Professional-grade' },
  ai: { purpose: 'Content Creation', budget: '200000', preferences: 'AI Workstation' },
  streaming: { purpose: 'Gaming', budget: '140000', preferences: 'Streaming and recording' },
  entry: { purpose: 'Gaming', budget: '90000', preferences: '1080p competitive gaming' },
  compact: { purpose: 'Office', budget: '80000', preferences: 'Compact SFF small footprint' },
  developer: { purpose: 'Office', budget: '170000', preferences: 'Software development and VMs' },
};

export function getPrebuiltById(rawId) {
  const id = Number(rawId);
  if (Number.isNaN(id)) return null;
  return PREBUILT_SHOWCASE.find((p) => p.id === id) ?? null;
}

/**
 * Fill missing line-item PKR from package total (catalog prebuilts often omit per-part price).
 * Distributes remaining budget across parts that have no valid price; leaves priced lines unchanged.
 */
export function allocateMissingLinePricesFromPackage(parts, packageTotal) {
  const pkg = Math.round(Number(packageTotal) || 0);
  const list = (Array.isArray(parts) ? parts : []).map((p) => ({ ...p }));
  if (!list.length || pkg <= 0) return list;

  const pricedSum = list.reduce((s, p) => {
    const n = Number(p.price);
    return s + (Number.isFinite(n) && n > 0 ? n : 0);
  }, 0);

  const indicesNeeding = list
    .map((p, i) => {
      const n = Number(p.price);
      return !Number.isFinite(n) || n <= 0 ? i : -1;
    })
    .filter((i) => i >= 0);

  if (indicesNeeding.length === 0) return list;

  const remaining = pkg - pricedSum;
  if (remaining < 0) return list;

  const k = indicesNeeding.length;
  const base = Math.floor(remaining / k);
  const rem = remaining - base * k;
  indicesNeeding.forEach((idx, j) => {
    list[idx] = { ...list[idx], price: base + (j < rem ? 1 : 0) };
  });
  return list;
}

/** Shape used by configurator / AppContext.selectedBuild */
export function prebuiltToConfiguratorBuild(item) {
  return {
    id: item.id,
    title: `${item.category} — ${item.title}`,
    type: item.category,
    price: item.price,
    stock: 25,
    image_url: item.heroImage || '/hero-build-visual.png',
    performanceScore: item.performanceScore,
    wattage: item.wattage,
    vendorETA: item.vendorETA,
    parts: allocateMissingLinePricesFromPackage(item.parts, item.price),
  };
}
