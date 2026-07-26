# GenSpark YOLO component dataset

## Folder structure (use this — not `train/images`)

```text
GenSpark/dataset/
├── data.yaml
├── images/
│   ├── train/    ← all training photos
│   └── val/      ← validation photos
└── labels/
    ├── train/    ← one .txt per image (same base name)
    └── val/
```

YOLO pairs `images/train/foo.jpg` with `labels/train/foo.txt` automatically.

## Classes (`data.yaml`) — order is fixed for the Flask API

| ID | Name     |
|----|----------|
| 0  | mouse    |
| 1  | keyboard |
| 2  | monitor  |
| 3  | ram      |

Do **not** reorder to `['keyboard', 'mouse', ...]` or detection labels in the app will be wrong.

## Add new keyboard photos

1. Save product shots under Cursor `assets/` (e.g. `Screenshot_2026-05-16_*.png`).
2. Run:

```bash
vendor dashboard\.venv\Scripts\python.exe tools\import_keyboard_assets.py
```

Labels use **class 1** with auto tight boxes (`tools/yolo_bbox_utils.py`) for dark/white backgrounds.

## Add new monitor photos

1. Place product shots (or chat uploads) in Cursor `assets/`.
2. Run:

```bash
vendor dashboard\.venv\Scripts\python.exe tools\import_monitor_assets.py
vendor dashboard\.venv\Scripts\python.exe tools\import_monitor_chat_sample.py
vendor dashboard\.venv\Scripts\python.exe tools\relabel_class_dataset.py monitor
```

Labels use **class 2** with auto tight boxes (`tools/yolo_bbox_utils.py`).  
For wide chat screenshots, `import_monitor_chat_sample.py` adds a center-cropped copy.

Windows one-shot: `tools\train_monitor.bat`

## Train (all classes)

```bash
vendor dashboard\.venv\Scripts\python.exe tools\validate_yolo_dataset.py
vendor dashboard\.venv\Scripts\python.exe tools\train_yolov8.py --epochs 100 --imgsz 640
```

Or on Windows: `tools\train_keyboard.bat` (imports keyboards, validates, trains).

Weights are copied to `vendor dashboard/models/best.pt` for the chatbot `/api/detect/component` endpoint.

## Label format

Each image needs a matching `.txt` under `labels/train` or `labels/val`:

```
2 0.5 0.5 0.95 0.95
```

(class `monitor`, centered box covering ~95% of frame — good for product shots on white background.)

For tighter boxes, use [Roboflow](https://roboflow.com) or `labelImg`, then re-run training.
