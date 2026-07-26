# GenSpark ERP — PC Builder, Marketplace & AI Assistant

GenSpark ERP is a full-stack PC-commerce platform: a **Flask + MySQL** backend and a
**React (Vite)** frontend. It features a **rule-based AI chatbot** that recommends
budget- and compatibility-validated PC builds, **YOLOv8 image-based component
detection**, a multi-vendor marketplace, rider delivery tracking, and an admin panel.

> **Final Year Project submission package.** This README is the single source of
> truth for running the project on a fresh machine.

---

## 1. System Requirements

| Software | Version | Notes |
|----------|---------|-------|
| **Python** | 3.11.x | Main backend (Flask). 3.10–3.12 also fine. |
| **Node.js** | 18+ (tested on 24) | Frontend (React/Vite). |
| **MySQL Server** | 8.0+ | Database `genspark_erp`. |
| **MySQL Workbench** | latest | To import the database (optional — CLI works too). |
| OS | Windows 10/11 (or macOS/Linux) | Commands below shown for Windows. |
| Disk | ~5 GB free | `backend/requirements.txt` installs PyTorch (CPU) for YOLO detection. |

---

## 2. Submission Folder Structure

```
GenSpark/
├── README.md                ← this file
├── LICENSE
├── docs/                     ← project documentation (guides, API reference, use-case diagram)
├── database/                 ← schema.sql + sample_data.sql (see Section 3)
├── backend/                  ← the Flask app — run this for the full demo
│   ├── run.py                 ← entry point (python run.py → :5000)
│   ├── config.py              ← reads DB settings from .env
│   ├── requirements.txt
│   ├── .env.example           ← copy to .env and fill in your MySQL credentials
│   ├── app/                   ← admin/vendor/rider/api blueprints, models, services
│   │   └── services/chat_intelligence.py  ← rule-based upgrade-evaluator
│   ├── models/best.pt         ← trained YOLOv8 weights used by backend's /api/detect
│   └── ml/                    ← YOLOv8 training pipeline + standalone detection script
└── frontend/                 ← React (Vite) single-page app
    ├── package.json
    ├── vite.config.js        ← dev proxy: /api → http://127.0.0.1:5000
    └── src/
```

> **`backend/` is the only backend.** It has the MySQL-backed ERP (orders,
> multi-vendor split, rider dispatch, admin/vendor/rider panels) and its own
> DB-driven `/api/recommend-build` and `/api/detect` endpoints — a rule-based
> AI engine and YOLOv8 detection, both self-contained.
> `node_modules/`, `.venv/`, caches and build output are excluded from this
> submission — they regenerate during setup below.

---

## 3. Database Restoration

See `database/README.md` for full details. Quick version:

```sql
CREATE DATABASE genspark_erp;
```

```bat
mysql -u root -p genspark_erp < database/schema.sql
mysql -u root -p genspark_erp < database/sample_data.sql
```

Then seed a working default admin/vendor login (Section 7) with fresh password
hashes — not shipped statically in this repo:

```bat
cd backend
python init_db.py
```

---

## 4. Backend Setup — `backend/`

```bat
cd backend

REM 1. Create and activate a virtual environment (Python 3.11)
py -3.11 -m venv .venv
.venv\Scripts\activate

REM 2. Install dependencies
pip install -r requirements.txt

REM 3. Configure database credentials
copy .env.example .env
REM   → open .env and set DB_USER / DB_PASSWORD to YOUR MySQL login (see Section 6)

REM 4. Run the backend (API on http://127.0.0.1:5000)
python run.py
```

The first request that uses the image/camera detector loads the YOLO model
(`models/best.pt`) — about 15 seconds once, then it is cached.

---

## 5. Frontend Setup (React + Vite)

Open a **second terminal**:

```bat
cd frontend

REM 1. Install dependencies
npm install

REM 2a. Development mode (hot reload) — recommended for the demo
npm run dev
REM   → http://localhost:5173 (proxies /api to backend on :5000)

REM 2b. OR production build
npm run build
npm run preview
```

Open **http://localhost:5173** in your browser.

---

## 6. Database Credentials (where to update)

All DB settings are read from **`backend/.env`** (loaded by `backend/config.py`).
After copying `.env.example` → `.env`, set these to match your MySQL server:

