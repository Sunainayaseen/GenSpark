# API Routes - GenSpark (JSON endpoints)
import os
import shutil
import secrets
import subprocess
import uuid
from pathlib import Path

import requests
from datetime import datetime
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import jsonify, request, make_response, redirect, session, current_app
from flask_login import login_user, current_user
from flask_jwt_extended import create_access_token
from werkzeug.utils import secure_filename
from app.api import api_bp
from app import db
from app.models import (
    Order, OrderItem, OrderStatusHistory, VendorOrder, VendorOrderItem,
    Vendor, User, Role,
    Component, VendorComponent, PcBuild, BuildComponent, Cart, CartItem
)
from app.models.order import sync_master_order_status_from_vendor_orders
from app.utils.email_helper import send_registration_verification_email
from app.utils.vendor_delete import permanently_delete_vendor
from sqlalchemy import or_, func

from app.api.controllers.cart_controller import (
    add_to_cart as api_add_to_cart_controller,
    get_cart as api_get_cart_controller,
    update_cart as api_update_cart_controller,
    remove_item as api_remove_item_controller,
    clear_cart as api_clear_cart_controller,
)


# ---------- Helpers ----------


def _token_serializer():
    secret = current_app.config.get('SECRET_KEY', 'genspark-erp-secret-key')
    return URLSafeTimedSerializer(secret_key=secret, salt='email-confirm')


def _generate_email_token(email: str) -> str:
    return _token_serializer().dumps(email)


def _confirm_email_token(token: str, max_age: int = 86400) -> str:
    """Return email from token if valid, otherwise raise."""
    return _token_serializer().loads(token, max_age=max_age)


def _next_order_number(prefix='ORD'):
    return f'{prefix}-{datetime.utcnow().strftime("%Y%m%d%H%M%S%f")}'


def _vendor_shop_name(vendor_id):
    if not vendor_id:
        return None
    v = Vendor.query.get(vendor_id)
    return v.shop_name if v else None


def _genspark_root():
    return Path(__file__).resolve().parents[3]


def _vendor_dashboard_root():
    return Path(__file__).resolve().parents[2]


def _bundled_model_dir():
    return _vendor_dashboard_root() / 'models'


# Resolved when GENSPARK_YOLO_MODEL is unset: newest weights/best.pt under detect runs.
_detection_model_cache: Path | None = None
_detection_model_logged: bool = False


def _legacy_detection_model_candidates():
    """Fixed paths used before auto-discovery (still used as fallback)."""
    root = _genspark_root()
    bundled = _bundled_model_dir() / 'best.pt'
    return [
        bundled,
        root / 'runs' / 'detect' / 'train' / 'weights' / 'best.pt',
        root / 'runs' / 'detect' / 'runs' / 'detect' / 'train' / 'weights' / 'best.pt',
        root / 'yolov8n.pt',
        root / 'yolov8n-seg.pt',
        Path.home() / 'yolov5' / 'runs' / 'detect' / 'runs' / 'detect' / 'train' / 'weights' / 'best.pt',
    ]


def _discover_best_pt_files():
    """All weights/best.pt files under Ultralytics-style runs/detect trees."""
    roots = (
        _genspark_root() / 'runs' / 'detect',
        Path.home() / 'yolov5' / 'runs' / 'detect',
    )
    found: list[Path] = []
    for base in roots:
        if not base.is_dir():
            continue
        for p in base.rglob('best.pt'):
            if p.is_file() and p.parent.name == 'weights':
                found.append(p)
    return found


def _detection_model_path(force_refresh: bool = False) -> Path:
    """
    Return path to YOLO weights for CLI inference.

    Priority:
      1) GENSPARK_YOLO_MODEL — if set and file exists, use it (production pin).
      2) Cached auto-pick — newest weights/best.pt under GenSpark + ~/yolov5 runs/detect.
      3) Legacy hard-coded fallbacks (oldest layout).
    """
    global _detection_model_cache, _detection_model_logged

    configured = os.getenv('GENSPARK_YOLO_MODEL', '').strip()
    if configured:
        p = Path(configured)
        if p.exists():
            _detection_model_cache = p
            if not _detection_model_logged:
                _detection_model_logged = True
                try:
                    current_app.logger.info('YOLO model (GENSPARK_YOLO_MODEL): %s', p)
                except RuntimeError:
                    pass
            return p

    if _detection_model_cache and not force_refresh and _detection_model_cache.exists():
        return _detection_model_cache

    bundled = _bundled_model_dir() / 'best.pt'
    if bundled.exists():
        _detection_model_cache = bundled
        if not _detection_model_logged:
            _detection_model_logged = True
            try:
                current_app.logger.info('YOLO model (bundled): %s', bundled)
            except RuntimeError:
                pass
        return bundled

    discovered = _discover_best_pt_files()
    if discovered:
        latest = max(discovered, key=lambda x: x.stat().st_mtime)
        _detection_model_cache = latest
        if not _detection_model_logged:
            _detection_model_logged = True
            try:
                current_app.logger.info(
                    'YOLO model (auto latest best.pt, mtime): %s', latest
                )
            except RuntimeError:
                pass
        return latest

    for candidate in _legacy_detection_model_candidates():
        if candidate.exists():
            _detection_model_cache = candidate
            if not _detection_model_logged:
                _detection_model_logged = True
                try:
                    current_app.logger.info('YOLO model (legacy fallback): %s', candidate)
                except RuntimeError:
                    pass
            return candidate

    # Same return shape as before: first fallback path for a clear error message.
    fallback = Path(configured) if configured else _legacy_detection_model_candidates()[0]
    return fallback


def _invalidate_detection_model_cache():
    global _detection_model_cache, _detection_model_logged
    _detection_model_cache = None
    _detection_model_logged = False


def _component_name(class_id):
    names = {
        0: 'mouse',
        1: 'keyboard',
        2: 'monitor',
        3: 'ram',
    }
    return names.get(class_id, f'class_{class_id}')


SUPPORTED_IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.jpe', '.jfif', '.png', '.bmp', '.webp',
    '.tif', '.tiff', '.heic', '.heif', '.avif', '.mpo', '.dng',
}


