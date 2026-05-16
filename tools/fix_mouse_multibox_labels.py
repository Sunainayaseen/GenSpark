"""Overwrite YOLO labels for imported mouse images that need multi-instance / tighter boxes."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS_TRAIN = ROOT / "dataset" / "labels" / "train"
LABELS_VAL = ROOT / "dataset" / "labels" / "val"

# class 0 = mouse; lines: class xc yc w h (YOLO normalized)

LABELS: dict[str, list[str]] = {
    # Wired vs wireless comparison — two mice
    "mouse_user_images-1ff1ece6-f3c9-4011-9779-7f3763a86c80": [
        "0 0.228 0.503 0.358 0.701",
        "0 0.766 0.503 0.391 0.823",
    ],
    # "Types of Mouse" — eight pointing-device mice (skip stylus + touchpad)
    "mouse_user_-5654e834-ce4b-4187-9846-323d3b39ad69": [
        "0 0.346 0.211 0.088 0.220",
        "0 0.648 0.186 0.094 0.195",
        "0 0.502 0.217 0.160 0.182",
        "0 0.794 0.333 0.091 0.176",
        "0 0.208 0.645 0.101 0.170",
        "0 0.807 0.638 0.104 0.245",
        "0 0.671 0.786 0.091 0.226",
        "0 0.494 0.802 0.107 0.182",
    ],
    # 2×4 collage — uniform tight grid (exclude watermark band at bottom)
    "mouse_user_-05930365-40b4-4562-b960-61bf9162cd6e": [
        "0 0.135 0.300 0.210 0.380",
        "0 0.375 0.300 0.210 0.380",
        "0 0.625 0.300 0.210 0.380",
        "0 0.865 0.300 0.210 0.380",
        "0 0.135 0.705 0.210 0.380",
        "0 0.375 0.705 0.210 0.380",
        "0 0.625 0.705 0.210 0.380",
        "0 0.865 0.705 0.210 0.380",
    ],
    # UGREEN mouse + dongle — box mouse body only
    "mouse_user_-0649056f-6307-46bb-a23a-ee14ce695b2c": [
        "0 0.550 0.480 0.860 0.900",
    ],
    # Wireless mouse + dongle (val) — mouse only
    "mouse_user_-7d29679f-06ab-496d-95b3-ba02d23d91ee": [
        "0 0.440 0.485 0.720 0.780",
    ],
    # Side-profile G mouse — tighter than full frame
    "mouse_user_-1d5585a7-390b-4da1-ac3d-deab9a461146": [
        "0 0.515 0.505 0.820 0.820",
    ],
}


def main() -> None:
    updated = 0
    for stem, lines in LABELS.items():
        text = "\n".join(lines) + "\n"
        for folder in (LABELS_TRAIN, LABELS_VAL):
            p = folder / f"{stem}.txt"
            if p.is_file():
                p.write_text(text, encoding="utf-8")
                print("wrote", p.relative_to(ROOT))
                updated += 1
    print(f"done, label files touched: {updated}")


if __name__ == "__main__":
    main()
