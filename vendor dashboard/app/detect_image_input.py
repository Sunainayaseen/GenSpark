# Parse /api/detect/component input: multipart file, JSON base64, or form data URL.
import base64
import io
import re

from flask import request
from PIL import Image

_DATA_URL_PREFIX = re.compile(r'^data:image/[\w.+-]+;base64,', re.I)


def _pil_from_bytes(raw: bytes) -> tuple[Image.Image | None, str | None]:
    if not raw:
        return None, 'Image data is empty.'
    try:
        img = Image.open(io.BytesIO(raw))
        return img.convert('RGB'), None
    except Exception as exc:
        return None, f'Could not read image: {exc}'


def _pil_from_base64_string(value: str) -> tuple[Image.Image | None, str | None]:
    text = (value or '').strip()
    if not text:
        return None, 'Base64 image string is empty.'
    text = _DATA_URL_PREFIX.sub('', text)
    try:
        raw = base64.b64decode(text, validate=False)
    except Exception as exc:
        return None, f'Base64 decoding failed: {exc}'
    return _pil_from_bytes(raw)


def _pil_from_upload() -> tuple[Image.Image | None, str | None]:
    file = request.files.get('image')
    if not file:
        return None, None
    try:
        raw = file.read()
    except Exception as exc:
        return None, f'File reading failed: {exc}'
    return _pil_from_bytes(raw)


def parse_request_image() -> tuple[Image.Image | None, str | None]:
    """
    Accept image from:
      - multipart file field `image` (upload / webcam File blob)
      - JSON body `{"image": "data:image/...;base64,..."}`
      - form field `image` with data URL or raw base64
    """
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        for key in ('image', 'image_base64', 'data'):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                return _pil_from_base64_string(val)

    form_image = request.form.get('image', '')
    if isinstance(form_image, str) and form_image.strip():
        stripped = form_image.strip()
        if stripped.startswith('data:image') or len(stripped) > 200:
            img, err = _pil_from_base64_string(stripped)
            if img is not None or err:
                return img, err

    img, err = _pil_from_upload()
    if img is not None:
        return img, None
    if err:
        return None, err

    return None, 'No valid image data or file received.'


def parse_confidence(default: float = 0.35) -> float:
    raw = request.form.get('conf')
    if raw is None and request.is_json:
        payload = request.get_json(silent=True) or {}
        raw = payload.get('conf')
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = default
    return min(max(value, 0.1), 0.95)
