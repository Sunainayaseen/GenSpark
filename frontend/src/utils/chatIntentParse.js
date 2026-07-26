/**
 * Client-side chat intent — mirrors backend/app.py before /api/recommend-build.
 * Sources: guide (greeting) | openai (live) | catalog (offline fallback).
 */

export const AI_SOURCE = {
  GUIDE: 'guide',
  EXPERT: 'expert',
  RULES: 'rules',
  OPENAI: 'openai',
  CATALOG: 'catalog',
};

const LEGACY_SOURCE_MAP = {
  local_guide: AI_SOURCE.GUIDE,
  catalog_fallback: AI_SOURCE.CATALOG,
  // DB-driven rule engine (backend ai_build_routes._recommend_from_catalog)
  'rules-db': AI_SOURCE.RULES,
  'rules-engine': AI_SOURCE.RULES,
  rules_db: AI_SOURCE.RULES,
};

const PURE_GREETING_PHRASES = [
  'kia hal ha',
  'kia hal hai',
  'kya hal hai',
  'kya hal ha',
  'kaise ho',
  'kaise hain',
  'how are you',
  'how r u',
  'salam alaikum',
  'assalam o alaikum',
  'assalam',
  'salam',
  'aoa',
  'hello',
  'hi',
  'hey',
  'yo',
  'sup',
  'help',
  'help me',
  'kia hal',
];

export function normalizeAiSource(source, { conversational = false, fallback = false } = {}) {
  if (source && LEGACY_SOURCE_MAP[source]) return LEGACY_SOURCE_MAP[source];
  if (
    source === AI_SOURCE.GUIDE ||
    source === AI_SOURCE.EXPERT ||
    source === AI_SOURCE.RULES ||
    source === AI_SOURCE.OPENAI ||
    source === AI_SOURCE.CATALOG
  ) {
    return source;
  }
  if (conversational) return AI_SOURCE.GUIDE;
  if (fallback) return AI_SOURCE.CATALOG;
  return AI_SOURCE.OPENAI;
}

/** Human-readable note when API fell back despite a configured key (e.g. quota 429). */
export function formatGeminiFallbackNotice(fallbackReason) {
  const raw = String(fallbackReason || '').trim();
  if (!raw) return null;
  const lower = raw.toLowerCase();
  if (lower.includes('insufficient_quota') || lower.includes('billing')) {
    return 'OpenAI key is set but billing/quota blocked the call. Add funds at https://platform.openai.com/settings/billing';
  }
  if (lower.includes('429') || lower.includes('quota') || lower.includes('rate limit')) {
    return 'AI quota/rate limit hit — catalog estimate shown. Check OpenAI billing at https://platform.openai.com/settings/billing';
  }
  if (lower.includes('openai') && lower.includes('not configured')) {
    return 'Set OPENAI_API_KEY in backend/.env (https://platform.openai.com/api-keys), then restart.';
  }
  if (lower.includes('not configured') || lower.includes('api key')) {
    return 'Set OPENAI_API_KEY in backend/.env, then restart the server.';
  }
  if (raw.length > 160) return `${raw.slice(0, 157)}…`;
  return raw;
}

export function getAiSourceBadge(sourceKey, options = {}) {
  const { openaiConfigured = false, intentBadge = '' } = options;

  if (intentBadge && String(intentBadge).trim()) {
    const key = normalizeAiSource(sourceKey, options);
    const icon =
      key === AI_SOURCE.EXPERT ? '🛠️' : key === AI_SOURCE.RULES ? '⚡' : '📋';
    return {
      source: key,
      label: String(intentBadge).trim(),
      geminiActive: false,
      icon,
    };
  }

  switch (normalizeAiSource(sourceKey, options)) {
    case AI_SOURCE.EXPERT:
      return {
        source: AI_SOURCE.EXPERT,
        label: 'Hardware expert guide',
        geminiActive: false,
        icon: '🛠️',
      };
    case AI_SOURCE.RULES:
      return {
        source: AI_SOURCE.RULES,
        label: 'GenSpark Rule Engine (Live)',
        geminiActive: false,
        icon: '⚡',
      };
    case AI_SOURCE.OPENAI:
      return {
        source: AI_SOURCE.OPENAI,
        label: 'OpenAI GPT (Live)',
        geminiActive: true,
        icon: '✨',
      };
    case AI_SOURCE.CATALOG:
      if (openaiConfigured) {
        return {
          source: AI_SOURCE.CATALOG,
          label: 'Catalog estimate (AI unavailable)',
          geminiActive: false,
          icon: '⚠️',
        };
      }
      return {
        source: AI_SOURCE.CATALOG,
        label: 'Catalog estimate (offline fallback)',
        geminiActive: false,
        icon: '📊',
      };
    default:
      return {
        source: AI_SOURCE.GUIDE,
        label: 'Build assistant guide',
        geminiActive: false,
        icon: '📋',
      };
  }
}

