# Fix production API (Vercel → vendors / checkout)

Symptom: **"Could not reach the API"** on https://genspark-frontend.vercel.app/vendor-assignment

Cause: `https://genspark-production.up.railway.app` returns **Application not found** (Railway service removed or URL changed).

## Fix A — Redeploy on Railway (recommended)

1. Open [Railway Dashboard](https://railway.app/dashboard)
2. **New Project** → **Deploy from GitHub repo** → select **GenSpark**
3. Settings → **Root Directory**: `vendor dashboard`
4. **Variables** (minimum):
   - `FLASK_ENV=production`
   - `USE_SQLITE=0`
   - `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` (Railway MySQL plugin or your cloud MySQL)
   - `SECRET_KEY` (random string)
   - `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` (for online pay)
5. Deploy → copy the public URL, e.g. `https://genspark-production-xxxx.up.railway.app`
6. Test: `https://YOUR-URL/api/health` and `https://YOUR-URL/api/vendors`

### Update frontend to new API URL

Replace `https://genspark-production.up.railway.app` with **your new URL** in:

- `my-react-app/vercel.json` → `destination` under `/api/:path*`
- `my-react-app/.env.production` → `VITE_API_BASE=...`
- `my-react-app/src/config/deployUrls.js` → `LIVE_API_URL`

Redeploy **Vercel** (push to main or Redeploy in Vercel dashboard).

Optional: set **Vercel** → Project → Environment Variables → `VITE_API_BASE` = your Railway URL.

## Fix B — Render.com

See `vendor dashboard/render.yaml`. After deploy, use the Render URL in the three files above.

## Local dev (works without Railway)

```bat
START-GENSPARK-DEV.bat
```

Open http://localhost:5173/vendor-assignment — uses `backend` on port 5000 + local MySQL vendors.