MIMETYPE_EXTENSIONS = {
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'image/bmp': '.bmp',
    'image/tiff': '.tiff',
    'image/avif': '.avif',
    'image/heic': '.heic',
    'image/heif': '.heif',
}

# If model confidence (0–100) is below this, do not show a trained-class label —
# unseen objects often map to the wrong nearest class.
DISPLAY_CONFIRM_CONFIDENCE_PCT = float(os.getenv('GENSPARK_DISPLAY_CONF_THRESHOLD', '80'))


def _read_image_pixel_size(path: Path):
    """Return (width, height) of raster image for pixel-space boxes, or (None, None)."""
    try:
        from PIL import Image

        with Image.open(path) as im:
            return im.size
    except Exception:
        return None, None


def _norm_xywh_to_xyxy_pixel(xc, yc, bw, bh, iw, ih):
    """YOLO normalized center+size → pixel xyxy clamped to image bounds."""
    if not iw or not ih:
        return None
    x1 = max(0.0, (float(xc) - float(bw) / 2) * iw)
    y1 = max(0.0, (float(yc) - float(bh) / 2) * ih)
    x2 = min(float(iw), (float(xc) + float(bw) / 2) * iw)
    y2 = min(float(ih), (float(yc) + float(bh) / 2) * ih)
    return [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)]


def _public_detection_error(technical: str) -> str:
    """User-safe message for API/frontend; log technical detail server-side."""
    t = (technical or '').strip()
    if not t:
        return 'Component detection could not be completed. Please try again.'
    low = t.lower()
    try:
        current_app.logger.warning('Detection technical: %s', t)
    except RuntimeError:
        pass
    if 'model not found' in low or 'best.pt' in low or 'yolov8' in low:
        return (
            'Component detection is temporarily unavailable. '
            'The AI model is not configured on this server yet. '
            'You can still get build recommendations using the form on the left, '
            'or browse parts on the Components page.'
        )
    if 'yolo command not found' in low or 'ultralytics' in low:
        return (
            'The detection service is still being set up on the server. '
            'Please try again later or continue without camera detection.'
        )
    if len(t) > 100 or '/root/' in t or '.pt' in low or 'runs/detect' in low:
        return (
            'We could not run component detection on this image. '
            'Try a clearer, well-lit photo, or use Get recommendations without uploading.'
        )
    return t if len(t) <= 120 else (
        'Component detection could not be completed. Please try again.'
    )


def _boxes_to_detections(result, img_w, img_h):
    """Build API detection list from an Ultralytics result object."""
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
                'spec': f'Below {DISPLAY_CONFIRM_CONFIDENCE_PCT:.0f}% certainty — not labeled as a trained part',
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


