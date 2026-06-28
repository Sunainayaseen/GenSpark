"""Verify YOLO dataset paths and image/label pairs before training."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
DATA_YAML = REPO / "dataset" / "data.yaml"
EXPECTED_NAMES = ["mouse", "keyboard", "monitor", "ram"]


def main() -> None:
    if not DATA_YAML.is_file():
        raise SystemExit(f"Missing {DATA_YAML}")

    cfg = yaml.safe_load(DATA_YAML.read_text(encoding="utf-8"))
    root = Path(cfg["path"]).resolve()
    train_img = root / cfg["train"]
    val_img = root / cfg["val"]
    train_lbl = root / "labels" / "train"
    val_lbl = root / "labels" / "val"

    names = cfg.get("names")
    if isinstance(names, dict):
        ordered = [names[i] for i in range(len(names))]
    else:
        ordered = list(names)
    if ordered != EXPECTED_NAMES:
        raise SystemExit(
            f"Class order must be {EXPECTED_NAMES} (matches Flask API). Got: {ordered}"
        )

    print(f"dataset root: {root}")
    print(f"train images: {train_img} ({'OK' if train_img.is_dir() else 'MISSING'})")
    print(f"val images:   {val_img} ({'OK' if val_img.is_dir() else 'MISSING'})")
    print(f"train labels: {train_lbl} ({'OK' if train_lbl.is_dir() else 'MISSING'})")
    print(f"val labels:   {val_lbl} ({'OK' if val_lbl.is_dir() else 'MISSING'})")

    for split, img_dir, lbl_dir in (
        ("train", train_img, train_lbl),
        ("val", val_img, val_lbl),
    ):
        imgs = {p.stem for p in img_dir.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}}
        lbls = {p.stem for p in lbl_dir.glob("*.txt")}
        missing_lbl = imgs - lbls
        missing_img = lbls - imgs
        print(f"\n[{split}] images={len(imgs)} labels={len(lbls)}")
        if missing_lbl:
            print(f"  WARNING: {len(missing_lbl)} images without labels (e.g. {list(missing_lbl)[:3]})")
        if missing_img:
            print(f"  WARNING: {len(missing_img)} labels without images")
        if not imgs:
            raise SystemExit(f"No images in {img_dir}")

    print("\nDataset OK for YOLOv8 training.")


if __name__ == "__main__":
    main()
