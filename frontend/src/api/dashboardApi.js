/**
 * API client for GenSpark Flask backend on Railway.
 * Every request resolves getApiPrefix() at call time → production uses
 * https://genspark-production.up.railway.app/api (see flaskBase.js).
 */

import { getApiPrefix, RAILWAY_API_BASE } from '../utils/flaskBase';
import { getAuthHeaders } from '../utils/authStorage';

export { RAILWAY_API_BASE };

const DEFAULT_TIMEOUT_MS = 20000;

async function request(endpoint, options = {}) {
  const apiPrefix = getApiPrefix();
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${apiPrefix}${path}`;
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const config = {
    ...options,
    signal: controller.signal,
    headers: getAuthHeaders({
      'Content-Type': 'application/json',
      ...options.headers,
    }),
    credentials: 'include',
  };
  delete config.timeoutMs;
  if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
    config.body = JSON.stringify(options.body);
  }
  let res;
  try {
    res = await fetch(url, config);
  } catch (networkErr) {
    const aborted = networkErr?.name === 'AbortError';
    const err = new Error(
      aborted
        ? `Request timed out after ${timeoutMs / 1000}s. Is MySQL running and START-GENSPARK-DEV.bat backend window open?`
        : 'Could not reach the GenSpark API. On the live site this usually means Railway is down or not deployed — ' +
            'open the Railway dashboard, redeploy the **vendor dashboard** service from GitHub `main`, then refresh. ' +
            'For local testing run **START-GENSPARK-DEV.bat** (backend on port 5000).'
    );
    err.cause = networkErr;
    throw err;
  } finally {
    clearTimeout(timer);
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
    const railwayDead =
      res.status === 404 &&
      parsed &&
      typeof parsed === 'object' &&
      (parsed.message === 'Application not found' || parsed.code === 404);

    const errMsg = railwayDead
      ? 'Production API is offline (Railway app not found). Redeploy the **vendor dashboard** service on Railway or Render, then update vercel.json + VITE_API_BASE. See scripts/DEPLOY-PRODUCTION-API.md in the repo.'
      : res.status === 404
        ? 'GenSpark API route not found (404). Railway may be running the wrong app or needs a fresh deploy from **vendor dashboard** on GitHub main.'
        : res.status === 500 && !fromJson
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
