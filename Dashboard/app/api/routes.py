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
    Component, ComponentCategory, VendorComponent, PcBuild, BuildComponent, Cart, CartItem
)
from app.models.order import sync_master_order_status_from_vendor_orders
from app.utils.email_helper import send_email, send_registration_verification_email
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


from app.yolo_weights import clear_yolo_model_cache, get_yolo_model, resolve_model_path


def _detection_model_path(force_refresh: bool = False) -> Path:
    """Dynamic path: vendor dashboard/models/best.pt (see app/yolo_weights.py)."""
    if force_refresh:
        clear_yolo_model_cache()
    return resolve_model_path()


# Fallback class map — used only if best.pt carries no .names metadata.
CLASS_NAMES = {0: 'mouse', 1: 'keyboard', 2: 'monitor', 3: 'ram'}


def _resolve_model_class_names(model) -> dict:
    """Prefer the trained model's own class map; fall back to CLASS_NAMES.

    Reading model.names keeps labels correct even if best.pt is retrained with a
    different class order — a hardcoded {0:mouse,...} silently mislabels then.
    """
    names = getattr(model, 'names', None)
    if isinstance(names, dict) and names:
        return {int(k): str(v) for k, v in names.items()}
    if isinstance(names, (list, tuple)) and names:
        return {i: str(v) for i, v in enumerate(names)}
    return dict(CLASS_NAMES)


def _component_name(class_id, names=None):
    table = names or CLASS_NAMES
    return table.get(class_id, CLASS_NAMES.get(class_id, f'class_{class_id}'))


# --- YOLO → components DB bridge -------------------------------------------
# Detected label (lowercase) -> components category name. Match by category NAME,
# not id: the catalog has duplicate categories (e.g. 'Mouse' at id 14 and 18).
DETECTION_CATEGORY_MAP = {
    'mouse': 'Mouse',
    'keyboard': 'Keyboard',
    'monitor': 'Monitor',
    'ram': 'RAM',
    # PC-internal classes (best.pt v2) -> catalog category names (genspark_erp)
    'cpu': 'Processor',
    'cpu_cooler': 'Cooling',
    'gpu': 'GPU',
    'motherboard': 'Motherboard',
    'psu': 'PSU',
    'ram_stick': 'RAM',
    'disk_drive': 'Storage',
    'optical_drive': 'Storage',
}
# Slot/region classes the detector learned that are NOT sellable products
# (they describe a part of a board/case) — never surfaced as components.
NON_PRODUCT_CLASSES = {'gpu_slot', 'ram_slot', 'front_panel', 'rear_io'}
# Prettier display labels (fallback: title-cased class name).
DETECTION_DISPLAY_NAMES = {
    'cpu': 'CPU',
    'cpu_cooler': 'CPU Cooler',
    'gpu': 'GPU',
    'motherboard': 'Motherboard',
    'psu': 'Power Supply (PSU)',
    'ram_stick': 'RAM',
    'disk_drive': 'Storage Drive',
    'optical_drive': 'Optical Drive',
}
# Short educational blurb per part — shown with the detection so users learn what
# the hardware is (FYP req: "display ... relevant information to assist users in
# recognizing PC hardware").
COMPONENT_INFO = {
    'cpu': "Processor — the PC's brain that runs all instructions. Key specs: cores/threads, clock speed (GHz).",
    'cpu_cooler': 'CPU cooler — keeps the processor from overheating (air tower or liquid AIO). Key specs: type, fan/radiator size.',
    'gpu': 'Graphics card — renders games, video and 3D. Key specs: model (e.g. RTX 4060), VRAM (GB).',
    'motherboard': 'Motherboard — the main board every part plugs into. Key specs: CPU socket, chipset, form factor (ATX/mATX).',
    'psu': 'Power Supply (PSU) — feeds clean power to the whole PC. Key specs: wattage (W), 80+ efficiency rating.',
    'ram_stick': 'Memory (RAM) — fast temporary storage for running apps. Key specs: capacity (GB), type (DDR4/DDR5), speed (MHz).',
    'disk_drive': 'Storage drive — holds your OS, apps and files (SSD/HDD). Key specs: capacity, interface (NVMe/SATA).',
    'optical_drive': 'Optical drive — reads/writes CDs, DVDs or Blu-ray discs.',
}
# Rank rows within a category: a name that actually mentions the part beats one
# that only shares the (sometimes mis-assigned) category.
DETECTION_NAME_KEYWORDS = {
    'mouse': ('mouse',),
    'keyboard': ('keyboard',),
    'monitor': ('monitor', 'display', 'inch'),
    'ram': ('ram', 'ddr', 'dimm'),
    'cpu': ('ryzen', 'core', 'intel', 'amd', 'processor'),
    'cpu_cooler': ('cooler', 'cooling', 'fan', 'aio', 'heatsink'),
    'gpu': ('rtx', 'gtx', 'radeon', 'geforce', 'graphics'),
    'motherboard': ('motherboard', 'b550', 'b650', 'x670', 'z790', 'atx', 'chipset'),
    'psu': ('psu', 'power', 'watt', '80+', 'gold', 'bronze'),
    'ram_stick': ('ram', 'ddr', 'dimm'),
    'disk_drive': ('ssd', 'hdd', 'nvme', 'storage'),
    'optical_drive': ('dvd', 'optical', 'blu-ray'),
}
DETECTION_MATCH_LIMIT = 3


