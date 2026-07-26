/**
 * Parse rules-engine / AI build markdown into structured UI data.
 */

function stripMd(text) {
  return String(text || '')
    .replace(/\*\*/g, '')
    .replace(/__/g, '')
    .trim();
}

function countStars(text) {
  const filled = (text.match(/⭐/g) || []).length;
  if (filled > 0) return filled;
  const m = text.match(/(\d)\s*\/\s*5/);
  return m ? Number(m[1]) : 0;
}

function parseStatsBlock(block) {
  const text = stripMd(block.replace(/\n/g, ' '));
  const raw = block;

  const compatLine =
    raw.match(/Compatibility Status:\*\*([^⚡🏆💰📊\n]+)/iu)?.[1] ||
    raw.match(/Compatibility Status:([^\n]+)/i)?.[1] ||
    '';
  let compatibility = stripMd(compatLine);
  let bottleneck = null;
  if (compatibility.includes('—')) {
    const [a, b] = compatibility.split('—').map((s) => s.trim());
    compatibility = a;
    bottleneck = b || null;
  } else if (compatibility.includes(' - ')) {
    const [a, b] = compatibility.split(' - ').map((s) => s.trim());
    compatibility = a;
    bottleneck = b || null;
  }

  const psuMatch = text.match(/PSU Wattage Buffer:\s*(\d+)\s*W/i);
  const vrmMatch = text.match(/VRM thermal index\s*(\d+)\s*\/\s*100/i);
  const perfMatch = text.match(/Performance Score:\s*(\d+)\s*\/\s*100/i);
  const telemetryMatch = text.match(/telemetry\s*([\d.]+)/i);
  const totalMatch = text.match(/Estimated parts total:\s*([\d,]+)\s*PKR/i);
  const tierMatch = text.match(/Tier:\s*([A-Za-z0-9]+)/i);

  const valueLine = raw.match(/Value For Money Rating:[^\n]*/i)?.[0] || '';

  return {
    compatibility: compatibility || 'Validated',
    bottleneck,
    psuWatts: psuMatch ? Number(psuMatch[1]) : null,
    vrmIndex: vrmMatch ? Number(vrmMatch[1]) : null,
    performanceScore: perfMatch ? Number(perfMatch[1]) : null,
    telemetry: telemetryMatch ? Number(telemetryMatch[1]) : null,
    valueStars: countStars(valueLine),
    totalPkr: totalMatch ? totalMatch[1].replace(/,/g, '') : null,
    tier: tierMatch ? tierMatch[1].toUpperCase() : null,
  };
}

function parseMarkdownTable(sectionText) {
  const lines = sectionText.split('\n').filter((l) => l.trim().startsWith('|'));
  if (lines.length < 2) return [];

  const rows = [];
  for (let i = 2; i < lines.length; i += 1) {
    const cells = lines[i]
      .split('|')
      .map((c) => c.trim())
      .filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
    if (cells.length >= 3 && !cells[0].match(/^[-:]+$/)) {
      rows.push({
        type: cells[0],
        name: cells[1],
        price: cells[2],
      });
    }
  }
  return rows;
}

function parseBulletList(text) {
  return text
    .split('\n')
    .map((l) => l.replace(/^[\s-*•]+/, '').trim())
    .filter((l) => l.length > 0 && !l.startsWith('|'));
}

/**
 * @returns {{ isBuildRecommendation: boolean, stats?: object, summary?: string, parts?: array, reasoning?: string[], remainderMarkdown?: string }}
 */
