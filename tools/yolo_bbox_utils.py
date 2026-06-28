"""Auto bounding boxes for product photos on dark, white, or grey backgrounds."""

from __future__ import annotations

from pathlib import Path


def _foreground_mask(rgb):
    import numpy as np

    gray = rgb.mean(axis=2).astype(np.float32)
    h, w = gray.shape
    margin = max(3, min(h, w) // 40)
    corners = np.concatenate([
        gray[:margin, :margin].ravel(),
        gray[:margin, -margin:].ravel(),
        gray[-margin:, :margin].ravel(),
        gray[-margin:, -margin:].ravel(),
    ])
    bg = float(np.median(corners))

    # Light studio (white / light grey) — object is usually darker than backdrop
    if bg >= 165:
        fg = gray < (bg - 18)
    # Dark studio (black) — object is brighter than backdrop
    elif bg <= 45:
        fg = gray > (bg + 18)
    # Mid grey backdrop
    else:
        fg = np.abs(gray - bg) > 22

    return fg


def yolo_label_line(class_id: int, image_path: Path, fallback_full_frame: bool = True) -> str:
    """
    Return one YOLO label line: class xc yc w h (normalized).
    Tight box around the product; fallback to ~95% frame if empty.
    """
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        if fallback_full_frame:
            return f"{class_id} 0.5 0.5 0.95 0.95\n"
        raise

    with Image.open(image_path) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.uint8)

    h, w = rgb.shape[:2]
    if h == 0 or w == 0:
        return f"{class_id} 0.5 0.5 0.95 0.95\n"

    fg = _foreground_mask(rgb)
    if not fg.any():
        return f"{class_id} 0.5 0.5 0.95 0.95\n"

    ys, xs = np.where(fg)
    x1, x2 = int(xs.min()), int(xs.max())
    y1, y2 = int(ys.min()), int(ys.max())

    pad_x = max(4, int(0.015 * w))
    pad_y = max(4, int(0.015 * h))
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(w - 1, x2 + pad_x)
    y2 = min(h - 1, y2 + pad_y)

    bw = (x2 - x1 + 1) / w
    bh = (y2 - y1 + 1) / h
    xc = (x1 + x2 + 1) / 2 / w
    yc = (y1 + y2 + 1) / 2 / h

    bw = min(0.98, max(0.05, bw))
    bh = min(0.98, max(0.05, bh))
    xc = min(1.0, max(0.0, xc))
    yc = min(1.0, max(0.0, yc))

    return f"{class_id} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}\n"