def _run_yolo_detection(image_path, confidence=0.55):
    model_path = _detection_model_path()
    if not model_path.exists():
        return None, _public_detection_error(f'Model not found: {model_path}')

    try:
        from ultralytics import YOLO

        model = YOLO(str(model_path))
        results = model.predict(
            source=str(image_path),
            conf=confidence,
            verbose=False,
        )
        if not results:
            return {
                'detections': [],
                'model': str(model_path),
                'output_dir': '',
                'image_width': None,
                'image_height': None,
            }, None

        r0 = results[0]
        img_w, img_h = _read_image_pixel_size(image_path)
        if (not img_w or not img_h) and getattr(r0, 'orig_shape', None):
            img_h, img_w = int(r0.orig_shape[0]), int(r0.orig_shape[1])

        detections = _boxes_to_detections(r0, img_w, img_h)
        return {
            'detections': detections,
            'model': str(model_path),
            'output_dir': '',
            'image_width': img_w,
            'image_height': img_h,
        }, None
    except ImportError:
        pass
    except Exception as exc:
        return None, _public_detection_error(str(exc))

    yolo_cmd = shutil.which('yolo')
    if not yolo_cmd:
        return None, _public_detection_error(
            'Ultralytics is not installed. Run: pip install ultralytics'
        )

    run_name = f'api-{uuid.uuid4().hex[:10]}'
    output_root = Path.home() / 'yolov5' / 'genspark_api_runs'
    output_root.mkdir(parents=True, exist_ok=True)

    cmd = [
        yolo_cmd,
        'task=detect',
        'mode=predict',
        f'model={model_path}',
        f'source={image_path}',
        'save=True',
        'save_txt=True',
        'save_conf=True',
        f'conf={confidence}',
        f'project={output_root}',
        f'name={run_name}',
        'exist_ok=True',
        'verbose=False',
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if result.returncode != 0:
        error = (result.stderr or result.stdout or 'YOLO prediction failed').strip()
        return None, _public_detection_error(error)

    labels_file = output_root / run_name / 'labels' / f'{image_path.stem}.txt'
    detections = []
    img_w, img_h = _read_image_pixel_size(image_path)
    if labels_file.exists():
        for raw_line in labels_file.read_text(encoding='utf-8').splitlines():
            parts = raw_line.strip().split()
            if len(parts) < 6:
                continue
            class_id = int(float(parts[0]))
            xc, yc, bw, bh = map(float, parts[1:5])
            conf01 = float(parts[5])
            confidence_pct = round(conf01 * 100, 2)
            component = _component_name(class_id)
            xyxy = _norm_xywh_to_xyxy_pixel(xc, yc, bw, bh, img_w, img_h)
            box = {'xCenter': xc, 'yCenter': yc, 'width': bw, 'height': bh}
            common = {
                'classId': class_id,
                'class_name': component,
                'confidence_model': round(conf01, 4),
                'box': box,
                'xyxy': xyxy,
            }
            if confidence_pct < DISPLAY_CONFIRM_CONFIDENCE_PCT:
                detections.append({
                    **common,
                    'type': 'UNKNOWN',
                    'name': 'Unknown Component',
                    'spec': f'Below {DISPLAY_CONFIRM_CONFIDENCE_PCT:.0f}% certainty — not labeled as a trained part',
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

    return {
        'detections': detections,
        'model': str(model_path),
        'output_dir': str(output_root / run_name),
        'image_width': img_w,
        'image_height': img_h,
    }, None


@api_bp.route('/detect/component', methods=['POST'])
def detect_component():
    """Receive an uploaded image and return YOLO component detections for React."""
    image = request.files.get('image')
    if not image or not image.filename:
        return jsonify({'success': False, 'error': 'Image file is required.'}), 400

    ext = Path(image.filename).suffix.lower()
    if not ext:
        ext = MIMETYPE_EXTENSIONS.get((image.mimetype or '').lower(), '')
    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        return jsonify({'success': False, 'error': 'Unsupported image format.'}), 400
    storage_ext = '.jpg' if ext in {'.jpe', '.jfif'} else ext

    try:
        confidence = float(request.form.get('conf', 0.55))
    except (TypeError, ValueError):
        confidence = 0.55
    confidence = min(max(confidence, 0.1), 0.95)

    upload_dir = Path.home() / 'yolov5' / 'genspark_api_uploads'
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(image.filename)
    if Path(safe_name).suffix.lower() != storage_ext:
        safe_name = f'{Path(safe_name).stem or "capture"}{storage_ext}'
    filename = f'{uuid.uuid4().hex}_{safe_name}'
    image_path = upload_dir / filename
    image.save(image_path)

    payload, error = _run_yolo_detection(image_path, confidence=confidence)
    if error:
        return jsonify({'success': False, 'error': error}), 500

    return jsonify({
        'success': True,
        'count': len(payload['detections']),
        'detections': payload['detections'],
        'model': payload['model'],
        'output_dir': payload['output_dir'],
        'image_width': payload.get('image_width'),
        'image_height': payload.get('image_height'),
    })


@api_bp.route('/detect/model', methods=['GET'])
def detect_model_info():
    """Return the YOLO weights path the API would use (no inference)."""
    p = _detection_model_path()
    return jsonify({
        'success': True,
        'model': str(p),
        'exists': p.exists(),
        'pinned_by_env': bool(os.getenv('GENSPARK_YOLO_MODEL', '').strip()),
    })


@api_bp.route('/detect/model/reload', methods=['POST'])
def detect_model_reload():
    """
    Clear cached model path and resolve latest best.pt again (no server restart).

    Disabled unless GENSPARK_MODEL_RELOAD_KEY is set; send the same value in header
    X-GenSpark-Model-Reload-Key.
    """
    expected = os.getenv('GENSPARK_MODEL_RELOAD_KEY', '').strip()
    if not expected:
        return jsonify({
            'success': False,
            'error': 'Reload disabled. Set GENSPARK_MODEL_RELOAD_KEY to enable.',
        }), 404
    supplied = (request.headers.get('X-GenSpark-Model-Reload-Key') or '').strip()
    if supplied != expected:
        return jsonify({'success': False, 'error': 'Invalid or missing reload key.'}), 403

    _invalidate_detection_model_cache()
    p = _detection_model_path(force_refresh=True)
    return jsonify({
        'success': True,
        'model': str(p),
        'exists': p.exists(),
    })


# ---------- Example: GET list ----------
@api_bp.route('/orders', methods=['GET'])
def list_orders():
    """GET /api/orders — ?mine=1 = current user's orders; else admin-only list."""
    mine = request.args.get('mine') == '1'
    status = request.args.get('status')
    limit = request.args.get('limit', type=int, default=50)
    if mine:
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Login required'}), 401
        query = Order.query.filter_by(user_id=current_user.id)
    else:
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        query = Order.query
    query = query.order_by(Order.created_at.desc())
    if status:
        query = query.filter_by(status=status)
    orders = query.limit(limit).all()
    return jsonify({
        'success': True,
        'count': len(orders),
        'orders': [
            {
                'id': o.id,
                'order_number': o.order_number or str(o.id),
                'total_amount': float(o.total_amount or 0),
                'status': o.status,
                'created_at': o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ]
    })


# ---------- Example: GET one by ID ----------
@api_bp.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    """GET /api/orders/1 — Customer sees own order; admin sees any."""
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'error': 'Login required'}), 401
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'success': False, 'error': 'Order not found'}), 404
    if not current_user.is_admin and order.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    order_items = order.items.all()
    items_subtotal = sum(float((it.total_price or 0)) for it in order_items)
    shipping_fee = float(getattr(order, 'shipping_fee', 0) or 0)
    vendor_orders = VendorOrder.query.filter_by(order_id=order.id).all()
    history = OrderStatusHistory.query.filter_by(order_id=order.id).order_by(OrderStatusHistory.created_at.asc()).all()
    return jsonify({
        'success': True,
        'order': {
            'id': order.id,
            'order_number': order.order_number or str(order.id),
            'items_subtotal': items_subtotal,
            'shipping_fee': shipping_fee,
            'total_amount': float(order.total_amount or 0),
            'status': order.status,
            'shipping_address': order.shipping_address,
            'created_at': order.created_at.isoformat() if order.created_at else None,
            'items': [
                {
                    'id': it.id,
                    'item_type': it.item_type,
                    'item_id': it.item_id,
                    'component_name': it.component_name,
                    'vendor_id': it.vendor_id,
                    'vendor_shop_name': _vendor_shop_name(it.vendor_id),
                    'quantity': int(it.quantity or 0),
                    'unit_price': float(it.unit_price or 0),
                    'total_price': float(it.total_price or 0),
                } for it in order_items
            ],
            'vendor_orders': [
                {
                    'id': vo.id,
                    'vendor_id': vo.vendor_id,
                    'vendor_shop_name': _vendor_shop_name(vo.vendor_id),
                    'status': vo.status,
                    'proof_image_url': vo.proof_image_url,
                    'proof_approved': bool(getattr(vo, 'proof_approved', True)),
                    'total_amount': float(vo.total_amount or 0),
                    'items': [
                        {
                            'component_id': vii.component_id,
                            'component_name': vii.component_name,
                            'quantity': int(vii.quantity or 0),
                            'unit_price': float(vii.unit_price or 0),
                            'total_price': float(vii.total_price or 0),
                        } for vii in vo.items.all()
                    ],
                } for vo in vendor_orders
            ],
            'status_history': [
                {
                    'status': h.status,
                    'notes': h.notes,
                    'created_at': h.created_at.isoformat() if h.created_at else None,
                } for h in history
            ],
        }
    })


