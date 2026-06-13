"""Copy user-provided mouse images into YOLO dataset with full-image bbox labels."""

from __future__ import annotations

import random
import shutil
from pathlib import Path

SRC = Path(r"C:\Users\MMT\.cursor\projects\c-Users-MMT-Desktop-GenSpark\assets")
ROOT = Path(r"C:\Users\MMT\Desktop\GenSpark\dataset")
TRAIN_I = ROOT / "images" / "train"
VAL_I = ROOT / "images" / "val"
TRAIN_L = ROOT / "labels" / "train"
VAL_L = ROOT / "labels" / "val"

WANTED = [
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__55_-42aa3990-cf30-4b33-ac2f-99b783e876f6.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__41_-973ff3f7-0c2c-4a21-8a3c-a6644b80727b.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__40_-470f3a77-b336-4f49-b7a9-07d2c13d654d.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__38_-d8fef995-e01a-4b39-ad65-bccc28e4a99d.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__37_-79ffc857-150c-4095-8d2d-9b6d841160b9.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__39_-b4ee651d-6f46-4123-9428-72ab8296f291.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__46_-2ba96758-1e7f-4aa7-9e0d-e6fdf52c40b6.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__47_-069c8edb-7425-4f3b-b6bd-12c63009def8.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__49_-26b3bdaa-f606-46dc-9af0-d4c0657849c7.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__50_-3134f2ef-7646-4a57-b2c8-860a0037667b.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__52_-f95a1c51-9a5e-47ae-bc3d-b79b12f3c1cf.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__44_-a6e6a5c7-6650-4826-b271-129b0ce4f8e5.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__51_-ea131d11-904a-4b74-b710-4bf43956b25a.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__42_-039b9437-4bf9-4b8b-b4cb-a61981ad2890.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__43_-10decbf1-38d1-4f15-80ea-f683537475f1.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__45_-715e60a3-b427-482e-9949-d69e2e5f0a21.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__48_-8b79cd3b-bcd2-4a2c-a903-62377e3c5a7b.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__54_-78e432dd-9ae5-48ac-b513-615eccc329d0.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__53_-14c9dbea-ce42-4f61-a27c-2330a1da9640.png",
    # Batch 2 (user 2026-05-15)
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__1_-3ee679f2-277c-4544-83c5-c33e971d2dc2.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__2_-0649056f-6307-46bb-a23a-ee14ce695b2c.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__3_-7d29679f-06ab-496d-95b3-ba02d23d91ee.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_download__4_-0825f33b-692e-4f44-bd9f-e1b38f18e792.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_images__3_-f0f379a5-a191-4feb-a8e4-ca5152c747ec.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_images__4_-cbefbc53-5228-42d9-8ed3-ebb182be81f3.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_images-1ff1ece6-f3c9-4011-9779-7f3763a86c80.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_images__29_-1d5585a7-390b-4da1-ac3d-deab9a461146.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_images__28_-5654e834-ce4b-4187-9846-323d3b39ad69.png",
    "c__Users_MMT_AppData_Roaming_Cursor_User_workspaceStorage_a9ed9d354da8ce79d4ccd745b607be78_images_images__27_-05930365-40b4-4562-b960-61bf9162cd6e.png",
]

LABEL_MOUSE_FULLIMAGE = "0 0.5 0.5 1 1\n"


def slug(p: Path) -> str:
    stem = p.stem
    parts = stem.split("_")
    tail = parts[-1]
    if len(tail) >= 8:
        return f"mouse_user_{tail}"
    return f"mouse_user_{stem[-32:]}"


def main() -> None:
    for d in (TRAIN_I, VAL_I, TRAIN_L, VAL_L):
        d.mkdir(parents=True, exist_ok=True)

    sources: list[Path] = []
    missing: list[str] = []
    for name in WANTED:
        path = SRC / name
        if path.is_file():
            sources.append(path)
        else:
            missing.append(name)

    rng = random.Random(42)
    rng.shuffle(sources)
    n_val = max(1, round(len(sources) * 0.20))
    val_set = set(sources[:n_val])

    copied_train = copied_val = skipped = 0
    for p in sources:
        fname = slug(p) + ".png"
        is_val = p in val_set
        dst_img = (VAL_I if is_val else TRAIN_I) / fname
        dst_lbl = (VAL_L if is_val else TRAIN_L) / (Path(fname).stem + ".txt")
        if dst_img.exists():
            skipped += 1
            continue
        shutil.copy2(p, dst_img)
        dst_lbl.write_text(LABEL_MOUSE_FULLIMAGE, encoding="utf-8")
        if is_val:
            copied_val += 1
        else:
            copied_train += 1

    print(f"sources_found={len(sources)} missing={len(missing)}")
    print(f"copied_train={copied_train} copied_val={copied_val} skipped_existing={skipped}")
    if missing:
        print("missing_examples:", missing[:5])


if __name__ == "__main__":
    main()