/** True for hi / salam / kia hal ha — must not trigger build table from left-panel state. */
export function isPureGreetingMessage(raw) {
  const msg = (raw || '').toLowerCase().trim().replace(/\s+/g, ' ');
  if (!msg) return true;
  if (/lakh|lac|\d\s*k\b|budget|build|setup|rig|\d{4,}/.test(msg)) return false;
  if (PURE_GREETING_PHRASES.some((p) => msg === p || msg.startsWith(`${p} `) || msg.endsWith(` ${p}`))) {
    return true;
  }
  const words = msg.replace(/[^\w\s]/g, '').split(/\s+/).filter(Boolean);
  if (words.length <= 4 && /^(hi|hey|hello|aoa|salam|help)$/i.test(words[0])) return true;
  return false;
}

export function parseBudgetFromChat(raw) {
  if (!raw?.trim()) return '';
  // Strip GPU/CPU model numbers first so they aren't mistaken for a budget,
  // e.g. "rtx 4070", "rx 6600 xt", "core i5-12400", "ryzen 5 5600".
  const lower = raw
    .toLowerCase()
    .replace(/,/g, '')
    .replace(/\b(?:rtx|gtx|rx|arc|gt)\s*\d{3,4}\s*(?:ti|super|xt|x)?\b/g, ' ')
    .replace(/\b(?:core\s*)?i[3579][\s-]*\d{3,5}\b/g, ' ')
    .replace(/\bryzen\s*[3579]?\s*\d{3,4}[a-z0-9]*\b/g, ' ');

  const lakh = lower.match(/(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|lacs)\b/);
  if (lakh) return String(Math.round(parseFloat(lakh[1]) * 100000));

  // Check 'k' before the bare-decimal lakh rule so "1.5k" -> 1500 (not 150000).
  const k = lower.match(/(\d+(?:\.\d+)?)\s*k\b/);
  if (k) return String(Math.round(parseFloat(k[1]) * 1000));

  const dotLakh = lower.match(/(\d+\.\d{1,2})(?:\s*(?:lakh|lac|budget|hai|me|main))?/);
  if (dotLakh) return String(Math.round(parseFloat(dotLakh[1]) * 100000));

  const five = lower.match(/\b(\d{5,7})\b/);
  if (five) return five[1];

  const four = lower.match(/\d{4,}/);
  if (four) return four[0];

  return '';
}

export function parsePurposeFromChat(raw) {
  const msg = (raw || '').toLowerCase().trim();
  if (!msg) return '';

  if (/office|study|excel|typing|productivity|school|documents|corporate/.test(msg)) {
    return 'Office';
  }
  if (/\boffice\s+work\b|\bwork\s+office\b/.test(msg)) return 'Office';
  if (/office/.test(msg) && /\bwork\b|kaam|k\s+liye|ke\s+liye/.test(msg)) return 'Office';

  if (/edit|editing|video|render|blender|photoshop|premiere|davinci|creator/.test(msg)) {
    return 'Editing';
  }

  if (/gaming|game|play|pubg|gta|streaming|valorant|fortnite|esports/.test(msg)) {
    return 'Gaming';
  }
  if (/\brigid\s+(?:build|setup|pc|rig)\b/.test(msg) || /rigid\s+build/.test(msg)) {
    return 'Gaming';
  }
  if (/gaming pc|gaming setup/.test(msg)) return 'Gaming';

  if (/cod|programming|coding/.test(msg)) return 'Coding';
  if (/content creation/.test(msg)) return 'Content Creation';

  return '';
}