@api_bp.route('/orders/place', methods=['POST'])
def place_order():
    """POST /api/orders/place

    Place customer order with mixed items (pc_build + component).
    Order goes to admin-review first.
    """
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'error': 'Login required'}), 401

    payload = request.get_json(silent=True) or {}
    shipping_address = (payload.get('shipping_address') or '').strip() or 'Pakistan'
    payment_method = (payload.get('payment_method') or 'cod').strip().lower()

    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart:
        return jsonify({'success': False, 'error': 'Cart is empty'}), 400
    cart_items = cart.items.all()
    if not cart_items:
        return jsonify({'success': False, 'error': 'Cart is empty'}), 400

    normalized = []
    grand_total = 0.0
    for ci in cart_items:
        component = Component.query.get(ci.component_id) if ci.component_id else None
        if not component:
            continue
        quantity = int(ci.quantity or 0)
        if quantity <= 0:
            continue
        unit_price = float(ci.unit_price or component.price or 0)
        total_price = unit_price * quantity
        grand_total += total_price
        normalized.append({
            'item_type': 'component',
            'item_id': component.id,
            'component_name': ci.component_name or component.name,
            'vendor_id': ci.vendor_id,
            'quantity': quantity,
            'unit_price': unit_price,
            'total_price': total_price,
        })

    if not normalized:
        return jsonify({'success': False, 'error': 'Cart has no valid items'}), 400

    # Match React checkout: flat shipping when there is at least one line (see Checkout.jsx).
    SHIPPING_FLAT_PKR = 2000.0
    shipping_fee = float(SHIPPING_FLAT_PKR) if normalized else 0.0
    order_grand_total = float(grand_total) + shipping_fee

    # One order at a time: until admin approves or rejects a pending order, block new placements
    _awaiting_admin = (
        Order.query.filter(
            Order.user_id == current_user.id,
            Order.status.in_(('pending', 'admin-review')),
        )
        .order_by(Order.created_at.desc())
        .first()
    )
    if _awaiting_admin:
        return jsonify({
            'success': False,
            'error': (
                'You already have an order awaiting admin approval. '
                'You cannot place another order until that one is approved or rejected.'
            ),
            'code': 'PENDING_ORDER_EXISTS',
            'blocking_order_id': _awaiting_admin.id,
        }), 400

    order = Order(
        user_id=current_user.id,
        order_number=_next_order_number('ORD'),
        total_amount=order_grand_total,
        shipping_fee=shipping_fee,
        status='pending',
        shipping_address=shipping_address,
        notes=f'payment_method={payment_method}',
    )
    db.session.add(order)
    db.session.flush()

    for it in normalized:
        db.session.add(OrderItem(
            order_id=order.id,
            item_type=it['item_type'],
            item_id=it['item_id'],
            component_name=it['component_name'],
            vendor_id=it['vendor_id'],
            quantity=it['quantity'],
            unit_price=it['unit_price'],
            total_price=it['total_price'],
        ))

    db.session.add(OrderStatusHistory(
        order_id=order.id,
        status='pending',
        notes='Order placed — awaiting admin approval',
    ))
    CartItem.query.filter_by(cart_id=cart.id).delete()
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Order placed successfully. Waiting for admin approval.',
        'order': {
            'id': order.id,
            'order_number': order.order_number,
            'status': order.status,
            'items_subtotal': float(grand_total),
            'shipping_fee': shipping_fee,
            'total_amount': float(order.total_amount or 0),
        }
    }), 201


@api_bp.route('/orders/<int:order_id>/admin-approve', methods=['POST'])
def admin_approve_order(order_id):
    """POST /api/orders/<id>/admin-approve

    Admin approves customer order and system generates vendor-wise child orders
    for components (including components exploded from pc_build items).
    """
    if not current_user.is_authenticated or not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Admin access required'}), 403

    parent = Order.query.get(order_id)
    if not parent:
        return jsonify({'success': False, 'error': 'Order not found'}), 404
    if parent.status in ('approved', 'processing', 'completed', 'rejected', 'ready_to_dispatch', 'shipped', 'delivered'):
        return jsonify({'success': False, 'error': 'Order cannot be approved in its current state'}), 400

    parent_items = parent.items.all()
    if not parent_items:
        return jsonify({'success': False, 'error': 'Order has no items'}), 400

    vendor_buckets = {}
    unassigned_items = []
    for it in parent_items:
        qty = int(it.quantity or 0)
        if qty <= 0:
            continue
        if not it.vendor_id:
            unassigned_items.append({'order_item_id': it.id, 'component_id': it.item_id})
            continue
        vendor_buckets.setdefault(it.vendor_id, []).append(it)

    if unassigned_items:
        return jsonify({'success': False, 'error': 'Some items have no vendor assignment', 'unassigned_items': unassigned_items}), 400

    generated_orders = []
    for vendor_id, items in vendor_buckets.items():
        v_order = VendorOrder(
            order_id=parent.id,
            vendor_id=vendor_id,
            status='assigned',
            total_amount=0,
        )
        db.session.add(v_order)
        db.session.flush()

        subtotal = 0.0
        for it in items:
            qty = int(it.quantity or 0)
            unit_price = float(it.unit_price or 0)
            line_total = unit_price * qty
            subtotal += line_total
            db.session.add(VendorOrderItem(
                vendor_order_id=v_order.id,
                component_id=it.item_id,
                component_name=it.component_name,
                quantity=qty,
                unit_price=unit_price,
                total_price=line_total,
            ))
            inv = VendorComponent.query.filter_by(vendor_id=vendor_id, component_id=it.item_id).first()
            if inv:
                inv.quantity = max(0, int(inv.quantity or 0) - qty)

        v_order.total_amount = subtotal
        generated_orders.append({
            'vendor_order_id': v_order.id,
            'vendor_id': vendor_id,
            'status': v_order.status,
            'total_amount': subtotal,
        })

    parent.status = 'processing'
    db.session.add(OrderStatusHistory(order_id=parent.id, status='approved', notes='Admin approved order'))
    db.session.add(OrderStatusHistory(order_id=parent.id, status='processing', notes='Vendor orders assigned'))
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Admin approved. Vendor orders created and assigned.',
        'order_id': parent.id,
        'vendor_orders': generated_orders,
    })


