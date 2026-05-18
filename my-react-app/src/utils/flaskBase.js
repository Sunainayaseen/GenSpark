const FLASK_BASE_KEY = 'genspark_flask_base';

/** Live production API (Railway). Default when VITE_API_BASE is unset. */
export const RAILWAY_API_BASE = 'https://genspark-production.up.railway.app';

const LOCAL_API_PATTERN = /^https?:\/\/(?:127\.0\.0\.1|localhost):5000/i;

/**
 * API origin for JSON calls (no trailing slash).
 * Set VITE_API_BASE in .env / .env.production (see .env.example).
 */
export function getApiBase() {
  const fromEnv = import.meta.env?.VITE_API_BASE?.replace(/\/$/, '');
  return fromEnv || RAILWAY_API_BASE;
}

/**
 * Rewrites localhost API links from the backend to the configured production base.
 * Used for email verification URLs returned by POST /api/register.
 */
export function normalizeBackendUrl(url) {
  if (!url || typeof url !== 'string') return url;
  return url.replace(LOCAL_API_PATTERN, getApiBase());
}

/** Prefix for REST JSON routes, e.g. https://genspark-production.up.railway.app/api */
export function getApiPrefix() {
  return `${getApiBase()}/api`;
}

/** Full URL for an API path, e.g. getApiUrl('/detect/component'). */
export function getApiUrl(path) {
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${getApiPrefix()}${p}`;
}

/** Flask HTML / OAuth base URL (same host as API). */
export function getFlaskBase() {
  return getApiBase();
}

/** Same as getFlaskBase — kept for callers that retry on network failure. */
export function getFlaskBaseFallback() {
  return getApiBase();
}

export function setFlaskBaseUsed(base) {
  if (typeof window !== 'undefined' && window.sessionStorage && base) {
    sessionStorage.setItem(FLASK_BASE_KEY, base);
  }
}

export function getFlaskLoginUrl() {
  return `${getFlaskBase()}/auth/login`;
}

export function getFlaskVendorDashboardUrl() {
  return `${getFlaskBase()}/vendor/dashboard`;
}

export function getFlaskAdminDashboardUrl() {
  return `${getFlaskBase()}/admin/dashboard`;
}

export function getFlaskApiLoginUrl() {
  return getApiUrl('/login');
}

export function getFlaskChangePasswordUrl() {
  return getApiUrl('/change-password');
}
