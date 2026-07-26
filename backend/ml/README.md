# GenSpark AI Model — Component Detection (YOLOv8)

Trained YOLOv8 model that identifies PC components (CPU, GPU, RAM, motherboard,
PSU, case, cooler, storage, monitor, keyboard, mouse) from a photo. Used by the
backend's `/api/detect/component` endpoint (chatbot "Detect components from
image" feature). The live weights the running app loads are at
`backend/models/best.pt`; everything here is the training/dev side.

## Contents

- `detect.py` — standalone live webcam detection script (Windows DirectShow
  capture). Run: `python detect.py` (defaults to `../models/best.pt`).
- `START-CAMERA-DETECTION.bat` — Windows launcher for `detect.py`.
- `dataset/` — YOLO-format training images + labels (`data.yaml` describes the
  class list and splits).
- `tools/` — one-off dataset prep/import/relabel scripts used while building
  the dataset (not needed to just run detection).
- `tools/train_yolov8.py` — retrains the model and deploys the result to
  `backend/models/best.pt`.
- `GENSPARK_TRAIN_COLAB.ipynb` — Google Colab notebook for GPU-accelerated
  training (used instead of local CPU training).

## Retraining

```bash
cd backend/ml
python tools/validate_yolo_dataset.py   # sanity-check dataset/data.yaml first
python tools/train_yolov8.py --epochs 100 --imgsz 640
```

This deploys the new weights automatically; restart the Flask backend
afterward so `/api/detect/component` picks up the change.
