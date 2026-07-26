"""Add chat-style monitor uploads (wide screenshots) + center crop for tighter labels."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from yolo_bbox_utils import yolo_label_line  # noqa: E402

ASSETS = Path(
    r"C:\Users\MMT\.cursor\projects\c-Users-MMT-Desktop-GenSpark\assets"
)
TRAIN_I = REPO / "dataset" / "images" / "train"
TRAIN_L = REPO / "dataset" / "labels" / "train"
CLASS_ID = 2

EXTRA_GLOBS = ["*image-8171*.png"]


def center_crop_wide(path: Path, out: Path, width_frac: float = 0.72) -> None:
    from PIL import Image

    with Image.open(path) as im:
        w, h = im.size
        if w / max(h, 1) < 1.35:
            shutil.copy2(path, out)
            return
        cw = int(w * width_frac)
        x1 = (w - cw) // 2
        cropped = im.crop((x1, 0, x1 + cw, h))
        cropped.save(out)


def main() -> None:
    TRAIN_I.mkdir(parents=True, exist_ok=True)
    TRAIN_L.mkdir(parents=True, exist_ok=True)

    sources: list[Path] = []
    for g in EXTRA_GLOBS:
        sources.extend(ASSETS.glob(g))

    for src in sources:
        if not src.is_file():
            continue
        full = TRAIN_I / "monitor_chat_full.png"
        crop = TRAIN_I / "monitor_chat_crop.png"
        shutil.copy2(src, full)
        center_crop_wide(src, crop)
        for img, stem in ((full, "monitor_chat_full"), (crop, "monitor_chat_crop")):
            lbl = TRAIN_L / f"{stem}.txt"
            lbl.write_text(yolo_label_line(CLASS_ID, img), encoding="utf-8")
        print(f"added {src.name} -> monitor_chat_full + monitor_chat_crop")


if __name__ == "__main__":
    main()