@api_bp.route('/orders/<int:order_id>/admin-reject', methods=['POST'])
def admin_reject_order(order_id):
    """POST /api/orders/<id>/admin-reject — Admin rejects before vendor split. JSON { reason?: str }"""
    if not current_user.is_authenticated or not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    parent = Order.query.get(order_id)
    if not parent:
        return jsonify({'success': False, 'error': 'Order not found'}), 404
    if parent.status in ('processing', 'completed', 'rejected', 'ready_to_dispatch', 'shipped', 'delivered'):
        return jsonify({'success': False, 'error': 'Order cannot be rejected in its current state'}), 400
    if VendorOrder.query.filter_by(order_id=parent.id).first():
        return jsonify({'success': False, 'error': 'Vendor orders already exist; use support to cancel'}), 400
    payload = request.get_json(silent=True) or {}
    reason = (payload.get('reason') or '').strip()
    parent.status = 'rejected'
    note_line = f'admin_reject_reason={reason}' if reason else 'admin_reject'
    parent.notes = (parent.notes or '') + '\n' + note_line
    db.session.add(OrderStatusHistory(
        order_id=parent.id,
        status='rejected',
        notes=reason or 'Order rejected by admin',
    ))
    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Order rejected.',
        'order_id': parent.id,
        'status': parent.status,
    })


@api_bp.route('/vendor/orders', methods=['GET'])
def vendor_orders_list():
    if not current_user.is_authenticated or not current_user.is_vendor:
        return jsonify({'success': False, 'error': 'Vendor access required'}), 403

    vendor = Vendor.query.filter_by(user_id=current_user.id).first()
    if not vendor:
        return jsonify({'success': False, 'error': 'Vendor profile not found'}), 404

    rows = VendorOrder.query.filter_by(vendor_id=vendor.id).order_by(VendorOrder.created_at.desc()).all()
    data = []
    for vo in rows:
        order = Order.query.get(vo.order_id)
        data.append({
            'vendor_order_id': vo.id,
            'order_id': vo.order_id,
            'order_number': order.order_number if order else str(vo.order_id),
            'status': vo.status,
            'total_amount': float(vo.total_amount or 0),
            'shipping_address': order.shipping_address if order else None,
            'items': [
                {
                    'component_id': it.component_id,
                    'component_name': it.component_name,
                    'quantity': int(it.quantity or 0),
                    'unit_price': float(it.unit_price or 0),
                    'total_price': float(it.total_price or 0),
                } for it in vo.items.all()
            ],
        })
    return jsonify({'success': True, 'count': len(data), 'vendor_orders': data})


@api_bp.route('/vendor/orders/<int:vendor_order_id>/status', methods=['POST'])
def vendor_order_update_status(vendor_order_id):
    if not current_user.is_authenticated or not current_user.is_vendor:
        return jsonify({'success': False, 'error': 'Vendor access required'}), 403
    vendor = Vendor.query.filter_by(user_id=current_user.id).first()
    if not vendor:
        return jsonify({'success': False, 'error': 'Vendor profile not found'}), 404

    vo = VendorOrder.query.filter_by(id=vendor_order_id, vendor_id=vendor.id).first()
    if not vo:
        return jsonify({'success': False, 'error': 'Vendor order not found'}), 404

    payload = request.get_json(silent=True) or {}
    new_status = (payload.get('status') or '').strip().lower()
    proof_image_url = (payload.get('proof_image_url') or '').strip() or None
    if new_status not in ('accepted', 'assembling', 'completed', 'rejected'):
        return jsonify({'success': False, 'error': 'Invalid status'}), 400

    vo.status = new_status
    if proof_image_url:
        vo.proof_image_url = proof_image_url
        vo.proof_approved = False
    if new_status == 'rejected':
        vo.rejection_reason = (payload.get('rejection_reason') or '').strip() or None

    order = Order.query.get(vo.order_id)
    if order:
        sync_master_order_status_from_vendor_orders(order.id)

    db.session.commit()
    return jsonify({'success': True, 'message': 'Vendor order updated', 'vendor_order_id': vo.id, 'status': vo.status})


# ---------- Example: GET vendors ----------
@api_bp.route('/vendors', methods=['GET'])
def list_vendors():
    """GET /api/vendors - List approved vendors"""
    vendors = Vendor.query.filter_by(approval_status='approved').order_by(Vendor.shop_name).all()
    return jsonify({
        'success': True,
        'count': len(vendors),
        'vendors': [
            {
                'id': v.id,
                'shop_name': v.shop_name,
                'city': v.city,
                'phone': v.phone,
            }
            for v in vendors
        ]
    })


# ---------- Cart (frontend) ----------
@api_bp.route('/add-to-cart', methods=['POST'])
def api_add_to_cart():
    return api_add_to_cart_controller()


@api_bp.route('/cart', methods=['GET'])
def api_get_cart():
    return api_get_cart_controller()


@api_bp.route('/update-cart', methods=['PUT'])
def api_update_cart():
    return api_update_cart_controller()


@api_bp.route('/remove-item', methods=['DELETE'])
def api_remove_item():
    return api_remove_item_controller()


# Extra feature: empty cart
@api_bp.route('/cart/clear', methods=['POST'])
def api_clear_cart():
    return api_clear_cart_controller()


# ---------- Vendor: block/remove from public listing ----------
@api_bp.route('/vendors/<int:vendor_id>/block', methods=['POST'])
def block_vendor(vendor_id):
    """
    POST /api/vendors/<vendor_id>/block
    Admin-only. Sets Vendor.approval_status='blocked' so it disappears from /api/vendors.
    """
    if not current_user.is_authenticated or not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Admin access required'}), 403

    vendor = Vendor.query.get(vendor_id)
    if not vendor:
        return jsonify({'success': False, 'error': 'Vendor not found'}), 404

    vendor.approval_status = 'blocked'
    db.session.commit()
    return jsonify({'success': True, 'message': f'Vendor {vendor.shop_name} blocked'})


@api_bp.route('/vendors/<int:vendor_id>', methods=['DELETE'])
def delete_vendor_permanent(vendor_id):
    """
    DELETE /api/vendors/<vendor_id>
    Admin-only. Permanently removes vendor row and related links from DB.
    """
    if not current_user.is_authenticated or not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Admin access required'}), 403

    ok, err = permanently_delete_vendor(vendor_id)
    if not ok:
        code = 404 if err == 'Vendor not found' else 500
        return jsonify({'success': False, 'error': err or 'Delete failed'}), code
    return jsonify({'success': True, 'message': 'Vendor removed from database'})


