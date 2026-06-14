"""Save component catalog images to GenSpark backend/uploads (served by backend/app.py)."""
import os
import secrets
from pathlib import Path

ALLOWED_IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

# vendor dashboard/app/utils -> repo root GenSpark
GENSPARK_ROOT = Path(__file__).resolve().parents[3]
COMPONENT_UPLOAD_DIR = GENSPARK_ROOT / 'backend' / 'uploads' / 'components'


def save_component_image(file_storage, component_id: int) -> str | None:
    if not file_storage or not getattr(file_storage, 'filename', None):
        return None
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        ext = '.jpg'
    COMPONENT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f'component_{component_id}_{secrets.token_hex(6)}{ext}'
    dest = COMPONENT_UPLOAD_DIR / safe_name
    file_storage.save(dest)
    return f'/uploads/components/{safe_name}'
