const FLASK_BASE_KEY = 'genspark_flask_base';

/** Production backend (Railway). Overridden by VITE_API_BASE when set. */
export const RAILWAY_API_BASE = 'https://genspark-production.up.railway.app';

/**
 * API origin for JSON calls (no trailing slash).
 * - VITE_API_BASE from .env (build-time)
 * - Production fallback: Railway URL
 * - Dev on Vite (5173/4173): '' → use relative /api (proxy)
 */
export function getApiBase() {
  const fromEnv = import.meta.env?.VITE_API_BASE?.replace(/\/$/, '');
  if (fromEnv) return fromEnv;
  if (import.meta.env?.PROD) return RAILWAY_API_BASE;
  return '';
}

/** Prefix for REST JSON routes: `https://host/api` or `/api`. */
export function getApiPrefix() {
  const base = getApiBase();
  return base ? `${base}/api` : '/api';
}

/** Full URL for an API path, e.g. getApiUrl('/detect/component'). */
export function getApiUrl(path) {
  const p = path.startsWith('/') ? path : `/${path}`;
  const prefix = getApiPrefix();
  if (prefix.startsWith('http')) return `${prefix}${p}`;
  return `${prefix}${p}`;
}

/**
 * When the React app runs on Vite (5173/4173), all /api calls must be same-origin
 * (proxied) so Flask session cookies are set and sent with fetch(..., credentials).
 */
function useSameOriginApi() {
  if (typeof window === 'undefined') return false;
  if (getApiBase()) return false;
  const p = window.location.port;
  return p === '5173' || p === '4173';
}

/**
 * Flask (run.py) base URL — HTML pages (login iframe, admin, vendor dashboards).
 */
export function getFlaskBase() {
  const configured = getApiBase();
  if (configured) return configured;
  if (useSameOriginApi()) return '';
  if (typeof window !== 'undefined' && window.sessionStorage) {
    const stored = sessionStorage.getItem(FLASK_BASE_KEY);
    if (stored) return stored;
  }
  const h = typeof window !== 'undefined' ? window.location.hostname : '';
  if (!h) return '';
  return `http://${h}:5000`;
}

/** Fallback URL jab getFlaskBase() se fetch fail ho (local dev only). */
export function getFlaskBaseFallback() {
  if (getApiBase()) return null;
  const h = typeof window !== 'undefined' ? window.location.hostname : '';
  if (h === 'localhost' || h === '127.0.0.1') return 'http://127.0.0.1:5000';
  return null;
}

export function setFlaskBaseUsed(base) {
  if (typeof window !== 'undefined' && window.sessionStorage && base) {
    sessionStorage.setItem(FLASK_BASE_KEY, base);
  }
}

export function getFlaskLoginUrl() {
  const base = getFlaskBase();
  return base ? `${base}/auth/login` : '/flask/auth/login';
}

export function getFlaskVendorDashboardUrl() {
  const base = getFlaskBase();
  return base ? `${base}/vendor/dashboard` : '/flask/vendor/dashboard';
}

export function getFlaskAdminDashboardUrl() {
  const base = getFlaskBase();
  return base ? `${base}/admin/dashboard` : '/flask/admin/dashboard';
}

export function getFlaskApiLoginUrl() {
  return getApiUrl('/login');
}

export function getFlaskChangePasswordUrl() {
  return getApiUrl('/change-password');
}