def _catalog_matches_for_label(label):
    """Top-N in-stock components for a detected part (stock > 0), most relevant first."""
    key = (label or '').strip().lower()
    category = DETECTION_CATEGORY_MAP.get(key)
    if not category:
        return []
    rows = (
        Component.query
        .join(ComponentCategory, Component.category_id == ComponentCategory.id)
        .filter(func.lower(ComponentCategory.name) == category.lower())
        .filter(Component.stock > 0)
        .all()
    )

    # Keep only components an approved vendor can actually fulfil — otherwise the
    # add-to-cart endpoint rejects them and the user gets a dead 'Add' button.
    ids = [c.id for c in rows]
    if ids:
        addable = {
            cid
            for (cid,) in (
                db.session.query(VendorComponent.component_id)
                .join(Vendor, Vendor.id == VendorComponent.vendor_id)
                .filter(
                    Vendor.approval_status == 'approved',
                    VendorComponent.quantity >= 1,
                    VendorComponent.component_id.in_(ids),
                )
                .distinct()
                .all()
            )
        }
        rows = [c for c in rows if c.id in addable]

    keywords = DETECTION_NAME_KEYWORDS.get(key, ())

    def _rank(c):
        name = (c.name or '').lower()
        name_hit = 0 if any(kw in name for kw in keywords) else 1
        return (name_hit, -(int(c.stock or 0)), float(c.price or 0))

    rows.sort(key=_rank)
    return [
        {
            'id': c.id,
            'name': c.name,
            'category': category,
            'price': float(c.price or 0),
            'stock': int(c.stock or 0),
            'image_url': c.image_url,
        }
        for c in rows[:DETECTION_MATCH_LIMIT]
    ]


def _attach_catalog_matches(detections):
    """Enrich confirmed detections in place with `matches` (real in-stock DB rows).

    Detection never fails because of the DB: on any error, matches stay empty.
    """
    for det in detections:
        det.setdefault('matches', [])
        det.setdefault('match_count', 0)

    cache = {}
    for det in detections:
        if det.get('type') == 'UNKNOWN':
            continue
        label = str(det.get('class_name') or '').strip().lower()
        if not label:
            continue
        if label not in cache:
            try:
                cache[label] = _catalog_matches_for_label(label)
            except Exception:
                try:
                    current_app.logger.exception('catalog match failed for %s', label)
                except RuntimeError:
                    pass
                cache[label] = []
        det['matches'] = cache[label]
        det['match_count'] = len(cache[label])
        if cache[label]:
            det['catalog_category'] = DETECTION_CATEGORY_MAP.get(label)


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
DISPLAY_CONFIRM_CONFIDENCE_PCT = float(os.getenv('GENSPARK_DISPLAY_CONF_THRESHOLD', '45'))


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


