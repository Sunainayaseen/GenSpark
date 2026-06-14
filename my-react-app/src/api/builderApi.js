/**
 * GenSpark Intelligent PC Builder — Flask OpenAI + MySQL ERP endpoints.
 */
import axios from 'axios';
import { getApiUrl, getApiPrefix } from '../utils/flaskBase';

/** @deprecated Use postRecommendBuild — kept for any legacy inline fetch in Chatbot. */
export { getApiUrl, getApiPrefix };

const jsonHeaders = { 'Content-Type': 'application/json' };

const LOCAL_API_PATTERN = /^https?:\/\/(?:127\.0\.0\.1|localhost)(:\d+)?/i;
const HF_API_PATTERN = /\.hf\.space/i;

/** Rules engine is ~5ms locally; cloud cold starts need longer. */
export function getRecommendBuildTimeoutMs() {
  const fromEnv = Number(import.meta.env?.VITE_RECOMMEND_BUILD_TIMEOUT_MS);
  if (fromEnv > 0 && !Number.isNaN(fromEnv)) {
    return fromEnv;
  }
  const base = import.meta.env?.VITE_API_BASE?.replace(/\/$/, '') || '';
  if (import.meta.env?.DEV) {
    if (!base || LOCAL_API_PATTERN.test(base)) {
      return 12_000;
    }
  }
  if (HF_API_PATTERN.test(base)) {
    return 90_000;
  }
  return 60_000;
}

function isAxiosTimeout(error) {
  return (
    error?.code === 'ECONNABORTED' ||
    /timeout/i.test(String(error?.message || ''))
  );
}

/**
 * @param {{ detected_part: string, message?: string, build_requested?: boolean, budget?: string, purpose?: string }} payload
 */
function axiosErrorMessage(error, fallback) {
  if (isAxiosTimeout(error)) {
    const seconds = Math.round(getRecommendBuildTimeoutMs() / 1000);
    if (import.meta.env?.DEV) {
      return (
        `Request timed out after ${seconds}s. Start **START-GENSPARK-DEV.bat** ` +
        '(backend on port 5000), then refresh **http://localhost:5173/chatbot**. ' +
        'Local rules engine should answer in under 1 second when the API is up.'
      );
    }
    return (
      `AI backend timed out after ${seconds}s. The server may be cold-starting ` +
      'or overloaded — wait 30s and retry, or point VITE_API_BASE to a faster host.'
    );
  }
  const status = error?.response?.status;
  const apiError = error?.response?.data?.error;
  if (status === 404) {
    return (
      apiError === 'Not found'
        ? 'AI route missing on the server. Restart vendor dashboard (run.py) or START-GENSPARK-DEV.bat, then refresh.'
        : apiError ||
            'AI endpoint not found on port 5000. Restart vendor dashboard/run.py and refresh the chatbot page.'
    );
  }
  if (apiError === 'Not found') {
    return 'AI route missing on the server. Restart vendor dashboard (run.py) or START-GENSPARK-DEV.bat, then refresh.';
  }
  return apiError || error?.message || fallback;
}

/**
 * YOLO component detection — multipart image upload.
 * @param {File|Blob} file
 * @param {{ confidence?: number }} [options]
 */
export async function postDetectComponent(file, options = {}) {
  const formData = new FormData();
  formData.append('image', file);
  if (options.confidence != null) {
    formData.append('conf', String(options.confidence));
  }

  const response = await fetch(getApiUrl('/detect/component'), {
    method: 'POST',
    body: formData,
  });
  const data = await response.json().catch(() => ({}));

  if (!response.ok || !data?.success) {
    throw new Error(data?.error || 'Component detection failed.');
  }
  return data;
}

/**
 * In-stock candidate parts per editable slot (cpu/gpu/ram/storage/psu). Passing the
 * current build map filters out parts that are hard-incompatible with it (e.g. a
 * DDR4 stick on a DDR5 board) so the dropdowns never offer an unusable component.
 * @param {Record<string, number>} [build]
 */
export async function getBuildOptions(build) {
  try {
    const { data } = await axios.post(
      getApiUrl('/build-options'),
      { build: build || {} },
      { headers: jsonHeaders, timeout: 20000 }
    );
    if (!data?.success) {
      throw new Error(data?.error || 'Failed to load component options.');
    }
    return data.options || {};
  } catch (error) {
    throw new Error(axiosErrorMessage(error, 'Failed to load component options.'));
  }
}

/**
 * Evaluate a single customization against the current build. Returns the 4-level
 * verdict (fully_compatible / unnecessary / needs_adjustments / incompatible).
 * @param {{purpose?:string, budget?:string, build:Record<string,number>,
 *          change:{slot:string, component_id:number}, mode?:string}} payload
 */
export async function postEvaluateCustomization(payload) {
  try {
    const { data } = await axios.post(getApiUrl('/evaluate-customization'), payload, {
      headers: jsonHeaders,
      timeout: 20000,
    });
    if (!data?.success) {
      throw new Error(data?.error || 'Customization evaluation failed.');
    }
    return data;
  } catch (error) {
    throw new Error(axiosErrorMessage(error, 'Customization evaluation failed.'));
  }
}

/**
 * Rule-based proactive upgrade suggestions for the current build
 * (e.g. "32GB RAM recommended for gaming"). Each names a concrete compatible part.
 * @param {{purpose?:string, budget?:string|number, build:Record<string,number>}} payload
 */
