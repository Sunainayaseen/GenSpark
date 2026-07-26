/** Persisted auth — survives page refresh (localStorage). */
import { getApiBase, RAILWAY_API_BASE } from './flaskBase';

const AUTH_USER_KEY = 'genspark_user';
const AUTH_TOKEN_KEY = 'genspark_token';
const LEGACY_AUTH_KEY = 'genspark_auth';
const API_ORIGIN_KEY = 'genspark_api_origin';

/** Immediate JWT for fetch right after login (before localStorage read races). */
let memoryToken = null;

export const AUTH_UPDATED_EVENT = 'genspark-auth-updated';

/**
 * Clear auth if user switched API base (e.g. local Flask vs live Railway).
 */
export function ensureApiOriginConsistency() {
  try {
    const current = getApiBase();
    const previous = localStorage.getItem(API_ORIGIN_KEY);
    if (previous && previous !== current) {
      clearAuthSession();
    }
    localStorage.setItem(API_ORIGIN_KEY, current);
  } catch (_) {
    /* private mode / quota */
  }
}

function migrateLegacyAuth() {
  try {
    if (localStorage.getItem(AUTH_USER_KEY)) return;
    const raw = localStorage.getItem(LEGACY_AUTH_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (parsed?.email) {
      saveAuthSession(parsed, null);
    }
    localStorage.removeItem(LEGACY_AUTH_KEY);
  } catch (_) {
    /* ignore */
  }
}

export function loadAuthSession() {
  ensureApiOriginConsistency();
  migrateLegacyAuth();
  try {
    const rawUser = localStorage.getItem(AUTH_USER_KEY);
    const token = memoryToken || localStorage.getItem(AUTH_TOKEN_KEY) || null;
    if (!rawUser) return { user: null, token: null };
    const user = JSON.parse(rawUser);
    if (!user?.email) return { user: null, token: null };
    if (token) memoryToken = token;
    return { user, token };
  } catch (_) {
    return { user: null, token: null };
  }
}

/**
 * Save user + JWT. Updates localStorage and in-memory token so the next
 * fetch immediately sends Authorization: Bearer <token>.
 */
export function saveAuthSession(user, token) {
  try {
    if (user?.email) {
      localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(AUTH_USER_KEY);
    }
    const jwt =
      token || user?.token || user?.access_token || user?.jwt || null;
    if (jwt) {
      const normalized = String(jwt);
      localStorage.setItem(AUTH_TOKEN_KEY, normalized);
      memoryToken = normalized;
    } else if (!user) {
      localStorage.removeItem(AUTH_TOKEN_KEY);
      memoryToken = null;
    }
    localStorage.removeItem(LEGACY_AUTH_KEY);
  } catch (_) {
    /* ignore quota / private mode */
  }
}

export function clearAuthSession() {
  try {
    localStorage.removeItem(AUTH_USER_KEY);
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(LEGACY_AUTH_KEY);
    memoryToken = null;
  } catch (_) {
    /* ignore */
  }
}

export function getStoredToken() {
  if (memoryToken) return memoryToken;
  return loadAuthSession().token;
}

/** Authorization header for every API call (reads latest token). */
export function getAuthHeaders(extra = {}) {
  const token = getStoredToken();
  const headers = { ...extra };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

/** Persist session and notify cart/other listeners (production sync). */
export function publishAuthSession(user, token) {
  saveAuthSession(user, token);
  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new CustomEvent(AUTH_UPDATED_EVENT, {
        detail: { user, token: getStoredToken() },
      })
    );
  }
}

export function getApiOriginForDebug() {
  return getApiBase() || RAILWAY_API_BASE;
}
