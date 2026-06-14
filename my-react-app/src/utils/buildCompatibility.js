/**
 * Rule-based build compatibility — mirrors the backend validator in
 * chat_intelligence.py (no network, no LLM). Given a parsed build's parts
 * ({ type, name, price }), it validates CPU-socket and RAM-generation coherence
 * against the motherboard and returns a per-component ✓/✗ status plus an overall
 * score so the Build preview panel can highlight conflicts.
 */

const CHIPSET_SOCKET = {
  a320: 'AM4', b350: 'AM4', b450: 'AM4', b550: 'AM4', x370: 'AM4', x470: 'AM4', x570: 'AM4', a520: 'AM4',
  a620: 'AM5', b650: 'AM5', x670: 'AM5', b840: 'AM5', b850: 'AM5', x870: 'AM5',
  h410: 'LGA1200', b460: 'LGA1200', h470: 'LGA1200', z490: 'LGA1200',
  h510: 'LGA1200', b560: 'LGA1200', h570: 'LGA1200', z590: 'LGA1200',
  h610: 'LGA1700', b660: 'LGA1700', h670: 'LGA1700', b760: 'LGA1700',
  h770: 'LGA1700', z690: 'LGA1700', z790: 'LGA1700',
};

// LGA1700 boards ship as DDR4 OR DDR5, so the board's own DDR mention wins for it.
const SOCKET_RAM_GEN = { AM4: 'DDR4', AM5: 'DDR5', LGA1200: 'DDR4', LGA1151: 'DDR4' };

const CHIPSET_RE = /\b(a320|b350|b450|b550|x370|x470|x570|a520|a620|b650|x670|b840|b850|x870|h410|b460|h470|z490|h510|b560|h570|z590|h610|b660|h670|b760|h770|z690|z790)\b/;
const SOCKET_RE = /\b(am4|am5|lga\s*1200|lga\s*1700|lga\s*1151)\b/;
const DDR_RE = /\bddr\s*([345])\b/;

function boardSocket(name) {
  const t = (name || '').toLowerCase();
  const chip = t.match(CHIPSET_RE);
  if (chip) return CHIPSET_SOCKET[chip[1]];
  const sock = t.match(SOCKET_RE);
  if (sock) return sock[1].toUpperCase().replace(/\s+/g, '');
  return null;
}

function cpuSocket(name) {
  const t = (name || '').toLowerCase();
  let m = t.match(/ryzen\s*[3579]?\s*(\d)\d{3}/);
  if (m) {
    const s = m[1];
    if ('12345'.includes(s)) return 'AM4';
    if ('789'.includes(s)) return 'AM5';
  }
  m = t.match(/(?:core\s*)?i[3579]\D*?(\d{4,5})\b/);
  if (m) {
    const model = m[1];
    const gen = model.length === 5 ? parseInt(model.slice(0, 2), 10) : parseInt(model[0], 10);
    if (gen === 8 || gen === 9) return 'LGA1151';
    if (gen === 10 || gen === 11) return 'LGA1200';
    if (gen >= 12 && gen <= 14) return 'LGA1700';
  }
  return null;
}

function ramGen(name) {
  const m = (name || '').toLowerCase().match(DDR_RE);
  return m ? `DDR${m[1]}` : null;
}

function findPart(parts, re) {
  return parts.find((p) => re.test(String(p.type || ''))) || null;
}

/**
 * @param {Array<{type:string,name:string,price?:string}>} parts
 * @returns {{score:number,total:number,okCount:number,issues:Array,statusByType:object,verdict:string,hasConflict:boolean}}
 */
export function checkBuildCompatibility(parts) {
  const list = Array.isArray(parts) ? parts : [];
  const cpu = findPart(list, /cpu|processor/i);
  const mobo = findPart(list, /mother|board|mobo/i);
  const ram = findPart(list, /\bram\b|memory/i);

  const bSock = mobo ? boardSocket(mobo.name) : null;
  const cSock = cpu ? cpuSocket(cpu.name) : null;
  // Board generation: its own DDR label first, else inferred from the socket.
  const bGen = (mobo && ramGen(mobo.name)) || (bSock ? SOCKET_RAM_GEN[bSock] : null) || null;
  const rGen = ram ? ramGen(ram.name) : null;

  // The motherboard is the fixed baseline; only the CPU / RAM can "conflict".
  const cpuConflict = Boolean(cSock && bSock && cSock !== bSock);
  const ramConflict = Boolean(rGen && bGen && rGen !== bGen);

  const statusByType = {};
  const issues = [];
  list.forEach((p) => {
    const type = String(p.type || '');
    let ok = true;
    let note = '';
    if (p === cpu && cpuConflict) {
      ok = false;
      note = `${cSock} CPU needs an ${cSock} board (you have ${bSock})`;
    } else if (p === ram && ramConflict) {
      ok = false;
      note = `${rGen} RAM won't fit a ${bGen} board`;
    }
    statusByType[type] = { ok, note };
    if (!ok) issues.push({ type, note });
  });

  const total = list.length || 0;
  const okCount = total - issues.length;
  const score = total ? Math.round((okCount / total) * 100) : 100;

  let verdict;
  if (issues.length === 0) verdict = 'Excellent — fully compatible';
  else if (issues.length === 1) verdict = 'Build needs attention — 1 issue';
  else verdict = `Build needs attention — ${issues.length} issues`;

  return { score, total, okCount, issues, statusByType, verdict, hasConflict: issues.length > 0 };
}