# ---------- Component search (frontend) ----------
@api_bp.route('/components/search', methods=['GET'])
def api_components_search():
    """GET /api/components/search?q=...&limit=20

    Returns matching components from DB for frontend search.
    """
    q = (request.args.get('q') or '').strip()
    limit = request.args.get('limit', type=int, default=20)

    # Optional filters
    category_id = request.args.get('category_id', type=int)
    brand_id = request.args.get('brand_id', type=int)

    query = Component.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Component.name.ilike(like),
                Component.description.ilike(like),
            )
        )
    if category_id is not None:
        query = query.filter(Component.category_id == category_id)
    if brand_id is not None:
        query = query.filter(Component.brand_id == brand_id)

    components = query.order_by(Component.stock.desc(), Component.price.asc()).limit(limit).all()

    include_vendor_summary = request.args.get('vendor_summary', type=int) == 1
    vendor_summary = {}
    if include_vendor_summary and components:
        ids = [c.id for c in components]
        rows = (
            db.session.query(
                VendorComponent.component_id,
                func.count(VendorComponent.id),
            )
            .join(Vendor, Vendor.id == VendorComponent.vendor_id)
            .filter(
                Vendor.approval_status == 'approved',
                VendorComponent.quantity > 0,
                VendorComponent.component_id.in_(ids),
            )
            .group_by(VendorComponent.component_id)
            .all()
        )
        vendor_summary = {cid: int(cnt) for cid, cnt in rows}

    def _component_row(c):
        row = {
            'id': c.id,
            'name': c.name,
            'category': c.category.name if getattr(c, 'category', None) else None,
            'brand': c.brand.name if getattr(c, 'brand', None) else None,
            'price': float(c.price or 0),
            'stock': int(c.stock or 0),
            'image_url': c.image_url,
            'description': c.description,
        }
        if include_vendor_summary:
            n = vendor_summary.get(c.id, 0)
            row['vendors_with_stock'] = n
            row['has_vendor_stock'] = n > 0
        return row

    return jsonify({
        'success': True,
        'count': len(components),
        'components': [_component_row(c) for c in components],
    })


@api_bp.route('/components/<int:component_id>/vendors', methods=['GET'])
def api_component_vendors(component_id):
    """GET /api/components/<id>/vendors

    Returns approved vendors that currently have stock for this component.
    """
    component = Component.query.get(component_id)
    if not component:
        return jsonify({'success': False, 'error': 'Component not found'}), 404

    links = (
        VendorComponent.query
        .filter(VendorComponent.component_id == component_id)
        .filter(VendorComponent.quantity > 0)
        .all()
    )

    vendors = []
    for link in links:
        vendor = Vendor.query.get(link.vendor_id)
        if not vendor or vendor.approval_status != 'approved':
            continue
        vendors.append({
            'id': vendor.id,
            'shop_name': vendor.shop_name,
            'city': vendor.city,
            'phone': vendor.phone,
            'available_quantity': int(link.quantity or 0),
            'vendor_price': float(link.price or 0),
        })

    return jsonify({
        'success': True,
        'component': {
            'id': component.id,
            'name': component.name,
            'price': float(component.price or 0),
        },
        'count': len(vendors),
        'vendors': vendors,
    })


# ---------- Health check (no DB) – browser me "OK" dikhe ----------
@api_bp.route('/health', methods=['GET'])
def health():
    """GET /api/health – sirf OK. Flask chal raha hai check karne ke liye."""
    r = make_response('OK', 200)
    r.headers['Content-Type'] = 'text/plain; charset=utf-8'
    return r


@api_bp.route('/deploy-check', methods=['GET'])
def deploy_check():
    """GET /api/deploy-check — confirms Railway is running the JWT change-password build."""
    return jsonify({
        'success': True,
        'change_password_handler': 'manual_bearer_v4',
        'message': 'If POST /api/change-password still returns Login required, redeploy failed.',
    })


# ---------- Example: POST (create) ----------
@api_bp.route('/ping', methods=['GET', 'POST'])
def ping():
    """GET/POST /api/ping - Health check or echo JSON body"""
    if request.method == 'POST':
        body = request.get_json(silent=True) or {}
        return jsonify({'success': True, 'message': 'pong', 'received': body})
    return jsonify({'success': True, 'message': 'pong'})


# ---------- React App.jsx calls this on load – 404 fix ----------
@api_bp.route('/message', methods=['GET', 'OPTIONS'])
def get_message():
    """GET /api/message - React app health / welcome message"""
    if request.method == 'OPTIONS':
        return make_response('', 204)
    return jsonify({
        'success': True,
        'message': 'Hello from GenSpark Flask API!',
    })


# ---------- Login (session + JWT) ----------
@api_bp.route('/login', methods=['POST', 'OPTIONS'])
def api_login():
    """POST /api/login - JSON { email, password }.

    - Validates credentials
    - Sets Flask session (login_user) for existing dashboards
    - Returns JWT token so React/frontend can use Bearer auth
    """
    if request.method == 'OPTIONS':
        r = make_response('', 204)
        r.headers['Access-Control-Max-Age'] = '86400'
        return r
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    if not email or not password:
        return jsonify({'success': False, 'error': 'Email and password required'}), 400
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
    if getattr(user, 'status', 'active') != 'active':
        msg = 'Account blocked'
        if getattr(user, 'status', None) == 'pending_email':
            msg = 'Please verify your email before logging in.'
        return jsonify({'success': False, 'error': msg}), 403

    # Flask-Login session (for existing admin/vendor dashboards)
    login_user(user)

    role_name = user.role_ref.name if getattr(user, 'role_ref', None) else 'customer'
    must_change = getattr(user, 'must_change_password', False)

    # JWT token for frontend (identity = user.id, include role)
    additional_claims = {
        'role': role_name,
    }
    access_token = create_access_token(identity=user.id, additional_claims=additional_claims)

    return jsonify({
        'success': True,
        'message': 'Logged in',
        'token': access_token,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': role_name,
            'must_change_password': bool(must_change),
        }
    })


