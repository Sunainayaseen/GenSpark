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
| **Python** | 3.11.x | Backend (Flask). 3.10–3.12 also fine. |
| **Node.js** | 18+ (tested on 24) | Frontend (React/Vite). |
| **MySQL Server** | 8.0+ | Database `genspark_erp`. |
| **MySQL Workbench** | latest | To import the database (optional — CLI works too). |
| OS | Windows 10/11 (or macOS/Linux) | Commands below shown for Windows. |
| Disk | ~5 GB free | The Python venv installs PyTorch (CPU) for YOLO. |

---

## 2. Submission Folder Structure

```
GenSpark-ERP/
├── README.md                ← this file
├── genspark_erp.sql         ← MySQL database dump (import this first)
├── backend/                 ← Flask API + AI (run from here)
│   ├── run.py               ← app entry point
│   ├── config.py            ← reads DB settings from .env
│   ├── requirements.txt     ← Python dependencies
│   ├── .env.example         ← copy to .env and fill in your MySQL credentials
│   ├── chat_intelligence.py ← rule-based chatbot upgrade-evaluator
│   ├── app/                 ← application package (api, models, services, …)
│   ├── models/best.pt       ← trained YOLOv8 weights (do NOT delete)
│   ├── init_db.py           ← creates tables + seed admin (only if NOT importing .sql)
│   └── seed_*.py            ← optional catalog seed scripts
└── frontend/                ← React (Vite) single-page app
    ├── package.json
    ├── vite.config.js       ← dev proxy: /api → http://127.0.0.1:5000
    └── src/
```

> **Note:** `backend/` is the project's Flask app (working folder `Dashboard/`), and
> `frontend/` is the React app (working folder `my-react-app/`). `node_modules/`,
> the Python `.venv/`, caches and build output are **excluded** — they are
> regenerated during setup below.

---

## 3. Database Restoration

The dump `genspark_erp.sql` already contains `CREATE DATABASE genspark_erp` and all
37 tables with data — you do **not** need to create the database manually.

### Option A — MySQL Workbench (GUI)
1. Open **MySQL Workbench** and connect to your local MySQL server.
2. Menu: **Server → Data Import**.
3. Select **"Import from Self-Contained File"** and browse to `genspark_erp.sql`.
4. Leave **Default Target Schema** blank (the file creates `genspark_erp` itself).
5. Click **Start Import**.
6. Refresh the **SCHEMAS** panel — `genspark_erp` should now appear.

### Option B — Command line (faster)
```bat
mysql -u root -p < genspark_erp.sql
```
Enter your MySQL root password when prompted.

---

## 4. Backend Setup (Flask)

```bat
cd backend

REM 1. Create and activate a virtual environment (Python 3.11)
py -3.11 -m venv .venv
.venv\Scripts\activate

REM 2. Install dependencies (Flask + PyTorch CPU; first run downloads a lot)
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
REM   → http://localhost:5173 (proxies /api to the Flask backend on :5000)

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

Run **both** at the same time (two terminals). Use the storefront at `:5173`; it
talks to the API at `:5000` automatically.

---

## 9. Troubleshooting

| Problem | Fix |
|---------|-----|
| `Access denied for user` / DB connection error | Wrong MySQL login in `backend/.env`. Fix `DB_USER` / `DB_PASSWORD`. |
| `Unknown database 'genspark_erp'` | The `.sql` import didn't run — redo **Section 3**. |
| Port 5000 already in use | Close other Flask instances, or change the port in `run.py`. Run only **one** backend. |
| Buttons / modals not responding | Hard-refresh the page (`Ctrl+Shift+R`) to clear cached JS/CSS. |
| `ModuleNotFoundError` on backend | venv not activated, or `pip install -r requirements.txt` didn't finish. |
| `npm run dev` fails | Delete `frontend/node_modules` and re-run `npm install` (Node 18+). |
| Detection says "Unknown" | Use a clear, single-component photo on a plain background; `models/best.pt` must be present. |
| Frontend loads but "Failed to fetch" / no data | Backend isn't running or MySQL is down. Start both; check `:5000/health`. |

---

## 10. Examiner Deployment Checklist

- [ ] Install Python 3.11, Node.js 18+, MySQL Server 8.0, MySQL Workbench.
- [ ] Import `genspark_erp.sql` (Section 3) — confirm the `genspark_erp` schema appears.
- [ ] `backend/` → create venv → `pip install -r requirements.txt`.
- [ ] Copy `backend/.env.example` → `backend/.env`, set MySQL `DB_USER` / `DB_PASSWORD`.
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
- **Rider delivery** — auto-assignment and live tracking.
- **Admin panel** — users, vendors, components, orders, payments, reports.

---

*GenSpark ERP — Final Year Project. Built with Flask, React, MySQL, and YOLOv8.*
