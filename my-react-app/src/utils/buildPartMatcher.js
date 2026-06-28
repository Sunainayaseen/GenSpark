import axios from 'axios';
import { getApiUrl } from '../api/builderApi';

const SLOT_KEY_FROM_LABEL = {
  CPU: 'cpu',
  GPU: 'gpu',
  Motherboard: 'motherboard',
  RAM: 'ram',
  Storage: 'storage',
  PSU: 'psu',
  Case: 'case',
};

const SKIP_VALUES = /^integrated$|^n\/a$|^none$|^—$|^-$/i;

export function partShouldSkipCart(part) {
  const query = String(part?.value || '').trim().toLowerCase();
  return !query || query === 'integrated' || SKIP_VALUES.test(query);
}

function slotKeyFromPart(part) {
  const label = String(part?.name || '').trim();
  if (SLOT_KEY_FROM_LABEL[label]) return SLOT_KEY_FROM_LABEL[label];
  const lower = label.toLowerCase();
  if (SLOT_KEY_FROM_LABEL[lower.toUpperCase()]) return lower;
  return lower;
}

/**
 * Resolve AI label → catalog component via backend scoring (not first search hit).
 */
export async function findComponentIdForPart(part) {
  if (partShouldSkipCart(part)) return null;

  const slot = slotKeyFromPart(part);
  const name = String(part?.value || part?.name || '').trim();
  if (!name || !slot) return null;

  try {
    const url = `${getApiUrl('/components/resolve')}?slot=${encodeURIComponent(slot)}&name=${encodeURIComponent(name)}`;
    const res = await fetch(url, { credentials: 'include' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data?.success || !data?.found || !data?.component?.id) {
      return null;
    }
    return data.component.id;
  } catch {
    return null;
  }
}

/**
 * Bulk add full build — one API call, full cart returned (no last-item overwrite).
 * @param {Record<string, string>} partsMap — keys: cpu, gpu, motherboard, ram, storage, psu, case
 */
export async function addBuildPartsBulk(partsMap) {
  const { data } = await axios.post(
    getApiUrl('/cart/add-build-parts'),
    { parts: partsMap },
    { headers: { 'Content-Type': 'application/json' }, timeout: 60000 }
  );
  if (!data?.success) {
    throw new Error(data?.error || 'Could not add build to cart.');
  }
  return data;
}

/**
 * Legacy per-part loop — prefer addBuildPartsBulk when you have a full slot map.
 */
export async function addBuildPartsToCart(parts, addToCart) {
  const slotMap = {};
  for (const part of parts || []) {
    if (partShouldSkipCart(part)) continue;
    const key = slotKeyFromPart(part);
    if (key && part.value) slotMap[key] = String(part.value).trim();
  }
  if (Object.keys(slotMap).length === 0) return 0;

  try {
    const result = await addBuildPartsBulk(slotMap);
    return Number(result.added_count || 0);
  } catch {
    let addedCount = 0;
    const usedIds = new Set();
    for (const part of parts || []) {
      if (partShouldSkipCart(part)) continue;
      try {
        const componentId = await findComponentIdForPart(part);
        if (!componentId || usedIds.has(componentId)) continue;
        const ok = await addToCart(
          { id: componentId, item_type: 'component', vendor_id: null },
          1
        );
        if (ok) {
          usedIds.add(componentId);
          addedCount += 1;
        }
      } catch {
        // try next part
      }
    }
    return addedCount;
  }
}
