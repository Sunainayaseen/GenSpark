# GenSpark — PC Recommendation & Ordering System

GenSpark is a full-stack web application that helps users build and buy a custom PC.
A **rule-based chatbot** collects the user's budget and purpose, a **recommendation
engine** builds a balanced parts list from a live catalog, a **compatibility checker**
validates the configuration, and a multi-vendor **ordering system** (cart, checkout,
rider delivery tracking) fulfils the purchase.

> The system is fully **rule-based** — no external LLM/AI APIs are used for the
> recommendation or chatbot logic. All decisions come from deterministic Python rules
> over a MySQL component catalog.

---

## Architecture

The project is cleanly separated into two independent applications that communicate
over HTTP (the React frontend calls the Flask JSON API via `fetch`).

```
GenSpark/
├── backend/                     # Flask REST API (Python) — server-side
│   ├── run.py                   # WSGI entry point  →  gunicorn run:app
│   ├── config.py                # environment / DB configuration
│   ├── requirements.txt         # backend Python dependencies
│   ├── chat_intelligence.py     # rule-based upgrade/compatibility intent engine
│   ├── init_db.py               # create tables + seed an admin user
│   ├── seed_*.py                # catalog / vendor / rider data seeders  (the "data" layer)
│   └── app/
│       ├── __init__.py          # application factory (create_app) + blueprint wiring
│       ├── api/                 # ── ROUTES ──  HTTP endpoints (controllers)
│       │   ├── ai_build_routes.py   # chatbot + recommend-build endpoints
│       │   ├── routes.py            # catalog, cart, orders, users
│       │   ├── stripe_checkout.py   # payment endpoints (server-verified pricing)
│       │   └── tracking_routes.py   # live rider tracking
│       ├── auth/                # ── ROUTES ──  login / register / sessions
│       ├── services/            # ── LOGIC ──  business rules
│       │   ├── build_intelligence.py  # rule-based chatbot + recommendation engine
│       │   ├── compatibility.py       # RAM / storage compatibility checking
│       │   ├── hardware_specs.py      # component spec classification
│       │   └── customization.py       # upgrade / swap suggestions
│       ├── models/              # ── MODELS ──  SQLAlchemy ORM (users, components, orders…)
│       ├── admin/ vendor/ rider/ ecommerce/   # role-specific blueprints
│       ├── templates/ static/   # server-rendered admin/vendor dashboards
│       └── utils/               # shared helpers
│
├── frontend/                    # React + Vite single-page app — client-side
│   ├── index.html
│   ├── vite.config.js           # dev proxy: /api, /uploads, /socket.io → :5000
│   ├── package.json
│   └── src/
│       ├── pages/               # Landing, Chatbot, BuildConfigurator, Cart, Checkout, TrackOrder…
│       ├── components/          # Layout, header, shared UI
│       ├── context/             # CartContext, AuthContext (global state)
│       └── utils/               # api.js (fetch wrapper), chatIntentParse.js, buildResolver.js
│
├── ml/                          # YOLOv8 component-detection (training + camera demo, optional)
├── docs/                        # architecture, testing and design guides
├── Procfile / Dockerfile        # deployment (backend WSGI)
└── README.md
```

### How this maps to the classic `routes / logic / models / data` layout

| Requested concept            | In this project                                              |
|------------------------------|--------------------------------------------------------------|
| `routes/` (chatbot, orders…) | `backend/app/api/` + `backend/app/auth/` (Flask blueprints)  |
| `logic/` (engine, rules)     | `backend/app/services/` + `backend/chat_intelligence.py`     |
| `models/`                    | `backend/app/models/` (SQLAlchemy)                           |
| `data/`                      | `backend/seed_*.py` seeders + the MySQL `genspark_erp` schema|

The blueprint layout is the production-grade Flask equivalent of the flat
`routes/logic/models` sketch and keeps role concerns (admin, vendor, rider, ecommerce)
properly isolated.

---

## Tech stack

- **Backend:** Python, Flask, SQLAlchemy, Flask-Login, Flask-SocketIO, MySQL (`genspark_erp`)
- **Frontend:** React 18, Vite, React Router, Context API
- **Payments:** Stripe (server-side price verification)
- **Detection (optional):** YOLOv8 / OpenCV for component recognition

---

## Getting started

### 1. Backend (Flask API → http://127.0.0.1:5000)

```bash
cd backend
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# Configure MySQL + secrets in a .env file (see config.py for keys):
#   DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME=genspark_erp, USE_SQLITE=0
#   STRIPE_SECRET_KEY=...   (optional, for online payments)

python init_db.py            # create tables + admin user
python seed_vendors_components.py
python seed_prebuilt_parts.py
python seed_build_components.py

python run.py                # starts the API on :5000
```

### 2. Frontend (React UI → http://localhost:5173)

```bash
cd frontend
npm install
npm run dev                  # Vite dev server; /api is proxied to :5000
```

Then open **http://localhost:5173** — or use the one-click dev launcher
**`START-GENSPARK-DASHBOARD-DEV.bat`** (Windows) which starts both servers.

---

## Chatbot logic (rule-based)

The assistant is a deterministic rule engine — no AI APIs:

1. **Intent detection** — parses the message for *budget* (`150k`, `1.5 lakh`,
   `150000`) and *purpose* (gaming / office / editing / coding). Greetings and
   model numbers (e.g. "RTX 4070") are recognised so they are **not** mistaken for a
   budget. *(`frontend/src/utils/chatIntentParse.js`, `backend/app/api/ai_build_routes.py`)*
2. **Recommendation flow** — picks a balanced CPU/GPU/RAM/storage/PSU/case set from
   the live catalog, fills the budget without overspending.
   *(`backend/app/services/build_intelligence.py`)*
3. **Compatibility checking** — validates RAM and storage against the chosen
   platform and flags incompatible configurations.
   *(`backend/app/services/compatibility.py`)*
4. **Upgrade suggestions** — when a user asks "will X fit / is X compatible", the
   rule engine returns an upgrade/compatibility verdict.
   *(`backend/chat_intelligence.py`)*

---

## Deployment

`Procfile` and `Dockerfile` run the backend WSGI app
(`gunicorn --chdir backend run:app`). Build the frontend with `npm run build` in
`frontend/` and host the static output separately (e.g. Vercel/Netlify), pointing it
at the backend API URL.
