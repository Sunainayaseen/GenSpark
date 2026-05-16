const FLASK_BASE_KEY = 'genspark_flask_base';

/**
 * When the React app runs on Vite (5173/4173), all /api calls must be same-origin
 * (proxied) so Flask session cookies are set and sent with fetch(..., credentials).
 * Direct http://host:5000/api/login sets a cookie for :5000 — cart on :5173 won't send it.
 */
function useSameOriginApi() {
  if (typeof window === 'undefined') return false;
  if (import.meta.env?.VITE_API_BASE) return false;
  const p = window.location.port;
  return p === '5173' || p === '4173';
}

/**
 * Flask (run.py) base URL.
 * Agar pehle fallback se login hua ho to woh stored base use hota hai (cookie/iframe same origin).
 */
export function getFlaskBase() {
  if (useSameOriginApi()) {
    return '';
  }
  if (typeof window !== 'undefined' && window.sessionStorage) {
    const stored = sessionStorage.getItem(FLASK_BASE_KEY);
    if (stored) return stored;
  }
  const h = typeof window !== 'undefined' ? window.location.hostname : '';
  if (!h) return '';
  return `http://${h}:5000`;
}

/** Fallback URL jab getFlaskBase() se fetch fail ho (e.g. localhost resolve nahi hota). */
export function getFlaskBaseFallback() {
  const h = typeof window !== 'undefined' ? window.location.hostname : '';
  if (h === 'localhost' || h === '127.0.0.1') return 'http://127.0.0.1:5000';
  return null;
}

/** Login success ke baad agar fallback URL use kiya ho to call karo taake iframe bhi usi se load ho. */
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
  const base = getFlaskBase();
  return base ? `${base}/api/login` : '/api/login';
}

export function getFlaskChangePasswordUrl() {
  const base = getFlaskBase();
  return base ? `${base}/api/change-password` : '/api/change-password';
}