@api_bp.route('/admin/login', methods=['POST', 'OPTIONS'])
def api_admin_login():
    """POST /api/admin/login - Admin-only login that returns JWT token."""
    if request.method == 'OPTIONS':
        r = make_response('', 204)
        r.headers['Access-Control-Max-Age'] = '86400'
        return r
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    if not email or not password:
        return jsonify({'success': False, 'error': 'Email and password required'}), 400
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
    if getattr(user, 'status', 'active') != 'active':
        msg = 'Account blocked'
        if getattr(user, 'status', None) == 'pending_email':
            msg = 'Please verify your email before logging in.'
        return jsonify({'success': False, 'error': msg}), 403
    role_name = user.role_ref.name if getattr(user, 'role_ref', None) else 'customer'
    if role_name != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403

    login_user(user)
    additional_claims = {'role': role_name}
    access_token = create_access_token(identity=user.id, additional_claims=additional_claims)
    return jsonify({
        'success': True,
        'message': 'Admin login successful',
        'token': access_token,
        'user_role': role_name,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
        }
    })


# ---------- Change password (first login or user-initiated) ----------
# No @login_required / @jwt_required — auth is manual Bearer + email/OTP fallback below.
@api_bp.route('/change-password', methods=['POST', 'OPTIONS'])
def api_change_password():
    """POST /api/change-password — manual Bearer decode, then email + current_password fallback."""
    if request.method == 'OPTIONS':
        r = make_response('', 204)
        r.headers['Access-Control-Max-Age'] = '86400'
        return r

    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    current = data.get('current_password') or ''
    new_pw = data.get('new_password') or ''

    if not current or not new_pw:
        return jsonify({'success': False, 'error': 'Current and new password required'}), 400
    if len(new_pw) < 6:
        return jsonify({'success': False, 'error': 'New password must be at least 6 characters'}), 400

    from app.utils.jwt_session_bridge import (
        find_user_by_email,
        resolve_change_password_user,
        user_from_bearer_token_string,
    )

    user = None

    # 1) Bulletproof manual Bearer extraction (no decorator / session gate)
    auth_header = (request.headers.get('Authorization') or '').strip()
    if auth_header.lower().startswith('bearer '):
        token = auth_header.split(' ', 1)[1].strip()
        if token:
            user = user_from_bearer_token_string(token)

    # 2) Email + one-time password from JSON (never return generic "Login required")
    if user is None:
        user, err_body, err_status = resolve_change_password_user(email, current)
        if err_body is not None:
            return jsonify(err_body), err_status
    elif email:
        by_email = find_user_by_email(email)
        if by_email and by_email.id != user.id:
            return jsonify({
                'success': False,
                'error': 'Email does not match your signed-in account.',
            }), 403

    if not user.check_password(current):
        return jsonify({'success': False, 'error': 'Current password is wrong'}), 400

    user.set_password(new_pw)
    user.must_change_password = False
    db.session.commit()
    return jsonify({'success': True, 'message': 'Password updated'})


# ---------- Registration (frontend) + email verification ----------