def _boxes_to_detections(result, img_w, img_h, names=None):
    """Build API detection list from an Ultralytics result object."""
    detections = []
    boxes = getattr(result, 'boxes', None)
    if boxes is None or len(boxes) == 0:
        return detections

    for box in boxes:
        class_id = int(box.cls[0])
        conf01 = float(box.conf[0])
        confidence_pct = round(conf01 * 100, 2)
        component = _component_name(class_id, names)

        # Skip slot/region classes (gpu_slot, ram_slot, …) — not sellable components.
        if component.strip().lower() in NON_PRODUCT_CLASSES:
            continue
        display_name = DETECTION_DISPLAY_NAMES.get(
            component.strip().lower(), component.replace('_', ' ').title()
        )

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
            'info': COMPONENT_INFO.get(component.strip().lower(), ''),
        }
        if confidence_pct < DISPLAY_CONFIRM_CONFIDENCE_PCT:
            detections.append({
                **common,
                'type': 'UNKNOWN',
                'name': 'Unknown Component',
                'spec': f'Below {DISPLAY_CONFIRM_CONFIDENCE_PCT:.0f}% certainty — not labeled as a trained part',
                'confidence': confidence_pct,
                'rawGuess': display_name,
            })
        else:
            detections.append({
                **common,
                'type': component.upper(),
                'name': display_name,
                'spec': f'{confidence_pct}% confidence',
                'confidence': confidence_pct,
            })
    return detections


def _run_yolo_detection(image_source, confidence=0.35):
    """
    Run YOLO on a file path or PIL Image (webcam base64 / multipart upload).
    """
    import numpy as np
    from PIL import Image as PILImage

    # Always defined (fixes UnboundLocalError if legacy CLI/fallback code paths exist)
    model_path = resolve_model_path()

    try:
        model, model_path = get_yolo_model()
        names = _resolve_model_class_names(model)
        if isinstance(image_source, PILImage.Image):
            img_w, img_h = image_source.size
            # ndarray is more reliable than PIL on headless Linux (Railway)
            source = np.asarray(image_source.convert('RGB'))
        else:
            source = str(image_source)
            img_w, img_h = _read_image_pixel_size(Path(source))

        results = model.predict(source=source, conf=confidence, verbose=False)
        if not results:
            return {
                'detections': [],
                'model': str(model_path),
                'output_dir': '',
                'image_width': img_w,
                'image_height': img_h,
            }, None

        r0 = results[0]
        if (not img_w or not img_h) and getattr(r0, 'orig_shape', None):
            img_h, img_w = int(r0.orig_shape[0]), int(r0.orig_shape[1])

        detections = _boxes_to_detections(r0, img_w, img_h, names)
        return {
            'detections': detections,
            'model': str(model_path),
            'output_dir': '',
            'image_width': img_w,
            'image_height': img_h,
        }, None
    except ImportError:
        return None, _public_detection_error(
            'Ultralytics is not installed. Run: pip install ultralytics'
        )
    except FileNotFoundError as exc:
        return None, _public_detection_error(str(exc))
    except Exception as exc:
        return None, _public_detection_error(str(exc))


@api_bp.route('/detect/component', methods=['POST'])
def detect_component():
    """
    YOLO detect from multipart file, JSON base64, or form data URL (webcam / upload).
    """
    from app.detect_image_input import parse_confidence, parse_request_image

    try:
        pil_image, parse_error = parse_request_image()
        if parse_error:
            return jsonify({'success': False, 'error': parse_error}), 400
        if pil_image is None:
            return jsonify({'success': False, 'error': 'No valid image data or file received.'}), 400

        confidence = parse_confidence()
        payload, error = _run_yolo_detection(pil_image, confidence=confidence)
        if error:
            return jsonify({'success': False, 'error': error}), 500

        # Bridge: attach real, in-stock components from the DB to each detection.
        _attach_catalog_matches(payload['detections'])

        return jsonify({
            'success': True,
            'count': len(payload['detections']),
            'detections': payload['detections'],
            'resolved_count': sum(d.get('match_count', 0) for d in payload['detections']),
            'model': payload['model'],
            'output_dir': payload.get('output_dir', ''),
            'image_width': payload.get('image_width'),
            'image_height': payload.get('image_height'),
        })
    except Exception as exc:
        try:
            current_app.logger.exception('detect_component failed')
        except RuntimeError:
            pass
        return jsonify({
            'success': False,
            'error': _public_detection_error(str(exc)),
        }), 500


