import { LIVE_API_URL, LIVE_FRONTEND_URL } from '../config/deployUrls';

const FLASK_BASE_KEY = 'genspark_flask_base';

/** Live production API (Railway) — see src/config/deployUrls.js */
export const RAILWAY_API_BASE = LIVE_API_URL;

export { LIVE_FRONTEND_URL };

const LOCAL_API_PATTERN = /^https?:\/\/(?:127\.0\.0\.1|localhost):5000/i;
const VERCEL_HOST_RE = /vercel\.app/i;

/**
 * API origin for JSON calls (no trailing slash).
 * Production builds always use Railway unless VITE_API_BASE is another non-Vercel API URL.
 */
const LOCAL_DEV_API = 'http://127.0.0.1:5000';

export function getApiBase() {
  const railway = LIVE_API_URL.replace(/\/$/, '');
  const fromEnv = import.meta.env?.VITE_API_BASE?.replace(/\/$/, '');

  // Vite dev (localhost, 127.0.0.1, or LAN IP like 192.168.x.x:5173):
  // same-origin + vite.config proxy /api → http://127.0.0.1:5000
  if (import.meta.env.DEV && typeof window !== 'undefined') {
    if (fromEnv && LOCAL_API_PATTERN.test(fromEnv)) {
      return fromEnv;
    }
    return window.location.origin.replace(/\/$/, '');
  }

  if (import.meta.env.PROD && typeof window !== 'undefined') {
    const host = window.location.hostname || '';
    // Vercel: same-origin /api → vercel.json proxies to Railway (avoids CORS "Failed to fetch")
    if (VERCEL_HOST_RE.test(host)) {
      return window.location.origin.replace(/\/$/, '');
    }
    if (fromEnv && !LOCAL_API_PATTERN.test(fromEnv) && !VERCEL_HOST_RE.test(fromEnv)) {
      return fromEnv;
    }
    return railway;
  }

  if (import.meta.env.PROD) {
    if (fromEnv && !LOCAL_API_PATTERN.test(fromEnv) && !VERCEL_HOST_RE.test(fromEnv)) {
      return fromEnv;
    }
    return railway;
  }

  if (fromEnv && !VERCEL_HOST_RE.test(fromEnv)) {
    return fromEnv;
  }
  return railway;
}

const FRONTEND_HOST_RE =
  /(?:^|\.)vercel\.app$|^localhost$|^127\.0\.0\.1$/i;

/**
 * Registration verify links must hit Flask on Railway, not the Vercel SPA.
 * Preserves the full ?token=... query string.
 */
const VERIFY_EMAIL_PATH_RE = /\/api\/verify-email/i;
const LOCAL_VERIFY_ORIGIN_RE = /^https?:\/\/(?:127\.0\.0\.1|localhost):5000$/i;

export function normalizeVerificationUrl(rawUrl) {
  if (rawUrl == null) return rawUrl;
  const url = String(rawUrl).trim();
  if (!url) return url;

  // Dev: backend already returns correct http://127.0.0.1:5000/api/verify-email?token=...
  try {
    const parsed = new URL(url);
    if (
      import.meta.env.DEV &&
      LOCAL_VERIFY_ORIGIN_RE.test(parsed.origin) &&
      VERIFY_EMAIL_PATH_RE.test(parsed.pathname)
    ) {
      return parsed.href;
    }
  } catch (_) {
    /* fall through */
  }

  const apiBase = getApiBase().replace(/\/$/, '');

  const toApiUrl = (pathname, search = '', hash = '') => {
    let path = pathname || '/api/verify-email';
    if (!path.startsWith('/api/')) {
      path = path.startsWith('/') ? `/api${path}` : `/api/${path}`;
    }
    return `${apiBase}${path}${search}${hash}`;
  };

  if (import.meta.env.PROD) {
    try {
      const parsed = new URL(url);
      return toApiUrl(parsed.pathname, parsed.search, parsed.hash);
    } catch (_) {
      if (url.startsWith('/')) {
        const q = url.indexOf('?');
        const path = q >= 0 ? url.slice(0, q) : url;
        const search = q >= 0 ? url.slice(q) : '';
        return toApiUrl(path, search);
      }
    }
    return url.replace(LOCAL_API_PATTERN, apiBase).replace(VERCEL_HOST_RE, apiBase);
  }

  try {
    const parsed = new URL(url);
    const isLocal = /^https?:\/\/(?:127\.0\.0\.1|localhost):5000$/i.test(parsed.origin);
    const isFrontend = FRONTEND_HOST_RE.test(parsed.hostname);
    if (isLocal || isFrontend) {
      return toApiUrl(parsed.pathname, parsed.search, parsed.hash);
    }
    return parsed.href;
  } catch (_) {
    if (url.startsWith('/')) {
      const q = url.indexOf('?');
      const path = q >= 0 ? url.slice(0, q) : url;
      const search = q >= 0 ? url.slice(q) : '';
      return toApiUrl(path, search);
    }
  }

  return url.replace(LOCAL_API_PATTERN, apiBase);
}

/** @deprecated Use normalizeVerificationUrl */
export function normalizeBackendUrl(url) {
  return normalizeVerificationUrl(url);
}

/** Prefix for REST JSON routes, e.g. https://genspark-production.up.railway.app/api */
export function getApiPrefix() {
  return `${getApiBase()}/api`;
}

/** Full URL for an API path, e.g. getApiUrl('/login'). */
export function getApiUrl(path) {
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${getApiPrefix()}${p}`;
}

export function getFlaskBase() {
  return getApiBase();
}

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
  return getApiUrl('/force-update-password');
}
