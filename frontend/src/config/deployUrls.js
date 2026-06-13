/**
 * Live deployment URLs — update here only, then redeploy Vercel + Railway.
 */
export const LIVE_FRONTEND_URL = 'https://genspark-frontend.vercel.app';

const _fromEnv =
  typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE
    ? String(import.meta.env.VITE_API_BASE).replace(/\/$/, '')
    : '';

/** Flask ERP API (vendor dashboard on Railway) */
export const LIVE_API_URL = _fromEnv || 'https://genspark-production.up.railway.app';
