# GenSpark deploy checklist (Railway + Vercel)

## STEP 6 — Test model API

Browser:

```
https://genspark-production.up.railway.app/api/detect/model
```

**Expected:**

```json
{
  "success": true,
  "exists": true,
  "model": ".../models/best.pt"
}
```

**If `"exists": false`:** `models/best.pt` is not on the server.

---

## STEP 7–8 — `best.pt` must be in the repo

| Location | Local (you) | GitHub / Railway |
|----------|-------------|------------------|
| Live API | `vendor dashboard/models/best.pt` | Must be committed |
| YOLO-only | `backend/best.pt` | Copy via `backend\copy_weights.bat` (gitignored — use volume or force-add) |

```bat
dir "vendor dashboard\models"
dir backend
```

`best.pt` ~6 MB — OK for GitHub if tracked as `vendor dashboard/models/best.pt`.

---

## Railway (production API)

1. **Root directory:** `vendor dashboard` (not `backend` for full app).
2. **Remove bad env** (if set): delete `GENSPARK_YOLO_MODEL` pointing to `/root/yolov5/...`.
3. **Optional:** `GENSPARK_YOLO_MODEL=models/best.pt`
4. **Deployments → Redeploy** after push.
5. **View logs** on start: `(GenSpark) YOLO weights: ... exists=True`

---

## Vercel (STEP 9)

**Settings → Environment Variables**

```
VITE_API_BASE=https://genspark-production.up.railway.app
```

Then **Redeploy** Vercel.

(`vercel.json` already proxies `/api` to Railway if env is unset.)

---

## STEP 10 — Detection flow

React calls `POST /api/detect/component` (field `image`) — no frontend change needed when API is live.

---

## If deploy fails — log errors

| Error | Meaning |
|-------|---------|
| torch install failed | RAM / build — pinned `torch==2.2.2` in requirements |
| best.pt missing | Commit `vendor dashboard/models/best.pt` + redeploy |
| ModuleNotFoundError | `pip install -r requirements.txt` issue |
| worker timeout | Model too large — use **yolov8n** |
| port bind error | Wrong Procfile — live uses `run:app` |

Send only **red** error lines from Deployments → View Logs.
