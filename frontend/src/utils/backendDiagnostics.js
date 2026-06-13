/**
 * Backend diagnostics — quick health checks for QA debugging.
 * Call from browser console: diagnostic results logged and returned.
 */

import { getApiUrl } from './flaskBase';

export async function checkBackendHealth() {
  const results = {
    timestamp: new Date().toISOString(),
    checks: {},
  };

  try {
    // 1. Test /health (liveness, no DB required)
    try {
      const res = await fetch(getApiUrl('/health'), { credentials: 'include' });
      results.checks.liveness = {
        ok: res.ok,
        status: res.status,
        message: res.ok ? 'Backend is alive' : `HTTP ${res.status}`,
      };
    } catch (e) {
      results.checks.liveness = {
        ok: false,
        status: 0,
        message: `Connection failed: ${e.message}`,
      };
    }

    // 2. Test /api/db-health (database connectivity)
    try {
      const res = await fetch(getApiUrl('/db-health'), { credentials: 'include' });
      const data = await res.json().catch(() => ({}));
      results.checks.database = {
        ok: res.ok,
        status: res.status,
        message: data.error || data.message || (res.ok ? 'Database connected' : `HTTP ${res.status}`),
        host: data.host,
        database: data.database,
        connected: data.connected,
        components: data.components,
      };
    } catch (e) {
      results.checks.database = {
        ok: false,
        status: 0,
        message: `Connection failed: ${e.message}`,
      };
    }

    // 3. Test component search (full cart flow)
    try {
      const res = await fetch(`${getApiUrl('/components/search')}?limit=1`, {
        credentials: 'include',
      });
      const data = await res.json().catch(() => ({}));
      results.checks.components = {
        ok: res.ok,
        status: res.status,
        count: data.count,
        message: res.ok ? `Found ${data.count} components` : `HTTP ${res.status}`,
      };
    } catch (e) {
      results.checks.components = {
        ok: false,
        status: 0,
        message: `Connection failed: ${e.message}`,
      };
    }

    // 4. Test /api/create-build OPTIONS (CORS preflight)
    try {
      const res = await fetch(getApiUrl('/create-build'), {
        method: 'OPTIONS',
        credentials: 'include',
      });
      results.checks.cors = {
        ok: res.ok,
        status: res.status,
        message: res.ok ? 'CORS preflight OK' : `HTTP ${res.status}`,
        headers: {
          allowOrigin: res.headers.get('Access-Control-Allow-Origin'),
          allowMethods: res.headers.get('Access-Control-Allow-Methods'),
        },
      };
    } catch (e) {
      results.checks.cors = {
        ok: false,
        status: 0,
        message: `Connection failed: ${e.message}`,
      };
    }
  } catch (e) {
    results.error = e.message;
  }

  results.summary = {
    healthy: Object.values(results.checks).every((c) => c.ok),
    details:
      'If database check fails: ensure MySQL is running and connection string is correct.\n' +
      'If CORS fails: backend may not have CORS configured for localhost:5173.\n' +
      'If all fail: backend on port 5000 may not be running.',
  };

  return results;
}

export async function runDiagnosticsInConsole() {
  console.log('🔍 GenSpark Backend Diagnostics starting...');
  const results = await checkBackendHealth();
  console.table(
    Object.entries(results.checks).map(([name, check]) => ({
      Check: name,
      Status: check.ok ? '✅ OK' : '❌ FAIL',
      Message: check.message,
    }))
  );
  console.log('📋 Full Results:', results);
  console.log('💡', results.summary.details);
  return results;
}

// Export as window global for console access
if (typeof window !== 'undefined') {
  window.runBackendDiagnostics = runDiagnosticsInConsole;
  window.checkBackendHealth = checkBackendHealth;
}
