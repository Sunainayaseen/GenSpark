# GenSpark YOLO Backend (Railway)

Minimal Flask API for **React (Vercel) → Flask (Railway) → YOLOv8**.

```
my-react-app (Vercel)
      ↓  VITE_API_BASE / proxy
Flask API (this folder on Railway)
      ↓
best.pt
```

## Folder layout

```
backend/
├── app.py
├── best.pt          ← place trained weights here (not committed)
├── requirements.txt
├── Procfile
├── runtime.txt
└── README.md
```

## Local setup

1. Copy weights after training:

   ```bat
   copy "vendor dashboard\models\best.pt" backend\best.pt
   ```

   Or run `tools\train_yolov8.py` (deploys to `vendor dashboard\models\best.pt`) then copy.

2. Create venv and install:

   ```bat
   cd backend
   py -3.10 -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```

3. Run:

   ```bat
   .venv\Scripts\python app.py
   ```

   - Health: http://127.0.0.1:5000/health  
   - Tutorial predict: `POST /predict` (field `file`)  
   - React chatbot: `POST /api/detect/component` (field `image`)

4. Point the React app at local Flask (`flaskBase.js` already uses `http://127.0.0.1:5000` on localhost).

## Deploy to Railway

**No `railway.json` needed** — Railway uses only:

`app.py` · `requirements.txt` · `Procfile` · `runtime.txt` · `best.pt`

1. Push repo to GitHub.
2. Railway service → **Root directory**: `backend`
3. Upload `best.pt` (volume or deploy artifact).
4. **Redeploy** from Deployments tab after each push.
5. Vercel: `VITE_API_BASE=https://YOUR-SERVICE.up.railway.app`

### Live production (full API)

**https://genspark-production.up.railway.app** uses **`vendor dashboard/`** (auth, DB, orders + YOLO).  
Set Railway root directory to `vendor dashboard` in the dashboard — not `backend`.

| Root directory | Use case |
|----------------|----------|
| `vendor dashboard` | **Current live** GenSpark API |
| `backend` | YOLO-only microservice (tutorial layout) |

## GitHub push (first time)

```bat
git add backend
git commit -m "Add Railway YOLO Flask backend"
git push -u origin main
```

## Procfile

Must be named exactly `Procfile` (no `.txt`):

```
web: gunicorn app:app
```

## API reference

### `POST /predict`

Tutorial format. Body: `multipart/form-data`, field **`file`**.

```json
{
  "detections": [
    { "class": "keyboard", "confidence": 0.87 }
  ]
}
```

### `POST /api/detect/component`

GenSpark React format. Body: field **`image`**, optional **`conf`** (0.1–0.95).

Returns bounding boxes, class names, and overlay data for `ImageDetectOverlay`.

### `GET /health`

Plain `OK` for Railway health checks.
