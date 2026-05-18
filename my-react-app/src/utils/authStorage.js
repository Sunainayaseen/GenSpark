/** Persisted auth — survives page refresh (localStorage). */
const AUTH_USER_KEY = 'genspark_user';
const AUTH_TOKEN_KEY = 'genspark_token';
const LEGACY_AUTH_KEY = 'genspark_auth';

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
  migrateLegacyAuth();
  try {
    const rawUser = localStorage.getItem(AUTH_USER_KEY);
    const token = localStorage.getItem(AUTH_TOKEN_KEY) || null;
    if (!rawUser) return { user: null, token: null };
    const user = JSON.parse(rawUser);
    if (!user?.email) return { user: null, token: null };
    return { user, token };
  } catch (_) {
    return { user: null, token: null };
  }
}

export function saveAuthSession(user, token) {
  try {
    if (user?.email) {
      localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(AUTH_USER_KEY);
    }
    if (token) {
      localStorage.setItem(AUTH_TOKEN_KEY, token);
    } else if (!user) {
      localStorage.removeItem(AUTH_TOKEN_KEY);
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
  } catch (_) {
    /* ignore */
  }
}

export function getStoredToken() {
  return loadAuthSession().token;
}

/** Authorization header for API calls (JWT Bearer). */
export function getAuthHeaders(extra = {}) {
  const token = getStoredToken();
  const headers = { ...extra };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}