export function parseChatIntent(message) {
  const raw = (message || '').trim();
  const budgetStr = parseBudgetFromChat(raw);
  const purpose = parsePurposeFromChat(raw);
  return {
    budget: budgetStr ? Number(budgetStr) : null,
    purpose: purpose || null,
  };
}

/**
 * Multi-turn refinement: a follow-up like "make it cheaper" / "sasta karo" /
 * "stronger" / "behtar" that tweaks the PREVIOUS build's budget instead of starting
 * over. Returns {kind, factor} or null. (Explicit new numbers are handled normally.)
 */
export function parseRefinement(raw) {
  const t = (raw || '').toLowerCase().trim();
  if (!t) return null;
  if (/\b(cheaper|cheapest|sasta|sasti|kam\s*kar|kam\s*kr|lower|reduce|budget\s*kam|thora?\s*kam|less)\b/.test(t)) {
    return { kind: 'cheaper', factor: 0.8 };
  }
  if (/\b(stronger|powerful|better|behtar|behtreen|mehng|zyada\s*(powerful|fast|strong)|upgrade|high[\s-]?end|beef|tez|fast)\b/.test(t)) {
    return { kind: 'stronger', factor: 1.25 };
  }
  return null;
}

/** Build intent from message text only — not from stale Criteria panel values. */
export function hasBuildIntentFromChat(raw) {
  const text = (raw || '').trim();
  if (!text || isPureGreetingMessage(text)) return false;

  const { budget, purpose } = parseChatIntent(text);
  if (budget != null || purpose) return true;
  if (/\b(build|rig|setup|recommend|spec|pc|chahye|chahie|chaiye)\b/i.test(text)) return true;
  return false;
}

export function formatBudgetPkr(amount) {
  const n = Number(String(amount).replace(/\D/g, ''));
  if (!n || Number.isNaN(n)) return '';
  // International grouping (189,000) — not lakh (1,89,000). See utils/format.js.
  return `${n.toLocaleString('en-US')} PKR`;
}

/** Same copy as backend/app.py _generate_greeting_markdown — offline + API fallback. */
export const GUIDE_GREETING_MARKDOWN = `### 👋 Hello! Welcome to GenSpark Builds AI Assistant

Yes, I can absolutely help you design and engineer the perfect custom PC setup.

To initialize my building framework, please let me know:
1. 💰 **Your target budget** (e.g. *1.20 lakh budget*, *120k*, or *150000 PKR*)
2. 🛠️ **Your primary deployment purpose** (e.g. *Gaming build*, *Video editing*, or *Office tasking*)

Our vision system can detect parts you already own (CPU, GPU, RAM, motherboard, PSU, cooler, storage) and exclude them from your quote.`;

const SLOT_LABELS_FALLBACK = {
  cpu: 'CPU',
  gpu: 'GPU',
  motherboard: 'Motherboard',
  ram: 'RAM',
  storage: 'Storage',
  psu: 'PSU',
  case: 'Case',
};

/** Rebuild markdown when API returns fallback_build but an empty recommendation_markdown. */
export function buildMarkdownFromFallbackBuild(parts, purpose = '', budget = '') {
  if (!parts || typeof parts !== 'object') return '';
  const rows = Object.entries(SLOT_LABELS_FALLBACK)
    .filter(([key]) => parts[key])
    .map(([key, label]) => `| ${label} | ${parts[key]} | — |`);
  if (!rows.length) return '';
  const budgetLine = budget ? `**${budget}**` : 'your budget';
  const purposeLine = purpose || 'your workload';
  return [
    '## Summary',
    `Catalog estimate for **${purposeLine}** at ${budgetLine}. Live OpenAI was unavailable — prices are indicative.`,
    '',
    '## Recommended Components',
    '| Component Type | Component Name | Est. Price (PKR) |',
    '| --- | --- | ---: |',
    ...rows,
  ].join('\n');
}

/** API-shaped payload when /api/recommend-build is down or returns an error for a greeting. */
export function buildGuideGreetingResponse(extra = {}) {
  return {
    success: true,
    conversational: true,
    source: AI_SOURCE.GUIDE,
    recommendation_markdown: GUIDE_GREETING_MARKDOWN,
    fallback: false,
    gemini_active: false,
    ...extra,
  };
}
