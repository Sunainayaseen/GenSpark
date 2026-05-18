/**
 * API client for GenSpark Flask backend on Railway.
 * Base URL: VITE_API_BASE in .env / .env.production (see src/utils/flaskBase.js).
 */

import { getApiPrefix } from '../utils/flaskBase';
import { getAuthHeaders } from '../utils/authStorage';

const API_PREFIX = getApiPrefix();

async function request(endpoint, options = {}) {
  const url = `${API_PREFIX}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const config = {
    headers: getAuthHeaders({
      'Content-Type': 'application/json',
      ...options.headers,
    }),
    // Needed for Flask session-based carts and auth cookies.
    credentials: 'include',
    ...options,
  };
  if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
    config.body = JSON.stringify(options.body);
  }
  const res = await fetch(url, config);
  if (!res.ok) {
    // Read response body once to avoid "body stream already read".
    const raw = await res.text();
    let parsed = null;
    try {
      parsed = raw ? JSON.parse(raw) : null;
    } catch {
      parsed = raw;
    }
    const fromJson =
      parsed && typeof parsed === 'object'
        ? parsed.error || parsed.message || null
        : null;
    const baseMsg =
      fromJson ||
      (typeof parsed === 'string' && parsed.length > 0 && parsed.length < 400 && !parsed.includes('<!DOCTYPE')
        ? parsed
        : null) ||
      res.statusText ||
      `Request failed (${res.status})`;
    const errMsg =
      res.status === 500 && !fromJson
        ? `${baseMsg} — The GenSpark API may be unavailable; try again later.`
        : baseMsg;
    const err = new Error(errMsg);
    err.status = res.status;
    err.response = res;
    err.data = parsed && typeof parsed === 'object' ? parsed : { error: baseMsg };
    throw err;
  }
  const contentType = res.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return res.json();
  }
  return res.text();
}

/** GET request to dashboard API */
export function dashboardGet(endpoint) {
  return request(endpoint, { method: 'GET' });
}

/** POST request to dashboard API */
export function dashboardPost(endpoint, body) {
  return request(endpoint, { method: 'POST', body });
}

/** PUT request to dashboard API */
export function dashboardPut(endpoint, body) {
  return request(endpoint, { method: 'PUT', body });
}

/** DELETE request to dashboard API */
export function dashboardDelete(endpoint, body) {
  return request(endpoint, { method: 'DELETE', body });
}

// Example usage – adapt endpoints to match your Python dashboard:
// export async function getDashboardStats() {
//   return dashboardGet('/stats');
// }
// export async function getOrders() {
//   return dashboardGet('/orders');
// }
