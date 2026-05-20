"""
GenSpark YOLO API — minimal Flask service for Railway.

  React (Vercel)  →  Flask (Railway)  →  YOLOv8 (best.pt)

Endpoints:
  GET  /health                 — Railway health check
  POST /predict                — tutorial-style upload (field: file)
  POST /api/detect/component   — GenSpark React chatbot (field: image)
  GET  /api/detect/model       — which weights file is loaded
"""
from __future__ import annotations

import io
import os
import uuid
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS
from PIL import Image
from werkzeug.utils import secure_filename

APP_DIR = Path(__file__).resolve().parent

DEFAULT_CORS_ORIGINS = [
    'https://genspark-frontend.vercel.app',
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:4173',
    'http://127.0.0.1:4173',
]

SUPPORTED_IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.jpe', '.jfif', '.png', '.bmp', '.webp',
    '.tif', '.tiff', '.heic', '.heif', '.avif', '.mpo', '.dng',
}

DISPLAY_CONFIRM_CONFIDENCE_PCT = float(
    os.getenv('GENSPARK_DISPLAY_CONF_THRESHOLD', '65')
)

CLASS_NAMES = {
    0: 'mouse',
    1: 'keyboard',
    2: 'monitor',
    3: 'ram',
}


def _cors_origins():
    origins = list(DEFAULT_CORS_ORIGINS)
    extra = os.getenv('GENSPARK_CORS_ORIGINS', '')
    for item in extra.split(','):
        item = item.strip()
        if item and item not in origins:
            origins.append(item)
    return origins


def _resolve_model_path() -> Path:
    configured = (
        os.getenv('YOLO_MODEL_PATH', '').strip()
        or os.getenv('GENSPARK_YOLO_MODEL', '').strip()
        or 'best.pt'
    )
    path = Path(configured)
    if not path.is_absolute():
        path = APP_DIR / path
    return path


MODEL_PATH = _resolve_model_path()
_model = None


def get_model():
    """Load YOLO once per worker (Railway/gunicorn)."""
    global _model
    if _model is None:
        from ultralytics import YOLO

        if not MODEL_PATH.is_file():
            raise FileNotFoundError(f'Model not found: {MODEL_PATH}')
        _model = YOLO(str(MODEL_PATH))
    return _model


app = Flask(__name__)
CORS(app, origins=_cors_origins(), methods=['GET', 'POST', 'OPTIONS'])


def _component_name(class_id: int) -> str:
    return CLASS_NAMES.get(class_id, f'class_{class_id}')


def _read_image_pixel_size(image: Image.Image) -> tuple[int, int]:
    return image.size


def _boxes_to_detections(result, img_w: int, img_h: int) -> list[dict]:
    """Match GenSpark vendor dashboard /api/detect/component shape."""
    detections = []
    boxes = getattr(result, 'boxes', None)
    if boxes is None or len(boxes) == 0:
        return detections

    for box in boxes:
        class_id = int(box.cls[0])
        conf01 = float(box.conf[0])
        confidence_pct = round(conf01 * 100, 2)
        component = _component_name(class_id)

        xyxy_px = box.xyxy[0].tolist()
        x1, y1, x2, y2 = map(float, xyxy_px)
        if img_w and img_h:
            xc = ((x1 + x2) / 2) / img_w
            yc = ((y1 + y2) / 2) / img_h
            bw = (x2 - x1) / img_w
            bh = (y2 - y1) / img_h
            xyxy = [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)]
        else:
            xc = yc = bw = bh = 0.0
            xyxy = xyxy_px

        box_norm = {'xCenter': xc, 'yCenter': yc, 'width': bw, 'height': bh}
        common = {
            'classId': class_id,
            'class_name': component,
            'confidence_model': round(conf01, 4),
            'box': box_norm,
            'xyxy': xyxy,
        }
        if confidence_pct < DISPLAY_CONFIRM_CONFIDENCE_PCT:
            detections.append({
                **common,
                'type': 'UNKNOWN',
                'name': 'Unknown Component',
                'spec': (
                    f'Below {DISPLAY_CONFIRM_CONFIDENCE_PCT:.0f}% certainty '
                    '— not labeled as a trained part'
                ),
                'confidence': confidence_pct,
                'rawGuess': component.title(),
            })
        else:
            detections.append({
                **common,
                'type': component.upper(),
                'name': component.title(),
                'spec': f'{confidence_pct}% confidence',
                'confidence': confidence_pct,
            })
    return detections


