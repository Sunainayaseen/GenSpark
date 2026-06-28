"""
Train YOLOv8 on dataset/data.yaml and deploy weights to vendor dashboard/models/best.pt.

Usage (from repo root):
  python tools/import_monitor_assets.py
  python tools/train_yolov8.py
  python tools/train_yolov8.py --epochs 80 --imgsz 640
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA_YAML = REPO / "dataset" / "data.yaml"
DEPLOY_WEIGHTS = REPO / "vendor dashboard" / "models" / "best.pt"
RUNS_DIR = REPO / "runs" / "detect"


def main() -> None:
    parser = argparse.ArgumentParser(description="Train GenSpark component detector (YOLOv8)")
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Train image size")
    parser.add_argument("--batch", type=int, default=8, help="Batch size (-1 = auto)")
    parser.add_argument("--base", default="yolov8n.pt", help="Base checkpoint")
    parser.add_argument("--name", default="genspark_components", help="Run name under runs/detect")
    parser.add_argument("--no-deploy", action="store_true", help="Skip copy to vendor dashboard/models")
    args = parser.parse_args()

    if not DATA_YAML.is_file():
        raise SystemExit(f"Missing dataset config: {DATA_YAML}")

    import subprocess
    import sys

    print("Validating dataset...")
    subprocess.run([sys.executable, str(REPO / "tools" / "validate_yolo_dataset.py")], check=True)

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit(
            "Install ultralytics: pip install ultralytics>=8.3.0\n"
            f"({exc})"
        ) from exc

    # Fine-tune from existing GenSpark weights when present
    base = DEPLOY_WEIGHTS if DEPLOY_WEIGHTS.is_file() else REPO / args.base
    if not Path(base).exists() and args.base == "yolov8n.pt":
        base = args.base

    print(f"Training with base={base}")
    print(f"data={DATA_YAML}")
    model = YOLO(str(base))
    results = model.train(
        data=str(DATA_YAML),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project=str(RUNS_DIR),
        name=args.name,
        exist_ok=True,
        patience=25,
        save=True,
        plots=True,
        val=True,
        # Augmentation — better generalization for FYP demo photos
        hsv_h=0.015,
        hsv_s=0.6,
        hsv_v=0.4,
        degrees=12.0,
        translate=0.08,
        scale=0.45,
        fliplr=0.5,
        mosaic=0.8,
        mixup=0.05,
        copy_paste=0.0,
        close_mosaic=10,
    )

    best = Path(results.save_dir) / "weights" / "best.pt"
    if not best.is_file():
        candidates = sorted(RUNS_DIR.rglob("weights/best.pt"), key=lambda p: p.stat().st_mtime)
        best = candidates[-1] if candidates else best

    if not best.is_file():
        raise SystemExit("Training finished but best.pt was not found.")

    print(f"Best weights: {best}")
    if not args.no_deploy:
        DEPLOY_WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best, DEPLOY_WEIGHTS)
        print(f"Deployed to: {DEPLOY_WEIGHTS}")
        print("Restart Flask (python run.py) so /api/detect/component picks up the new model.")


if __name__ == "__main__":
    main()