export async function getBuildSuggestions({ purpose, budget, build }) {
  try {
    const { data } = await axios.post(
      getApiUrl('/build-suggestions'),
      { purpose, budget: budget != null ? String(budget) : undefined, build: build || {} },
      { headers: jsonHeaders, timeout: 20000 }
    );
    if (!data?.success) throw new Error(data?.error || 'Failed to load suggestions.');
    return data.suggestions || [];
  } catch (error) {
    throw new Error(axiosErrorMessage(error, 'Failed to load suggestions.'));
  }
}

export async function postRecommendBuild(payload) {
  try {
    const { data } = await axios.post(getApiUrl('/recommend-build'), payload, {
      headers: jsonHeaders,
      timeout: getRecommendBuildTimeoutMs(),
    });
    if (!data?.success) {
      throw new Error(data?.error || 'Build recommendation failed.');
    }
    return data;
  } catch (error) {
    throw new Error(axiosErrorMessage(error, 'Build recommendation failed.'));
  }
}

/**
 * @param {Record<string, string|number|null>} partsPayload
 */
export async function postCreateBuild(partsPayload) {
  try {
    const { data } = await axios.post(getApiUrl('/create-build'), partsPayload, {
      headers: jsonHeaders,
      timeout: 60000,
    });
    if (!data?.success) {
      throw new Error(data?.error || 'Could not save build to inventory.');
    }
    return data;
  } catch (error) {
    throw new Error(axiosErrorMessage(error, 'Could not save build to inventory.'));
  }
}

/** Map markdown "Component Type" (or legacy Component) column → create-build JSON keys. */
const PART_ROW_MAP = {
  cpu: 'cpu',
  gpu: 'gpu',
  'graphics card': 'gpu',
  motherboard: 'motherboard',
  mobo: 'motherboard',
  ram: 'ram',
  memory: 'ram',
  storage: 'storage',
  ssd: 'storage',
  'hard drive': 'storage',
  nvme: 'storage',
  psu: 'psu',
  'power supply': 'psu',
  case: 'case',
  chassis: 'case',
  'component type': null,
};

/**
 * Parse "## Recommended Components" table rows from Gemini Markdown.
 * @returns {Record<string, string>}
 */
export function parseGeminiPartsFromMarkdown(markdown) {
  const parts = {};
  if (!markdown) return parts;

  for (const line of markdown.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed.startsWith('|')) continue;
    if (/^\|[\s\-:|]+\|$/i.test(trimmed)) continue;
    if (/component\s*type\s*\|/i.test(trimmed) && /component\s*name\s*\|/i.test(trimmed)) {
      continue;
    }
    if (/component\s*\|/i.test(trimmed) && /model\s*\|/i.test(trimmed)) continue;

    const cells = trimmed
      .split('|')
      .map((c) => c.trim())
      .filter((c) => c.length > 0);
    if (cells.length < 2) continue;

    const slot = PART_ROW_MAP[cells[0].toLowerCase()];
    const nameCell = cells[1];
    if (slot && nameCell && !parts[slot]) {
      parts[slot] = nameCell;
    }
  }
  return parts;
}

/** Hardware slots required by POST /api/create-build */
export const REQUIRED_BUILD_SLOTS = [
  'cpu',
  'gpu',
  'motherboard',
  'ram',
  'storage',
  'psu',
  'case',
];

const _NON_PRODUCT_MODEL_RE =
  /^(owned|user'?s?\s+existing|n\/a|na|—|-+|tbd|none|\(owned\)|integrated|onboard)$/i;

/**
 * Normalize a Gemini table "Model" cell into a product name for ERP lookup.
 * @param {string} raw
 * @returns {string}
 */
export function sanitizeGeminiPartName(raw) {
  if (raw == null) return '';
  let name = String(raw).trim();
  if (!name || _NON_PRODUCT_MODEL_RE.test(name)) return '';
  name = name
    .replace(/^\(owned\)\s*/i, '')
    .replace(/\s*\(owned\)\s*$/i, '')
    .replace(/\s*—\s*est\.?\s*price.*$/i, '')
    .trim();
  if (_NON_PRODUCT_MODEL_RE.test(name)) return '';
  return name;
}

/**
 * Merge cached payload with freshly parsed markdown; return ERP-ready slots.
 * @param {string|null|undefined} markdown
 * @param {Record<string, string>|null|undefined} cachedPayload
 * @returns {{ parts: Record<string, string>, missing: string[] }}
 */
export function extractGeminiBuildSlots(markdown, cachedPayload = null) {
  const fromMarkdown = parseGeminiPartsFromMarkdown(markdown || '');
  const fromCache =
    cachedPayload && typeof cachedPayload === 'object' ? { ...cachedPayload } : {};

  const merged = { ...fromCache, ...fromMarkdown };
  /** @type {Record<string, string>} */
  const parts = {};

  for (const slot of REQUIRED_BUILD_SLOTS) {
    const sanitized = sanitizeGeminiPartName(merged[slot]);
    if (sanitized) parts[slot] = sanitized;
  }

  const missing = REQUIRED_BUILD_SLOTS.filter((key) => {
    if (key === 'gpu') {
      const raw = merged[key];
      if (!raw || _NON_PRODUCT_MODEL_RE.test(String(raw).trim())) return false;
    }
    return !parts[key];
  });
  return { parts, missing };
}
