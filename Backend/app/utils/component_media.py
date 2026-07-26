"""Save component catalog images under this app's own static/uploads/ folder
(served both at /static/uploads/components/... via Flask's static handler, and
at the bare /uploads/components/... URL — the historical format already stored
in Component.image_url — via the /uploads/<path:filename> route in app/__init__.py)."""
import os
import secrets
from pathlib import Path

from flask import current_app

ALLOWED_IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


def _component_upload_dir() -> Path:
    return Path(current_app.static_folder) / 'uploads' / 'components'


def save_component_image(file_storage, component_id: int) -> str | None:
    if not file_storage or not getattr(file_storage, 'filename', None):
        return None
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        ext = '.jpg'
    upload_dir = _component_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f'component_{component_id}_{secrets.token_hex(6)}{ext}'
    dest = upload_dir / safe_name
    file_storage.save(dest)
    return f'/uploads/components/{safe_name}'
