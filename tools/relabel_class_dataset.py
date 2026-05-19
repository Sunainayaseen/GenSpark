"""Re-write YOLO labels for one class using auto tight boxes (class id 0–3)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from yolo_bbox_utils import yolo_label_line  # noqa: E402

ROOT = REPO / "dataset"
CLASS_PREFIX = {
    "mouse": 0,
    "keyboard": 1,
    "monitor": 2,
    "ram": 3,
}


def relabel_split(class_id: int, stem_prefix: str, split: str) -> int:
    img_dir = ROOT / "images" / split
    lbl_dir = ROOT / "labels" / split
    n = 0
    for img in sorted(img_dir.iterdir()):
        if not img.is_file():
            continue
        if not img.stem.lower().startswith(stem_prefix.lower()):
            continue
        lbl = lbl_dir / f"{img.stem}.txt"
        line = yolo_label_line(class_id, img)
        lbl.write_text(line, encoding="utf-8")
        n += 1
    return n


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("component", choices=list(CLASS_PREFIX.keys()))
    args = parser.parse_args()
    class_id = CLASS_PREFIX[args.component]
    prefix = args.component
    total = 0
    for split in ("train", "val"):
        c = relabel_split(class_id, prefix, split)
        print(f"{split}: relabeled {c} {prefix} images")
        total += c
    print(f"done total={total} class_id={class_id}")


if __name__ == "__main__":
    main()