@api_bp.route('/detect/model', methods=['GET'])
def detect_model_info():
    """Return the YOLO weights path the API would use (no inference)."""
    p = _detection_model_path()
    loaded = False
    try:
        get_yolo_model()
        loaded = True
    except Exception:
        loaded = False
    return jsonify({
        'success': True,
        'model': str(p),
        'exists': p.exists(),
        'loaded': loaded,
        'api_version': 2,
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

    clear_yolo_model_cache()
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
    total_amount = float(order.total_amount or 0)
    # Assembly isn't a separate column — it's the remainder of the stored total
    # after parts + shipping (kept consistent by the place-order/Stripe endpoints).
    assembly_fee = max(0.0, round(total_amount - items_subtotal - shipping_fee, 2))
    vendor_orders = VendorOrder.query.filter_by(order_id=order.id).all()
    history = OrderStatusHistory.query.filter_by(order_id=order.id).order_by(OrderStatusHistory.created_at.asc()).all()
    return jsonify({
        'success': True,
        'order': {
            'id': order.id,
            'order_number': order.order_number or str(order.id),
            'items_subtotal': items_subtotal,
            'shipping_fee': shipping_fee,
            'assembly_fee': assembly_fee,
            'total_amount': total_amount,
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
    # Assembly service fee — same rule/amount as the configurator (CPU + motherboard
    # present ⇒ a full PC to assemble). Order-level fee, like shipping.
    from app.services.fees import assembly_fee_for
    assembly_fee = assembly_fee_for([it['component_name'] for it in normalized])
    order_grand_total = float(grand_total) + shipping_fee + assembly_fee

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

    # High-priority WhatsApp + on-site: order confirmed (Order Success).
    try:
        from app.services.notification_service import notify_order_placed, notify_admin_new_order
        notify_order_placed(order)
        notify_admin_new_order(order)  # admins: new order awaiting approval
    except Exception as _e:
        print('notify order-placed skipped:', _e)

    return jsonify({
        'success': True,
        'message': 'Order placed successfully. Waiting for admin approval.',
        'order': {
            'id': order.id,
            'order_number': order.order_number,
            'status': order.status,
            'items_subtotal': float(grand_total),
            'shipping_fee': shipping_fee,
            'assembly_fee': assembly_fee,
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
    created_vendor_orders = []
    for vendor_id, items in vendor_buckets.items():
        v_order = VendorOrder(
            order_id=parent.id,
            vendor_id=vendor_id,
            status='assigned',
            total_amount=0,
        )
        db.session.add(v_order)
        db.session.flush()
        created_vendor_orders.append(v_order)

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

    try:
        from app.services.notification_service import notify_order_status, notify_vendor_order_assigned
        notify_order_status(parent, 'approved')
        # Notify each assigned vendor (the previously-missing vendor-facing alert).
        for vo in created_vendor_orders:
            notify_vendor_order_assigned(vo)
    except Exception as _e:
        print('notify approved skipped:', _e)

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
    try:
        from app.services.notification_service import notify_order_status
        notify_order_status(parent, 'rejected')
    except Exception as _e:
        print('notify rejected skipped:', _e)
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
                func.min(VendorComponent.price),
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
        # Track both the vendor count and the cheapest vendor price — the cart picks
        # the lowest-priced in-stock approved vendor, so this is what's really charged.
        vendor_summary = {
            cid: {'count': int(cnt), 'min_price': (float(mp) if mp is not None else None)}
            for cid, cnt, mp in rows
        }

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
            info = vendor_summary.get(c.id) or {}
            n = info.get('count', 0)
            row['vendors_with_stock'] = n
            row['has_vendor_stock'] = n > 0
            # effective_price = what the cart will actually charge (cheapest approved
            # vendor), falling back to the catalog price when no vendor has it.
            min_vp = info.get('min_price')
            row['effective_price'] = (
                min_vp if (min_vp is not None and min_vp > 0) else float(c.price or 0)
            )
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
    from app.utils.urls import PRODUCTION_VERIFY_EMAIL_API_BASE, build_verify_email_url

    return jsonify({
        'success': True,
        'auth_system': 'production_railway_v6',
        'change_password_handler': 'force_update_password',
        'password_update_path': '/api/force-update-password',
        'verify_email_base': PRODUCTION_VERIFY_EMAIL_API_BASE,
        'verify_email_sample': build_verify_email_url('deploy-check-sample'),
        'api_base': PRODUCTION_VERIFY_EMAIL_API_BASE,
        'message': 'Verify links and API must use api_base, never Vercel.',
    })


# ---------- Example: POST (create) ----------
@api_bp.route('/ping', methods=['GET', 'POST'])
def ping():
    """GET/POST /api/ping - Health check or echo JSON body"""
    if request.method == 'POST':
        body = request.get_json(silent=True) or {}
        return jsonify({'success': True, 'message': 'pong', 'received': body})
    return jsonify({
        'success': True,
        'message': 'pong',
        'api_build': 'force_update_password_v7',
    })


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
    from app.utils.rate_limit import login_key, is_locked_out, record_failure, record_success
    rl_key = login_key(request.remote_addr, email)
    if is_locked_out(rl_key):
        return jsonify({'success': False, 'error': 'Too many failed attempts. Please wait a few minutes and try again.'}), 429
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        record_failure(rl_key)
        return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
    if getattr(user, 'status', 'active') != 'active':
        msg = 'Account blocked'
        if getattr(user, 'status', None) == 'pending_email':
            msg = 'Please verify your email before logging in.'
        return jsonify({'success': False, 'error': msg}), 403
    record_success(rl_key)

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
    from app.utils.rate_limit import login_key, is_locked_out, record_failure, record_success
    rl_key = login_key(request.remote_addr, email)
    if is_locked_out(rl_key):
        return jsonify({'success': False, 'error': 'Too many failed attempts. Please wait a few minutes and try again.'}), 429
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        record_failure(rl_key)
        return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
    if getattr(user, 'status', 'active') != 'active':
        msg = 'Account blocked'
        if getattr(user, 'status', None) == 'pending_email':
            msg = 'Please verify your email before logging in.'
        return jsonify({'success': False, 'error': msg}), 403
    role_name = user.role_ref.name if getattr(user, 'role_ref', None) else 'customer'
    if role_name != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    record_success(rl_key)

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


def _update_password_from_email_otp(email, current_otp, new_password):
    """Shared logic: verify email + current OTP, set new password hash. No auth decorators."""
    if not email:
        return jsonify({'success': False, 'error': 'Email is required'}), 400
    if not current_otp or not new_password:
        return jsonify({'success': False, 'error': 'Current and new password required'}), 400
    if len(new_password) < 6:
        return jsonify({'success': False, 'error': 'New password must be at least 6 characters'}), 400

    from app.utils.jwt_session_bridge import find_user_by_email

    user = find_user_by_email(email)
    if not user:
        return jsonify({'success': False, 'error': 'No account found for this email'}), 404

    # Hardening: this endpoint has no auth decorator (it must work for the forced
    # first-login change before a session exists). To stop it being an account-takeover
    # vector, an UNAUTHENTICATED caller may only use it to complete a forced reset
    # (must_change_password set by registration / admin-add). Changing an established
    # account's password requires being signed in as that same account.
    from flask_login import current_user
    is_self = (
        current_user.is_authenticated
        and (getattr(current_user, 'email', '') or '').strip().lower() == email.strip().lower()
    )
    if not is_self and not getattr(user, 'must_change_password', False):
        return jsonify({
            'success': False,
            'error': 'Please sign in to change your password.',
        }), 403

    if not user.check_password(current_otp):
        return jsonify({
            'success': False,
            'error': 'Current password is wrong. Use the one-time password from registration or admin.',
        }), 400

    user.set_password(new_password)
    user.must_change_password = False
    db.session.commit()
    return jsonify({'success': True, 'message': 'Password updated'})


# ---------- Change password (legacy path — prefer /force-update-password) ----------
@api_bp.route('/change-password', methods=['POST', 'OPTIONS'])
def api_change_password():
    """POST /api/change-password — legacy; use /api/force-update-password on production."""
    if request.method == 'OPTIONS':
        r = make_response('', 204)
        r.headers['Access-Control-Max-Age'] = '86400'
        return r
    data = request.get_json(silent=True) or {}
    return _update_password_from_email_otp(
        (data.get('email') or '').strip(),
        data.get('current_password') or '',
        data.get('new_password') or '',
    )


# Open endpoint — no JWT/session; bypasses old production middleware on /change-password.
@api_bp.route('/force-update-password', methods=['POST', 'OPTIONS'])
def force_update_password():
    """POST /api/force-update-password — JSON { email, current_password, new_password }."""
    if request.method == 'OPTIONS':
        r = make_response('', 204)
        r.headers['Access-Control-Max-Age'] = '86400'
        return r
    data = request.get_json(silent=True) or {}
    return _update_password_from_email_otp(
        (data.get('email') or '').strip(),
        data.get('current_password') or '',
        data.get('new_password') or '',
    )


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
        return jsonify({
            'success': False,
            'error': 'Email already registered. Sign in with your password or use Forgot password if needed.',
        }), 409

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
        from app.utils.urls import (
            PRODUCTION_VERIFY_EMAIL_API_BASE,
            build_verify_email_url,
            _is_production_deploy,
        )
        verify_url = build_verify_email_url(token)
        if _is_production_deploy():
            verify_url = (
                f'{PRODUCTION_VERIFY_EMAIL_API_BASE.rstrip("/")}'
                f'/api/verify-email?token={token}'
            )
        send_registration_verification_email(
            to_email=user.email,
            name=user.name,
            one_time_password=one_time_password,
            verify_url=verify_url,
            role_type='vendor' if role_name == 'vendor' else 'user',
        )
    except Exception as mail_exc:
        current_app.logger.warning('Verification email not sent: %s', mail_exc)

    return jsonify({
        'success': True,
        'message': 'Registration successful. Please check your email to verify your account.',
        'one_time_password': one_time_password,
        'verification_url': verify_url,
    })


_SITE_LOGO_DATA_URI = None  # cached base64 data URI for the GenSpark Builds logo


def _site_logo_data_uri() -> str:
    """Return the GenSpark Builds logo as a base64 data URI (cached).

    Embedding makes the verification page self-contained so the logo shows even
    when the link is opened from an email, regardless of static-serving config.
    """
    global _SITE_LOGO_DATA_URI
    if _SITE_LOGO_DATA_URI is None:
        import base64
        try:
            logo_path = Path(current_app.static_folder) / 'img' / 'genspark-builds-logo.png'
            encoded = base64.b64encode(logo_path.read_bytes()).decode('ascii')
            _SITE_LOGO_DATA_URI = f'data:image/png;base64,{encoded}'
        except Exception:
            _SITE_LOGO_DATA_URI = ''  # fall back to text brand below
    return _SITE_LOGO_DATA_URI


def _verify_email_response_html(*, title: str, message: str, login_href: str, ok: bool = True):
    """Branded, on-theme account-verification page (GenSpark navy/blue)."""
    from flask import make_response
    primary, primary_dark = '#02457A', '#001B48'
    status = '#16a34a' if ok else '#dc2626'      # success green / error red
    icon = '&#10003;' if ok else '&#33;'          # ✓ / !
    logo_uri = _site_logo_data_uri()
    logo_block = (
        f'<img src="{logo_uri}" alt="GenSpark Builds">'
        if logo_uri else
        '<div class="brand">GENSPARK BUILDS<small>PC CUSTOMIZATION</small></div>'
    )
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} – GenSpark Builds</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box}}
body{{font-family:'Inter',system-ui,-apple-system,sans-serif;margin:0;min-height:100vh;display:flex;
  align-items:center;justify-content:center;padding:1.25rem;color:#0f172a;
  background:linear-gradient(135deg,#eef3fb 0%,#f6f8fc 45%,#eaf0fb 100%)}}
.card{{background:#fff;width:100%;max-width:460px;border-radius:18px;overflow:hidden;
  border:1px solid rgba(2,69,122,.08);box-shadow:0 24px 60px rgba(2,69,122,.18)}}
.head{{background:#ffffff;padding:1.25rem 2rem;display:flex;align-items:center;
  border-bottom:1px solid #eef2f7}}
/* Square PNG cropped to a horizontal strip — same trick as the site header (.logo-image). */
.head img{{display:block;width:210px;height:46px;object-fit:cover;object-position:center;max-width:100%}}
.brand{{color:{primary_dark};font-weight:800;font-size:1.05rem;letter-spacing:.05em;line-height:1.1}}
.brand small{{display:block;font-weight:500;font-size:.6rem;letter-spacing:.2em;opacity:.78;margin-top:2px}}
.body{{padding:2rem}}
.badge{{width:56px;height:56px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:1.7rem;font-weight:800;color:#fff;background:{status};margin-bottom:1.15rem;
  box-shadow:0 8px 20px {status}40}}
h1{{margin:0 0 .6rem;font-size:1.45rem;font-weight:800;color:{primary_dark};letter-spacing:-.01em}}
p{{margin:0 0 1.6rem;line-height:1.6;color:#475569;font-size:.95rem}}
p strong,p b{{color:{primary_dark};font-weight:700}}
a.btn{{display:inline-flex;align-items:center;gap:.5rem;padding:.8rem 1.6rem;border-radius:10px;
  color:#fff;text-decoration:none;font-weight:700;font-size:.95rem;
  background:linear-gradient(135deg,{primary} 0%,{primary_dark} 100%);
  box-shadow:0 8px 18px rgba(2,69,122,.32);transition:transform .15s ease,box-shadow .15s ease}}
a.btn:hover{{transform:translateY(-1px);box-shadow:0 12px 26px rgba(2,69,122,.42)}}
.foot{{padding:.9rem 2rem;border-top:1px solid #eef2f7;color:#94a3b8;font-size:.74rem;text-align:center;letter-spacing:.02em}}
</style></head><body>
<div class="card">
  <div class="head">
    {logo_block}
  </div>
  <div class="body">
    <div class="badge">{icon}</div>
    <h1>{title}</h1>
    <p>{message}</p>
    <a class="btn" href="{login_href}">Continue to login &#8594;</a>
  </div>
  <div class="foot">&copy; GenSpark Builds &middot; Secure account verification</div>
</div>
</body></html>"""
    return make_response(html, 200 if ok else 400)


@api_bp.route('/verify-email', methods=['GET'])
def api_verify_email():
    """GET /api/verify-email?token=... - mark user email as verified."""
    from app.utils.urls import get_api_base_url, get_frontend_url

    wants_html = request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'text/html'
    frontend_login = f'{get_frontend_url()}/?login=1&email_verified=1'
    flask_login = f'{get_api_base_url()}/auth/login'

    token = request.args.get('token', '')
    if not token:
        if wants_html:
            return _verify_email_response_html(
                title='Missing link',
                message='This verification link is incomplete. Register again or copy the full link from the app.',
                login_href=frontend_login,
                ok=False,
            )
        return jsonify({'success': False, 'error': 'Missing token'}), 400
    try:
        email = _confirm_email_token(token)
    except SignatureExpired:
        if wants_html:
            return _verify_email_response_html(
                title='Link expired',
                message='This verification link has expired (24 hours). Please register again or ask an admin to activate your account.',
                login_href=frontend_login,
                ok=False,
            )
        return jsonify({'success': False, 'error': 'Verification link expired'}), 400
    except BadSignature:
        if wants_html:
            return _verify_email_response_html(
                title='Invalid link',
                message='This verification link is invalid. Use the link from your registration screen or register again.',
                login_href=frontend_login,
                ok=False,
            )
        return jsonify({'success': False, 'error': 'Invalid verification link'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        if wants_html:
            return _verify_email_response_html(
                title='User not found',
                message='No account exists for this link. Try registering again on the same server (127.0.0.1:5000).',
                login_href=frontend_login,
                ok=False,
            )
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if (user.status or '').lower() != 'active':
        user.status = 'active'
        db.session.commit()

    if wants_html:
        return _verify_email_response_html(
            title='Email verified',
            message=(
                f'Your email <strong>{email}</strong> is verified. '
                'Sign in with your <strong>one-time password</strong> from registration, then set a new password.'
            ),
            login_href=frontend_login,
            ok=True,
        )

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


@api_bp.route('/contact', methods=['POST'])
def contact():
    """POST /api/contact - Landing page contact form. Emails the support inbox."""
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    message = (data.get('message') or '').strip()
    if not name or not email or not message:
        return jsonify({'success': False, 'error': 'Name, email, and message are required'}), 400

    phone = (data.get('phone') or '').strip()
    subject = (data.get('subject') or 'other').strip()
    support_inbox = current_app.config.get('SUPPORT_EMAIL', 'support@gensparkbuilds.com')

    body = (
        f"New contact form submission\n\n"
        f"Name: {name}\nEmail: {email}\nPhone: {phone or '-'}\nSubject: {subject}\n\n"
        f"Message:\n{message}\n"
    )
    sent = send_email(support_inbox, f'GenSpark contact form: {subject}', body)
    if not sent:
        current_app.logger.warning('Contact form received but email not sent (MAIL_SERVER not configured): %s', email)
    return jsonify({'success': True})