def _public_detection_error(technical: str) -> str:
    t = (technical or '').strip()
    if not t:
        return 'Component detection could not be completed. Please try again.'
    low = t.lower()
    if 'model not found' in low or 'best.pt' in low:
        return (
            'Component detection is temporarily unavailable. '
            'The AI model is not configured on this server yet.'
        )
    if 'ultralytics' in low:
        return (
            'The detection service is still being set up on the server. '
            'Please try again later.'
        )
    if len(t) > 100 or '.pt' in low:
        return (
            'We could not run component detection on this image. '
            'Try a clearer, well-lit photo.'
        )
    return t if len(t) <= 120 else (
        'Component detection could not be completed. Please try again.'
    )


def _run_inference(image: Image.Image, confidence: float = 0.35) -> tuple[dict | None, str | None]:
    try:
        model = get_model()
    except FileNotFoundError as exc:
        return None, _public_detection_error(str(exc))

    img_w, img_h = _read_image_pixel_size(image)
    try:
        results = model.predict(source=image, conf=confidence, verbose=False)
    except Exception as exc:
        return None, _public_detection_error(str(exc))

    if not results:
        return {
            'detections': [],
            'model': str(MODEL_PATH),
            'image_width': img_w,
            'image_height': img_h,
        }, None

    r0 = results[0]
    detections = _boxes_to_detections(r0, img_w, img_h)
    return {
        'detections': detections,
        'model': str(MODEL_PATH),
        'image_width': img_w,
        'image_height': img_h,
    }, None


def _parse_confidence(default: float = 0.35) -> float:
    raw = request.form.get('conf', default)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = default
    return min(max(value, 0.1), 0.95)


def _image_from_upload(field_name: str) -> tuple[Image.Image | None, str | None]:
    file = request.files.get(field_name)
    if not file or not file.filename:
        return None, 'No file uploaded'
    try:
        image = Image.open(io.BytesIO(file.read()))
        image.load()
        return image, None
    except Exception:
        return None, 'Could not read image file.'


@app.route('/health', methods=['GET'])
def health():
    return 'OK', 200


@app.route('/predict', methods=['POST'])
def predict():
    """Tutorial-style endpoint: multipart field `file`, simple class + confidence list."""
    image, err = _image_from_upload('file')
    if err:
        return jsonify({'error': err}), 400

    confidence = _parse_confidence()
    payload, error = _run_inference(image, confidence=confidence)
    if error:
        return jsonify({'error': error}), 500

    model = get_model()
    simple = []
    for item in payload['detections']:
        name = item.get('class_name') or item.get('rawGuess', 'unknown')
        conf = float(item.get('confidence_model', 0))
        simple.append({
            'class': name,
            'confidence': round(conf, 2),
        })

    return jsonify({'detections': simple})


@app.route('/api/detect/component', methods=['POST'])
def detect_component():
    """GenSpark React chatbot — multipart field `image`."""
    image, err = _image_from_upload('image')
    if err:
        return jsonify({'success': False, 'error': 'Image file is required.'}), 400

    confidence = _parse_confidence()
    payload, error = _run_inference(image, confidence=confidence)
    if error:
        return jsonify({'success': False, 'error': error}), 500

    return jsonify({
        'success': True,
        'count': len(payload['detections']),
        'detections': payload['detections'],
        'model': payload['model'],
        'image_width': payload.get('image_width'),
        'image_height': payload.get('image_height'),
    })


@app.route('/api/detect/model', methods=['GET'])
def detect_model_info():
    return jsonify({
        'success': True,
        'model': str(MODEL_PATH),
        'exists': MODEL_PATH.is_file(),
        'pinned_by_env': bool(
            os.getenv('YOLO_MODEL_PATH', '').strip()
            or os.getenv('GENSPARK_YOLO_MODEL', '').strip()
        ),
    })


if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    app.run(host='0.0.0.0', port=port)
