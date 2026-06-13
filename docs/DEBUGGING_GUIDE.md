# GenSpark Build Configurator — Network Error Debugging Guide

## Recent Fixes Applied

### 1. **Backend Route Bug (FIXED)**
- **Issue**: Vendor dashboard `/api/create-build` was calling undefined function `_json_from_backend()`
- **Fix**: Changed to use `_invoke_backend_cli('create-build', data)` which properly invokes the backend AI service
- **Status**: Route no longer crashes (500 → 503); returns proper JSON error

### 2. **Frontend Error Messages (IMPROVED)**
- **Issue**: Generic "Network Error" message didn't help diagnose root cause
- **Fix**: Enhanced error handling in BuildConfigurator to show:
  - `503` hints about backend service startup
  - `404` hints about missing routes
  - `timeout` hints about backend overload
- **File**: [my-react-app/src/pages/BuildConfigurator.jsx](../my-react-app/src/pages/BuildConfigurator.jsx#L230-L260)

### 3. **Backend Diagnostics Utility (NEW)**
- **Purpose**: Quick health checks from browser console to diagnose connectivity
- **File**: [my-react-app/src/utils/backendDiagnostics.js](../my-react-app/src/utils/backendDiagnostics.js)
- **Available endpoints**:
  - `/health` — Liveness check (no DB required)
  - `/api/db-health` — Database connectivity + component count
  - `/components/search` — Full cart flow test
  - `/create-build` — CORS preflight check

---

## QA Testing Checklist

### Step 1: Start Backend Services
```batch
# Terminal 1: Start Flask backend on port 5000
cd c:\Users\MMT\Desktop\GenSpark
START-GENSPARK-DEV.bat

# Wait for output like:
# * Running on http://127.0.0.1:5000
# * Press CTRL+C to quit
```

**Verify**: Backend port is listening
```powershell
netstat -ano | findstr :5000
# Should show: TCP 127.0.0.1:5000 LISTENING
```

### Step 2: Check Diagnostics from Browser Console
```javascript
// Press F12 (Developer Tools) → Console tab
// Run:
window.runBackendDiagnostics()

// Expected output (all checks should be ✅ OK):
// ✅ liveness - Backend is alive
// ✅ database - Database connected, X components found
// ✅ components - Found N components  
// ✅ cors - CORS preflight OK
```

**If database check fails:**
- Is MySQL running? (`mysql.exe` in Services)
- Check connection string in `backend/.env`:
  - Railway: `MYSQLHOST=...`, `MYSQL_PORT=3306`, `MYSQL_USER=...`
  - Local: `DB_HOST=localhost`, `DB_USER=root`, `DB_PASSWORD=...`

### Step 3: Start Vite Dev Server
```batch
# Terminal 2: Start Vite dev server on port 5173
cd c:\Users\MMT\Desktop\GenSpark\my-react-app
npm run dev

# Wait for:
# VITE v7.2.7 ready in XXX ms
# ➜ Local: http://127.0.0.1:5173
# ➜ press h + enter to show help
```

### Step 4: Test the Full Build Creation Flow

1. **Navigate to Configurator**: Go to [http://127.0.0.1:5173/configurator](http://127.0.0.1:5173/configurator)

2. **Select Components**:
   - CPU, GPU, Motherboard, RAM, Storage, PSU, Case
   - Click "Apply" to load from database

3. **Check Console Diagnostics** (Dev Tools → Console):
   ```javascript
   window.runBackendDiagnostics()
   ```

4. **Click "Add to Cart"**:
   - **Success** ✅: Button shows "Added to Cart", build appears in cart
   - **503 Error**: Backend AI service is offline (expected if `ai_api_cli.py` .venv not set up)
     - **Solution**: Ensure `backend/.venv` exists and has dependencies installed
       ```batch
       cd backend
       python -m venv .venv
       .venv\Scripts\activate
       pip install -r requirements.txt
       ```
   - **404 Error**: Component doesn't exist in database
     - **Solution**: Verify components exist via: `window.checkBackendHealth()`
   - **Network Error**: Vite proxy issue or CORS problem
     - **Debug**: Open Dev Tools → Network tab, check request/response headers

### Step 5: Verify Cart and Checkout Flow

1. **View Cart**: Click cart icon (top right)
2. **Items should display** with:
   - Build summary grouped by `pc_build_id`
   - Component list (CPU, GPU, etc.)
   - Total price
3. **Proceed to Checkout**: Button should be enabled
4. **Stripe test**: Use test card `4242 4242 4242 4242` (any future date, any CVC)

---

## Browser Console Commands for QA

**All these are available on any page:**

```javascript
// Full diagnostics (4 checks)
window.runBackendDiagnostics()

// Individual health checks
window.checkBackendHealth()

// Inspect cart state
console.log(JSON.stringify(window.__cartState__, null, 2))

// Check if backend is responding to OPTIONS (CORS preflight)
fetch('http://127.0.0.1:5000/api/create-build', { method: 'OPTIONS' })
  .then(r => r.status === 204 ? '✅ CORS OK' : `❌ Status ${r.status}`)
```

---

## Common Issues & Troubleshooting

| Issue | Symptom | Solution |
|-------|---------|----------|
| **Backend not running** | `ERR_CONNECTION_REFUSED` on /api/create-build | Run `START-GENSPARK-DEV.bat` in backend directory |
| **Port 5000 in use** | `Address already in use` on startup | `KILL-PORT-5000.bat` (in vendor dashboard) or `netstat -ano \| findstr :5000` |
| **Database not accessible** | `/api/db-health` returns 503 | Check MySQL running, verify DB_HOST/.env, ensure connection pool is healthy |
| **CORS error** | Browser console shows "Access to XMLHttpRequest blocked" | Backend may not be running; check proxy in vite.config.js points to 5000 |
| **Component not found** | POST /api/add-to-cart → 404 | Verify component_id exists in MySQL `components` table |
| **Build not created** | `/api/create-build` returns 503 | Backend AI CLI service offline; ensure `backend/scripts/ai_api_cli.py` exists |
| **Network Error in UI** | "Could not create build: Network Error" | Open F12 Network tab, look for actual HTTP response (may be 503, 404, etc.) |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│            Browser (http://127.0.0.1:5173)              │
│  ├─ React Components (BuildConfigurator, CartDropdown)  │
│  ├─ Vite Proxy: /api/* → http://127.0.0.1:5000          │
│  └─ Diagnostics: window.runBackendDiagnostics()         │
└──────────────────────┬──────────────────────────────────┘
                       │ (Vite proxy)
┌──────────────────────v──────────────────────────────────┐
│         Flask Backend (http://127.0.0.1:5000)           │
│  ├─ /api/create-build → POST → ai_api_cli.py            │
│  ├─ /api/add-to-cart → POST → MySQL insert               │
│  ├─ /api/components/search → GET → MySQL query           │
│  ├─ /health → GET → Liveness (no DB)                     │
│  └─ /api/db-health → GET → Database connectivity test    │
└──────────────────────┬──────────────────────────────────┘
                       │ (MySQL connector pool)
┌──────────────────────v──────────────────────────────────┐
│      MySQL Database (genspark_erp)                       │
│  ├─ components (id, name, category, price, ...)          │
│  ├─ pc_builds (id, user_id, cpu_id, gpu_id, ...)         │
│  ├─ cart_items (id, pc_build_id, user_id, ...)           │
│  └─ vendors (id, name, category_id, location, ...)       │
└────────────────────────────────────────────────────────┘
```

---

## Next Steps

1. ✅ Run `START-GENSPARK-DEV.bat` to start backend
2. ✅ Open `http://127.0.0.1:5173` in browser
3. ✅ Run `window.runBackendDiagnostics()` in console to verify connectivity
4. ✅ Click "Add to Cart" on a configured build
5. ✅ Verify build appears in cart
6. ✅ Complete checkout flow with Stripe test card

**Presentation Ready**: Once all checks pass, the full PC builder flow is QA-validated for June 10 demo.

---

*Last Updated: Frontend build + diagnostics tool deployed*