```ini
# backend/.env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root              # ← your MySQL username
DB_PASSWORD=your_password # ← your MySQL password
DB_NAME=genspark_erp
USE_SQLITE=0              # keep 0 to use MySQL
```

- `backend/config.py` builds the SQLAlchemy connection string from these values —
  **no code change is needed**, only the `.env` file.
- A connection error almost always means the `.env` credentials are wrong.

---

## 7. Demo Login Accounts

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@genspark.com` | `admin123` |
| Vendor | `vendor.isb@genspark.com` | `vendor123` |
| Rider | `rider@genspark.com` | `rider123` |

(Customers can also self-register from the storefront.)

---

## 8. Running the Application (quick reference)

| Component | Command (from its folder) | URL |
|-----------|---------------------------|-----|
| Backend (Flask API) | `python run.py` | http://127.0.0.1:5000 |
| Frontend (React) | `npm run dev` | http://localhost:5173 |
| Health check | — | http://127.0.0.1:5000/health → `OK` |

Run **both** at the same time (two terminals: `backend/` then `frontend/`).
Use the storefront at `:5173`; it talks to the API at `:5000` automatically.

---

## 9. Troubleshooting

| Problem | Fix |
|---------|-----|
| `Access denied for user` / DB connection error | Wrong MySQL login in `backend/.env`. Fix `DB_USER` / `DB_PASSWORD`. |
| `Unknown database 'genspark_erp'` | The `.sql` import didn't run — redo **Section 3**. |
| Port 5000 already in use | Close other Flask instances, or change `PORT` in the `.env`. Run only **one** service on :5000 at a time. |
| Buttons / modals not responding | Hard-refresh the page (`Ctrl+Shift+R`) to clear cached JS/CSS. |
| `ModuleNotFoundError` on backend | venv not activated, or `pip install -r requirements.txt` didn't finish. |
| `npm run dev` fails | Delete `frontend/node_modules` and re-run `npm install` (Node 18+). |
| Detection says "Unknown" | Use a clear, single-component photo on a plain background; `backend/models/best.pt` must be present. |
| Frontend loads but "Failed to fetch" / no data | `backend/` isn't running or MySQL is down. Start it; check `:5000/health`. |

---

## 10. Examiner Deployment Checklist

- [ ] Install Python 3.11, Node.js 18+, MySQL Server 8.0, MySQL Workbench.
- [ ] Import `database/schema.sql` + `database/sample_data.sql` (Section 3) — confirm the `genspark_erp` schema appears.
- [ ] `backend/` → create venv → `pip install -r requirements.txt`.
- [ ] Copy `backend/.env.example` → `backend/.env`, set MySQL `DB_USER` / `DB_PASSWORD`.
- [ ] Run `python init_db.py` once to seed roles + demo admin/vendor accounts.
- [ ] Run `python run.py` → open `http://127.0.0.1:5000/health` → shows `OK`.
- [ ] `frontend/` → `npm install` → `npm run dev`.
- [ ] Open `http://localhost:5173` → storefront loads.
- [ ] Log in as Admin (`admin@genspark.com` / `admin123`).
- [ ] AI Assistant: type "Gaming PC 120000" → a build with 100% compatibility appears.
- [ ] AI Assistant: "Detect components from image" → upload a part photo → it is identified.

---

## 11. Key Features (for the demo)

- **AI Build Assistant** — rule-based chatbot: budget + purpose → compatibility-validated build, with performance (FPS) and running-cost estimates, bottleneck analysis, and multi-turn refinement ("make it cheaper" / "stronger").
- **AI Component Detection** — YOLOv8 detects PC parts (CPU, GPU, RAM, motherboard, PSU, cooler, storage) from an uploaded image or live camera and links them to in-stock catalog products.
- **Multi-vendor marketplace** — per-line-item vendor orders, completion-proof images, admin approval.
- **Rider delivery** — auto-assignment (rating/distance/workload scoring) with a manual override/reassign option, plus live tracking.
- **Admin panel** — users, vendors, components, orders, payments, reports.

---

*GenSpark ERP — Final Year Project. Built with Flask, React, MySQL, and YOLOv8.*
