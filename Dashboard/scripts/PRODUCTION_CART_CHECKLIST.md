# Production cart (Vercel + Railway) — diagnostic checklist

## Symptom
Add to cart works on localhost but live site shows an empty cart after login.

## Two cart systems in MySQL

| Tables | Used by | API |
|--------|---------|-----|
| `cart`, `cart_items` | PC builder (Components, Prebuilt, header cart) | `/api/cart`, `/api/add-to-cart` |
| `ecom_carts`, `ecom_cart_items` | E-commerce shop (`/ecom/cart`) | `/api/ecom/cart` |

Migrate **both** if you use both UIs. Main storefront cart is usually `cart` + `cart_items`.

## Root cause (configuration, not cart logic)
- Cart API uses **Flask session** (`session['cart_id']`) and **Flask-Login** (`current_user`).
- Frontend on `*.vercel.app` calls API on `*.railway.app` (cross-site).
- React sends **JWT** in `Authorization` but cart routes did not activate Flask-Login from JWT until the bridge was added.
- Session cookies need **`SameSite=None; Secure`** in production.

## 1. Database — reset AUTO_INCREMENT (after migration)

Run on Railway MySQL:

```bash
mysql -h HOST -P PORT -u root -p railway < scripts/fix_cart_auto_increment.sql
```

Or in Railway MySQL console, run the contents of `scripts/fix_cart_auto_increment.sql`.

Also ensure **`vendor_components`** rows exist on Railway (add-to-cart needs approved vendor stock).

## 2. Railway backend variables

| Variable | Example |
|----------|---------|
| `FLASK_ENV` | `production` |
| `SECRET_KEY` | long random string (stable across deploys) |
| `FRONTEND_URL` | `https://genspark-frontend.vercel.app` |
| `GENSPARK_CORS_ORIGINS` | optional Vercel preview URLs, comma-separated |
| MySQL vars | `MYSQLHOST`, `MYSQLPASSWORD`, etc. |

Redeploy backend after changing env vars.

## 3. Vercel frontend

| Variable | Value |
|----------|--------|
| `VITE_API_BASE` | `https://genspark-production.up.railway.app` |

Redeploy frontend after env change.

## 4. Browser verification (logged-in user)

1. DevTools → Application → Local Storage: `genspark_token` and `genspark_user` present after login.
2. DevTools → Network → `POST /api/add-to-cart`: request has `Authorization: Bearer …` and `credentials: include`.
3. Response `200` with `"success": true` and non-empty `cart.items` (if vendor stock exists).
4. `GET /api/cart` returns the same items.

## 5. Guest cart note

Guest carts rely on the **session cookie** from Railway. Some mobile browsers block third-party cookies; **sign in** for a reliable cart on production.