export function parseBuildRecommendationMarkdown(markdown) {
  const md = String(markdown || '').trim();
  if (!md) return { isBuildRecommendation: false, remainderMarkdown: '' };

  const hasPartsTable = /##\s*Recommended Components/i.test(md);
  const hasCompat = /Compatibility Status/i.test(md);
  if (!hasPartsTable && !hasCompat) {
    return { isBuildRecommendation: false, remainderMarkdown: md };
  }

  const sections = [];
  const headingRe = /^##\s+(.+)$/gm;
  let match;
  let lastIndex = 0;
  let lastTitle = null;

  const preamble = md.match(/^[\s\S]*?(?=^##\s+)/m)?.[0]?.trim() || '';

  while ((match = headingRe.exec(md)) !== null) {
    if (lastTitle !== null) {
      sections.push({
        title: lastTitle,
        body: md.slice(lastIndex, match.index).trim(),
      });
    }
    lastTitle = match[1].trim();
    lastIndex = match.index + match[0].length;
  }
  if (lastTitle !== null) {
    sections.push({ title: lastTitle, body: md.slice(lastIndex).trim() });
  }

  const stats = hasCompat ? parseStatsBlock(preamble || md.split(/^##\s+/m)[0]) : null;

  let summary = '';
  let parts = [];
  let reasoning = [];

  for (const sec of sections) {
    const t = sec.title.toLowerCase();
    if (t === 'summary') {
      summary = sec.body.replace(/\*\*/g, '').replace(/\s+/g, ' ').trim();
    } else if (t.includes('recommended components')) {
      parts = parseMarkdownTable(sec.body);
    } else if (t.includes('reasoning') || t.includes('scoring engine')) {
      const sub = sec.body.split(/^###\s+/m);
      reasoning = parseBulletList(sub.length > 1 ? sub.slice(1).join('\n') : sec.body);
    }
  }

  const h3Reasoning = md.match(/###\s*🧠[^\n]*\n([\s\S]*?)(?=^##\s|$)/m);
  if (h3Reasoning && reasoning.length === 0) {
    reasoning = parseBulletList(h3Reasoning[1]);
  }

  if (!summary && sections.length === 0 && preamble) {
    const lines = preamble.split('\n').filter(Boolean);
    if (lines.length > 3) {
      summary = '';
    }
  }

  return {
    isBuildRecommendation: Boolean(hasCompat && stats),
    stats,
    summary,
    parts,
    reasoning,
    remainderMarkdown: '',
  };
}

export function formatPkr(amount) {
  const n = Number(String(amount).replace(/,/g, ''));
  if (!Number.isFinite(n)) return String(amount);
  // International grouping (189,000) — not lakh (1,89,000). See utils/format.js.
  return n.toLocaleString('en-US');
}

const _ZERO_PRICE_RE = /^(0|0\.0+|—|-+)$/;
const _INTEGRATED_GPU_RE =
  /(integrated|onboard|i-?gpu|vega|uhd|iris|no\s+discrete|graphics\s*\(cpu\))/i;

/**
 * Make an integrated-GPU row read "Included" instead of a bare "0".
 * A 0 price on a GPU row means the CPU's built-in graphics are used (e.g. Ryzen
 * 5600G APU) — there is no separate card to buy. Showing "0" looks like a bug or
 * a missing/free product, so clarify it. Display-only: totals/cart are unchanged.
 */
export function clarifyIntegratedGraphicsMarkdown(markdown) {
  if (!markdown || typeof markdown !== 'string') return markdown;
  return markdown
    .split('\n')
    .map((line) => {
      const t = line.trim();
      if (!t.startsWith('|')) return line;
      const cells = t.split('|');
      if (cells.length < 5) return line; // need at least | type | name | price |
      const type = cells[1].trim();
      const name = cells[2].trim();
      const price = cells[cells.length - 2].trim();
      if (/^[-:]+$/.test(type)) return line; // separator row
      if (/component\s*type|^part$|^type$|^selection$/i.test(type)) return line; // header
      const isIntegratedRow = /gpu|graphics/i.test(type) || _INTEGRATED_GPU_RE.test(name);
      if (isIntegratedRow && _ZERO_PRICE_RE.test(price)) {
        cells[cells.length - 2] = ' Included ';
        if (!name || /^[-—]+$/.test(name)) cells[2] = ' Integrated graphics (CPU) ';
        return cells.join('|');
      }
      return line;
    })
    .join('\n');
}
