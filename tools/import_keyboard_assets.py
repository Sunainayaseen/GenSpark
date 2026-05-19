"""Import keyboard photos into YOLO dataset (class id 1 = keyboard)."""

from __future__ import annotations

import random
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from yolo_bbox_utils import yolo_label_line  # noqa: E402

SRC = Path(
    r"C:\Users\MMT\.cursor\projects\c-Users-MMT-Desktop-GenSpark\assets"
)
if not SRC.is_dir():
    SRC = REPO / "assets"

ROOT = REPO / "dataset"
TRAIN_I = ROOT / "images" / "train"
VAL_I = ROOT / "images" / "val"
TRAIN_L = ROOT / "labels" / "train"
VAL_L = ROOT / "labels" / "val"

KEYBOARD_CLASS_ID = 1

# May 2026 keyboard batch (cyan-backlit product shots)
GLOB_PATTERNS = [
    "*Screenshot_2026-05-16*.png",
    "*keyboard*.png",
    "*Keyboard*.png",
]


def discover_sources() -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    if not SRC.is_dir():
        return found
    for pattern in GLOB_PATTERNS:
        for p in sorted(SRC.glob(pattern)):
            if not p.is_file():
                continue
            key = p.name.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(p)
    return found


def next_stem(prefix: str, folder: Path) -> str:
    n = 1
    while (folder / f"{prefix}{n}.png").exists() or (folder / f"{prefix}{n}.jpg").exists():
        n += 1
    return f"{prefix}{n}"


def main() -> None:
    for d in (TRAIN_I, VAL_I, TRAIN_L, VAL_L):
        d.mkdir(parents=True, exist_ok=True)

    sources = discover_sources()
    if not sources:
        print(f"No keyboard images found under {SRC}")
        return

    rng = random.Random(42)
    rng.shuffle(sources)
    n_val = max(2, round(len(sources) * 0.2))
    val_set = set(sources[:n_val])

    copied_train = copied_val = skipped = 0
    for p in sources:
        stem = next_stem("keyboard_user_", TRAIN_I)
        ext = p.suffix.lower() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} else ".png"
        fname = stem + ext
        is_val = p in val_set
        dst_img = (VAL_I if is_val else TRAIN_I) / fname
        dst_lbl = (VAL_L if is_val else TRAIN_L) / (Path(fname).stem + ".txt")

        if dst_img.exists():
            skipped += 1
            continue

        shutil.copy2(p, dst_img)
        label = yolo_label_line(KEYBOARD_CLASS_ID, dst_img)
        dst_lbl.write_text(label, encoding="utf-8")

        if is_val:
            copied_val += 1
        else:
            copied_train += 1

    print(f"discovered={len(sources)} copied_train={copied_train} copied_val={copied_val} skipped={skipped}")
    print(f"labels use class_id={KEYBOARD_CLASS_ID} (keyboard) with auto tight bounding boxes")


if __name__ == "__main__":
    main()
