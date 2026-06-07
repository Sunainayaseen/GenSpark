# GenSpark Backend (Flask + YOLO) — Render / Railway

```
backend/
├── app.py
├── requirements.txt
├── render.yaml          # optional Render blueprint
├── Procfile             # Railway: web: gunicorn app:app
├── runtime.txt
├── best.pt              # trained weights (local; not in git)
├── yolov8n.pt           # optional nano fallback
└── uploads/
```

## STEP 1 — Local setup

```bat
cd backend
py -3.10 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy_weights.bat
```

`copy_weights.bat` copies `vendor dashboard\models\best.pt` → `backend\best.pt`.

Optional nano weights (first run may auto-download):

```bat
.venv\Scripts\python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

## STEP 2 — Run locally

```bat
.venv\Scripts\python app.py
```

Open: http://127.0.0.1:5000/ → `Backend Running`

## STEP 3 — Render deploy

1. New **Web Service** → connect GitHub repo  
2. **Root directory:** `backend` (if monorepo) or use this folder as its own repo  
3. **Build:** `pip install -r requirements.txt`  
4. **Start command:** `gunicorn app:app` (Render: `gunicorn app:app --bind 0.0.0.0:$PORT`)  
5. Upload `best.pt` or set env `YOLO_MODEL_PATH=best.pt`  
6. Add `best.pt` to deploy (Git LFS / manual upload) — file is gitignored by default (~6 MB)

Or use `render.yaml` in this folder.

## STEP 4 — GitHub push

```bat
git add backend
git commit -m "Add Render-ready Flask YOLO backend"
git push origin main
```

## API (GenSpark React)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/` | Backend Running |
| GET | `/health` | OK |
| GET | `/api/detect/model` | Model path + exists |
| POST | `/api/detect/component` | field `image` (file or base64 JSON) |
| POST | `/predict` | field `file` (tutorial format) |

Vercel env: `VITE_API_BASE=https://YOUR-RENDER-URL.onrender.com`
