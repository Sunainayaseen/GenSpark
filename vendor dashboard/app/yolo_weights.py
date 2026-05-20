# GenSpark — YOLO weights path (local + Railway)
import os
from pathlib import Path

# vendor dashboard/ (parent of app/)
VENDOR_DASHBOARD_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = VENDOR_DASHBOARD_ROOT / 'models' / 'best.pt'

_yolo_model = None


def resolve_model_path() -> Path:
    """Always prefer vendor dashboard/models/best.pt unless GENSPARK_YOLO_MODEL is set."""
    configured = os.getenv('GENSPARK_YOLO_MODEL', '').strip()
    if configured:
        p = Path(configured)
        if not p.is_absolute():
            p = VENDOR_DASHBOARD_ROOT / p
        return p
    return MODEL_PATH


def get_yolo_model(force_reload: bool = False):
    """Load YOLO once per worker; path is dynamic (no ~/yolov5 hardcoding)."""
    global _yolo_model
    path = resolve_model_path()
    if not path.is_file():
        raise FileNotFoundError(f'Model not found: {path}')
    if force_reload or _yolo_model is None:
        from ultralytics import YOLO

        _yolo_model = YOLO(str(path))
    return _yolo_model, path


def clear_yolo_model_cache():
    global _yolo_model
    _yolo_model = None
