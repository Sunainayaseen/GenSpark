"""Import monitor photos into YOLO dataset (class id 2 = monitor)."""

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

MONITOR_CLASS_ID = 2

# Monitor product shots (avoid 14:xx keyboard screenshots)
GLOB_PATTERNS = [
    "*Screenshot_2026-05-16_15*.png",
    "*Screenshot_2026-05-16_16*.png",
    "*Screenshot_2026-05-16_143028*.png",
    "*ChatGPT_Image_May_16*.png",
    "*Gemini_Generated_Image*.png",
    "*removebg*.png",
    "*user_01508*.png",
    "*user_01543*.png",
    "*image-8171*.png",
    "*monitor*.png",
    "*Monitor*.png",
]

# Keyboard batch times — skip if matched only by broad glob
SKIP_SUBSTRINGS = [
    "Screenshot_2026-05-16_135",
    "Screenshot_2026-05-16_140",
    "Screenshot_2026-05-16_141",
    "Screenshot_2026-05-16_142",
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
            name = p.name
            if any(s in name for s in SKIP_SUBSTRINGS):
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(p)
    return found


def next_stem(prefix: str, folder: Path) -> str:
    n = 1
    while (folder / f"{prefix}{n:02d}.png").exists() or (folder / f"{prefix}{n:02d}.jpg").exists():
        n += 1
    return f"{prefix}{n:02d}"


def main() -> None:
    for d in (TRAIN_I, VAL_I, TRAIN_L, VAL_L):
        d.mkdir(parents=True, exist_ok=True)

    sources = discover_sources()
    if not sources:
        print(f"No monitor images found under {SRC}")
        return

    rng = random.Random(42)
    rng.shuffle(sources)
    n_val = max(3, round(len(sources) * 0.22))
    val_set = set(sources[:n_val])

    copied_train = copied_val = skipped = relabeled = 0
    for p in sources:
        stem = next_stem("monitor_user_", TRAIN_I)
        ext = p.suffix.lower() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} else ".png"
        fname = stem + ext
        is_val = p in val_set
        dst_img = (VAL_I if is_val else TRAIN_I) / fname
        dst_lbl = (VAL_L if is_val else TRAIN_L) / (Path(fname).stem + ".txt")

        if dst_img.exists():
            label = yolo_label_line(MONITOR_CLASS_ID, dst_img)
            dst_lbl.write_text(label, encoding="utf-8")
            relabeled += 1
            continue

        shutil.copy2(p, dst_img)
        label = yolo_label_line(MONITOR_CLASS_ID, dst_img)
        dst_lbl.write_text(label, encoding="utf-8")

        if is_val:
            copied_val += 1
        else:
            copied_train += 1

    print(
        f"discovered={len(sources)} new_train={copied_train} new_val={copied_val} "
        f"skipped_copy_relabeled={relabeled}"
    )
    print(f"class_id={MONITOR_CLASS_ID} labels=auto tight bbox")


if __name__ == "__main__":
    main()
