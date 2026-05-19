/**
 * API client for GenSpark Flask backend on Railway.
 * Every request resolves getApiPrefix() at call time → production uses
 * https://genspark-production.up.railway.app/api (see flaskBase.js).
 */

import { getApiPrefix, RAILWAY_API_BASE } from '../utils/flaskBase';
import { getAuthHeaders } from '../utils/authStorage';

export { RAILWAY_API_BASE };

async function request(endpoint, options = {}) {
  const apiPrefix = getApiPrefix();
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${apiPrefix}${path}`;
  const config = {
    ...options,
    headers: getAuthHeaders({
      'Content-Type': 'application/json',
      ...options.headers,
    }),
    credentials: 'include',
  };
  if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
    config.body = JSON.stringify(options.body);
  }
  let res;
  try {
    res = await fetch(url, config);
  } catch (networkErr) {
    const err = new Error(
      'Could not reach the API. Check your internet connection, or redeploy Railway if the password route was just updated.'
    );
    err.cause = networkErr;
    throw err;
  }
  if (!res.ok) {
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

export function dashboardGet(endpoint) {
  return request(endpoint, { method: 'GET' });
}

export function dashboardPost(endpoint, body) {
  return request(endpoint, { method: 'POST', body });
}

export function dashboardPut(endpoint, body) {
  return request(endpoint, { method: 'PUT', body });
}

export function dashboardDelete(endpoint, body) {
  return request(endpoint, { method: 'DELETE', body });
}