@api_bp.route('/register', methods=['POST', 'OPTIONS'])
def api_register():
    """POST /api/register - JSON { name, email, role }.

    - Creates user with one-time password
    - Marks status as pending_email
    - Sends verification email with link + one-time password
    - Returns one_time_password so frontend can show it once
    """
    if request.method == 'OPTIONS':
        r = make_response('', 204)
        r.headers['Access-Control-Max-Age'] = '86400'
        return r

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    role_raw = (data.get('role') or 'customer').strip().lower()
    if not name or not email:
        return jsonify({'success': False, 'error': 'Name and email are required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'error': 'Email already registered'}), 409

    role_name = 'vendor' if role_raw == 'vendor' else 'customer'
    role = Role.query.filter_by(name=role_name).first()
    if not role:
        return jsonify({'success': False, 'error': 'Role configuration error. Run init_db.py.'}), 500

    one_time_password = secrets.token_urlsafe(8)
    user = User(
        name=name,
        email=email,
        role_id=role.id,
        status='pending_email',
        must_change_password=True,
    )
    user.set_password(one_time_password)
    db.session.add(user)
    db.session.commit()

    verify_url = None
    try:
        token = _generate_email_token(user.email)
        from app.utils.urls import build_api_url
        verify_url = build_api_url(f'/verify-email?token={token}')
        send_registration_verification_email(
            to_email=user.email,
            name=user.name,
            one_time_password=one_time_password,
            verify_url=verify_url,
            role_type='vendor' if role_name == 'vendor' else 'user',
        )
    except Exception:
        # Email failure should not break registration – user can be manually verified.
        pass

    return jsonify({
        'success': True,
        'message': 'Registration successful. Please check your email to verify your account.',
        'one_time_password': one_time_password,
        'verification_url': verify_url,
    })


@api_bp.route('/verify-email', methods=['GET'])
def api_verify_email():
    """GET /api/verify-email?token=... - mark user email as verified."""
    token = request.args.get('token', '')
    if not token:
        return jsonify({'success': False, 'error': 'Missing token'}), 400
    try:
        email = _confirm_email_token(token)
    except SignatureExpired:
        return jsonify({'success': False, 'error': 'Verification link expired'}), 400
    except BadSignature:
        return jsonify({'success': False, 'error': 'Invalid verification link'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    user.status = 'active'
    db.session.commit()
    return jsonify({'success': True, 'message': 'Email verified. You can now log in.'})


# ---------- Current user (for OAuth callback sync on frontend) ----------
@api_bp.route('/me', methods=['GET'])
def api_me():
    """GET /api/me - Return current user if logged in (session or JWT Bearer)."""
    from app.utils.jwt_session_bridge import resolve_api_user

    user = resolve_api_user()
    if not user:
        return jsonify({'success': False, 'user': None}), 200
    role_name = user.role_ref.name if getattr(user, 'role_ref', None) else 'customer'
    return jsonify({
        'success': True,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': role_name,
            'must_change_password': bool(getattr(user, 'must_change_password', False)),
        }
    })


# ---------- OAuth: Google ----------
@api_bp.route('/auth/google', methods=['GET'])
def auth_google():
    """Redirect to Google account chooser / sign-in."""
    cid = current_app.config.get('GOOGLE_CLIENT_ID')
    if not cid:
        return jsonify({'success': False, 'error': 'Google login not configured'}), 503
    state = secrets.token_urlsafe(24)
    session['oauth_state'] = state
    session['oauth_provider'] = 'google'
    base = request.url_root.rstrip('/')
    redirect_uri = f'{base}/api/auth/google/callback'
    url = (
        'https://accounts.google.com/o/oauth2/v2/auth?'
        f'client_id={cid}&redirect_uri={redirect_uri}&response_type=code&'
        'scope=openid%20email%20profile&state=' + state
    )
    return redirect(url)


@api_bp.route('/auth/google/callback', methods=['GET'])
def auth_google_callback():
    if session.get('oauth_provider') != 'google':
        return redirect(_frontend_url() + '?auth_error=state')
    state = request.args.get('state')
    if not state or state != session.get('oauth_state'):
        return redirect(_frontend_url() + '?auth_error=state')
    code = request.args.get('code')
    if not code:
        return redirect(_frontend_url() + '?auth_error=no_code')
    session.pop('oauth_state', None)
    session.pop('oauth_provider', None)

    cid = current_app.config.get('GOOGLE_CLIENT_ID')
    secret = current_app.config.get('GOOGLE_CLIENT_SECRET')
    base = request.url_root.rstrip('/')
    redirect_uri = f'{base}/api/auth/google/callback'
    r = requests.post(
        'https://oauth2.googleapis.com/token',
        data={
            'code': code,
            'client_id': cid,
            'client_secret': secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        },
        headers={'Accept': 'application/json'},
        timeout=10,
    )
    if r.status_code != 200:
        return redirect(_frontend_url() + '?auth_error=token')
    data = r.json()
    access_token = data.get('access_token')
    if not access_token:
        return redirect(_frontend_url() + '?auth_error=token')
    r2 = requests.get(
        'https://www.googleapis.com/oauth2/v2/userinfo',
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=10,
    )
    if r2.status_code != 200:
        return redirect(_frontend_url() + '?auth_error=profile')
    profile = r2.json()
    email = (profile.get('email') or '').strip().lower()
    name = (profile.get('name') or profile.get('email') or 'User').strip()[:100]
    if not email:
        return redirect(_frontend_url() + '?auth_error=no_email')
    user = User.query.filter_by(email=email).first()
    if not user:
        role = Role.query.filter_by(name='customer').first()
        if not role:
            return redirect(_frontend_url() + '?auth_error=config')
        user = User(name=name, email=email, role_id=role.id, must_change_password=False)
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.commit()
    if getattr(user, 'status', 'active') != 'active':
        return redirect(_frontend_url() + '?auth_error=blocked')
    login_user(user)
    return redirect(_frontend_url() + '?oauth=google')


# ---------- OAuth: GitHub ----------
@api_bp.route('/auth/github', methods=['GET'])
def auth_github():
    """Redirect to GitHub authorize (connect with GitHub account)."""
    cid = current_app.config.get('GITHUB_CLIENT_ID')
    if not cid:
        return jsonify({'success': False, 'error': 'GitHub login not configured'}), 503
    state = secrets.token_urlsafe(24)
    session['oauth_state'] = state
    session['oauth_provider'] = 'github'
    base = request.url_root.rstrip('/')
    redirect_uri = f'{base}/api/auth/github/callback'
    url = (
        'https://github.com/login/oauth/authorize?'
        f'client_id={cid}&redirect_uri={redirect_uri}&state={state}&scope=user:email%20read:user'
    )
    return redirect(url)


@api_bp.route('/auth/github/callback', methods=['GET'])
def auth_github_callback():
    if session.get('oauth_provider') != 'github':
        return redirect(_frontend_url() + '?auth_error=state')
    state = request.args.get('state')
    if not state or state != session.get('oauth_state'):
        return redirect(_frontend_url() + '?auth_error=state')
    code = request.args.get('code')
    if not code:
        return redirect(_frontend_url() + '?auth_error=no_code')
    session.pop('oauth_state', None)
    session.pop('oauth_provider', None)

    cid = current_app.config.get('GITHUB_CLIENT_ID')
    secret = current_app.config.get('GITHUB_CLIENT_SECRET')
    base = request.url_root.rstrip('/')
    redirect_uri = f'{base}/api/auth/github/callback'
    r = requests.post(
        'https://github.com/login/oauth/access_token',
        data={
            'code': code,
            'client_id': cid,
            'client_secret': secret,
            'redirect_uri': redirect_uri,
        },
        headers={'Accept': 'application/json'},
        timeout=10,
    )
    if r.status_code != 200:
        return redirect(_frontend_url() + '?auth_error=token')
    data = r.json()
    access_token = data.get('access_token')
    if not access_token:
        return redirect(_frontend_url() + '?auth_error=token')
    r2 = requests.get(
        'https://api.github.com/user',
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=10,
    )
    if r2.status_code != 200:
        return redirect(_frontend_url() + '?auth_error=profile')
    profile = r2.json()
    email = (profile.get('email') or '').strip().lower()
    if not email:
        r3 = requests.get(
            'https://api.github.com/user/emails',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
        if r3.status_code == 200 and r3.json():
            for e in r3.json():
                if e.get('primary'):
                    email = (e.get('email') or '').strip().lower()
                    break
            if not email and r3.json():
                email = (r3.json()[0].get('email') or '').strip().lower()
    name = (profile.get('name') or profile.get('login') or 'User').strip()[:100]
    if not email:
        return redirect(_frontend_url() + '?auth_error=no_email')
    user = User.query.filter_by(email=email).first()
    if not user:
        role = Role.query.filter_by(name='customer').first()
        if not role:
            return redirect(_frontend_url() + '?auth_error=config')
        user = User(name=name, email=email, role_id=role.id, must_change_password=False)
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.commit()
    if getattr(user, 'status', 'active') != 'active':
        return redirect(_frontend_url() + '?auth_error=blocked')
    login_user(user)
    return redirect(_frontend_url() + '?oauth=github')


def _frontend_url():
    from app.utils.urls import get_frontend_url
    return get_frontend_url()


# ---------- Example: POST with validation ----------
@api_bp.route('/echo', methods=['POST'])
def echo():
    """POST /api/echo - Echo back JSON body (for testing)"""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'success': False, 'error': 'Send JSON body'}), 400
    return jsonify({'success': True, 'echo': data})
