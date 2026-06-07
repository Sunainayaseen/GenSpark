"""
GenSpark Intelligent PC Builder API (OpenAI ChatGPT)
==================================================
Vite React contract:
  POST /api/recommend-build   { message?, build_requested?, detected_part | detected_parts, budget?, purpose? }
  POST /api/create-build      { cpu, gpu, motherboard, ram, storage, psu, case, user_id?, status? }
  POST /api/detect/component  multipart `image` or JSON/base64 image
"""
from __future__ import annotations

import io
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path


def _force_utf8_stdio() -> None:
    """Windows consoles default to cp1252; Gemini emojis in logs must not crash the API."""
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    for name in ('stdout', 'stderr'):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, 'reconfigure', None)
        if callable(reconfigure):
            try:
                reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass
        elif hasattr(stream, 'buffer'):
            try:
                setattr(
                    sys,
                    name,
                    io.TextIOWrapper(
                        stream.buffer,
                        encoding='utf-8',
                        errors='replace',
                        line_buffering=True,
                    ),
                )
            except Exception:
                pass


_force_utf8_stdio()

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
from mysql.connector import Error as MySQLError

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
# override=True: load backend/.env over stale OS-level env vars
load_dotenv(APP_DIR / '.env', override=True)

from chat_intelligence import analyze_user_message, unknown_help_markdown  # noqa: E402
from configurator import (  # noqa: E402
    advanced_pc_configurator,
    configurator_to_parts_payload,
    format_configurator_markdown,
)
from stripe_checkout import (  # noqa: E402
    complete_checkout as stripe_complete_checkout,
    create_payment_intent as stripe_create_payment_intent,
    stripe_config_status,
    stripe_configured,
)
from auth_api import register_auth_routes  # noqa: E402

import stripe as stripe_sdk  # noqa: E402

# Debug: Verify STRIPE_SECRET_KEY is loaded
stripe_key = os.environ.get('STRIPE_SECRET_KEY')
print(f'(GenSpark) STRIPE_SECRET_KEY loaded: {stripe_key[:10] if stripe_key else "None"}...')
stripe_sdk.api_key = stripe_key


def _resolve_openai_api_key() -> str:
    return (os.getenv('OPENAI_API_KEY') or '').strip()


OPENAI_API_KEY = _resolve_openai_api_key()

_OPENAI_KEY_PLACEHOLDERS = frozenset({
    'sk-proj-your-openai-key-here',
    'your-openai-api-key-here',
    'sk-your-openai-key-here',
})


def _openai_is_configured() -> bool:
    key = OPENAI_API_KEY.strip()
    if not key:
        return False
    normalized = key.lower()
    if normalized in _OPENAI_KEY_PLACEHOLDERS:
        return False
    if 'your-openai' in normalized or 'key-here' in normalized:
        return False
    return key.startswith('sk-') and len(key) >= 20


def _resolve_ai_provider() -> str:
    """OpenAI only — requires OPENAI_API_KEY in backend/.env."""
    return 'openai' if _openai_is_configured() else 'none'


def _rule_engine_enabled() -> bool:
    """Default on: fast deterministic builds (no LLM). Set GENSPARK_RULE_ENGINE=0 to use OpenAI."""
    raw = (os.getenv('GENSPARK_RULE_ENGINE', '1') or '1').strip().lower()
    return raw not in ('0', 'false', 'no', 'off')


def _live_model_id(_provider: str = 'openai') -> str:
    return os.getenv('OPENAI_MODEL', 'gpt-4o-mini')


OPENAI_BUILD_SYSTEM_INSTRUCTION = """You are GenSpark AI Desktop Engineering Core — expert PC architect for Pakistan (PKR).

RUNTIME (authoritative):
- Budget: {budget}
- Purpose: {purpose}
- Vision detected parts: {detected_part}

RULES:
1. At the top, print these badges on separate lines:
   - 🟢 **Compatibility Status:** [socket/chipset validation summary]
   - ⚡ **PSU Wattage Buffer:** [CPU+GPU TDP + ~100W headroom vs recommended PSU]
   - 🏆 **GenSpark Performance Score:** [0-100]
   - 💰 **Value For Money Rating:** ⭐⭐⭐⭐⭐ (adjust stars to fit budget tier)
2. Total component prices MUST NOT exceed the stated budget.
3. If detected parts are not "None", set owned peripheral rows to price 0 and include in ## Summary exactly:
   "Based on our hardware vision analytics, we have excluded [{detected_part}] from your invoice list to optimize core hardware headroom!"
4. Office builds may use integrated graphics; Gaming/Editing prioritize discrete GPU within budget.

OUTPUT — valid Markdown only, in this order:
### Summary
2-4 sentences.

### Recommended Components
{table_columns}
{table_separator}
Exactly seven rows in order (no extra rows):
CPU
GPU
Motherboard
RAM
Storage
PSU
Case
Columns: Component Type | Component Name | Estimated Price — price cells are plain integers only (no "PKR" in cells).

### 🧠 GenSpark AI Reasoning
3-5 bullets: why this build, expected FPS/resolution or office workload fit.

No JSON. No code fences."""


# Vite dev servers + production (extend via GENSPARK_CORS_ORIGINS)
DEFAULT_CORS_ORIGINS = [
    'https://genspark-frontend.vercel.app',
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:4173',
    'http://127.0.0.1:4173',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

BUILD_TABLE_COLUMNS = '| Component Type | Component Name | Estimated Price |'
BUILD_TABLE_SEPARATOR = '|----------------|-----------------|------------------|'
BUILD_REQUIRED_TYPES = ('CPU', 'GPU', 'Motherboard', 'RAM', 'Storage', 'PSU', 'Case')

OWNED_PERIPHERAL_LABELS = frozenset({'mouse', 'keyboard', 'monitor'})

# Frontend create-build keys → DB column + products.category filter
BUILD_PART_SLOTS = (
    ('cpu', 'cpu_id', 'CPU'),
    ('gpu', 'gpu_id', 'GPU'),
    ('motherboard', 'motherboard_id', 'Motherboard'),
    ('ram', 'ram_id', 'RAM'),
    ('storage', 'storage_id', 'Storage'),
    ('psu', 'psu_id', 'PSU'),
    ('case', 'case_id', 'Case'),
)

REQUIRED_PART_KEYS = tuple(slot[0] for slot in BUILD_PART_SLOTS)

DISPLAY_CONFIRM_CONFIDENCE_PCT = float(os.getenv('GENSPARK_DISPLAY_CONF_THRESHOLD', '60'))
CLASS_NAMES = {0: 'mouse', 1: 'keyboard', 2: 'monitor', 3: 'ram'}
MODEL_PATH = APP_DIR / 'best.pt'
_yolo_model = None


def _cors_origins() -> list[str]:
    origins = list(DEFAULT_CORS_ORIGINS)
    extra = os.getenv('GENSPARK_CORS_ORIGINS', '')
    for item in extra.split(','):
        item = item.strip()
        if item and item not in origins:
            origins.append(item)
    # Hugging Face Docker Space — allow this Space + Vercel callers
    space_id = (os.getenv('SPACE_ID') or '').strip()
    if space_id:
        slug = space_id.replace('/', '-').lower()
        hf_origin = f'https://{slug}.hf.space'
        if hf_origin not in origins:
            origins.append(hf_origin)
    return origins


app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'genspark-dev-session-key')

# Global CORS — allows Vite preflight (OPTIONS) from localhost:5173 and credentials
CORS(
    app,
    resources={r'/*': {'origins': _cors_origins()}},
    supports_credentials=True,
    allow_headers=['Content-Type', 'Authorization', 'X-Requested-With', 'Accept'],
    methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    expose_headers=['Content-Type'],
    max_age=86400,
    intercept_exceptions=True,
)

UPLOAD_DIR = APP_DIR / 'uploads'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
COMPONENT_UPLOAD_DIR = UPLOAD_DIR / 'components'
COMPONENT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Serve admin component images and other files under backend/uploads/."""
    return send_from_directory(UPLOAD_DIR, filename)


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------
def _json_error(message: str, status: int = 400, **extra):
    body = {'success': False, 'error': message}
    body.update(extra)
    return jsonify(body), status


def _json_ok(http_status: int = 200, **payload):
    """Return JSON success. Use http_status for the HTTP code (not a body field named status)."""
    body = {'success': True}
    body.update(payload)
    return jsonify(body), http_status


def _parse_json_body() -> dict:
    """Always returns a dict — never raises on missing keys."""
    if not request.is_json:
        return {}
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _parse_budget_pkr(raw) -> int | None:
    if raw is None:
        return None
    digits = re.sub(r'[^\d]', '', str(raw))
    return int(digits) if digits else None


def _normalize_part_label(item: str) -> str:
    """Title-case YOLO class names; preserve longer product names as given."""
    cleaned = re.sub(r'\s+', ' ', (item or '').strip())
    if not cleaned:
        return ''
    key = cleaned.lower()
    if key in OWNED_PERIPHERAL_LABELS or key == 'ram':
        return key.upper() if key == 'ram' else cleaned.title()
    return cleaned


def _parse_detected_parts(raw) -> list[str]:
    """
    Accept a list, or a comma/semicolon/pipe-separated string.
    Returns deduplicated labels in stable order.
    """
    if raw is None:
        return []

    if isinstance(raw, list):
        items = [str(x) for x in raw]
    elif isinstance(raw, str):
        text = raw.strip()
        if not text or text.lower() == 'none':
            return []
        items = re.split(r'[,;|]+', text)
    else:
        items = [str(raw)]

    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        label = _normalize_part_label(str(item))
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(label)
    return result


def _format_detected_parts_display(parts: list[str]) -> str:
    return ', '.join(parts) if parts else 'None'


_GREETING_FRAGMENTS = (
    'hi',
    'hello',
    'help me',
    'help',
    'hey',
    'aoa',
    'salam',
    'assalam',
    'assalam o alaikum',
    'salam alaikum',
    'kia hal',
    'kia hal ha',
    'kia hal hai',
    'kya hal',
    'kaise ho',
    'kaise hain',
    'how are you',
    'how r u',
    'yo',
    'sup',
)

_PURPOSE_HINTS = (
    ('gaming', 'Gaming'),
    ('pubg', 'Gaming'),
    ('gta', 'Gaming'),
    ('office', 'Office'),
    ('excel', 'Office'),
    ('productivity', 'Office'),
    ('school', 'Office'),
    ('editing', 'Editing'),
    ('video edit', 'Editing'),
    ('rendering', 'Editing'),
    ('render', 'Editing'),
    ('blender', 'Editing'),
    ('photoshop', 'Editing'),
    ('streaming', 'Gaming'),
    ('rigid', 'Gaming'),
    ('rigid build', 'Gaming'),
    ('play', 'Gaming'),
    ('pc build', 'Gaming'),
    ('gaming pc', 'Gaming'),
    ('coding', 'Coding'),
    ('programming', 'Coding'),
    ('content creation', 'Content Creation'),
)


def _infer_purpose_from_text(text: str) -> str | None:
    """
    Priority tiers — office/editing before gaming so 'rigid setup' + 'office work'
    does not become Gaming because of the word rigid alone.
    """
    lower = (text or '').lower()
    if not lower.strip():
        return None

    office_markers = (
        'office',
        'study',
        'excel',
        'typing',
        'productivity',
        'school',
        'documents',
        'word',
        'corporate',
    )
    if any(tag in lower for tag in office_markers):
        return 'Office'
    if re.search(r'\boffice\s+work\b|\bwork\s+office\b', lower):
        return 'Office'
    if 'office' in lower and re.search(r'\bwork\b|kaam|k\s+liye|ke\s+liye', lower):
        return 'Office'

    if any(
        tag in lower
        for tag in (
            'editing',
            'video edit',
            'rendering',
            'blender',
            'photoshop',
            'premiere',
            'davinci',
            'after effects',
        )
    ) or re.search(r'\bedit(?:ing)?\b|\brender(?:ing)?\b', lower):
        return 'Editing'

    if any(
        tag in lower
        for tag in ('gaming', 'pubg', 'gta', 'valorant', 'fortnite', 'esports', 'game', 'play')
    ):
        return 'Gaming'
    if re.search(r'\brigid\s+(?:build|setup|pc|rig)\b', lower) or 'rigid build' in lower:
        return 'Gaming'
    if 'gaming pc' in lower or 'gaming setup' in lower:
        return 'Gaming'

    for needle, label in _PURPOSE_HINTS:
        if needle in ('rigid', 'rigid build', 'play', 'game'):
            continue
        if needle in lower:
            return label

    return None


def _infer_budget_from_text(text: str) -> str | None:
    """Parse chat: 1.20 lakh, 120k, 150000 PKR, etc."""
    raw = (text or '').strip()
    if not raw:
        return None
    lower = raw.lower().replace(',', '')

    lakh_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|lacs)\b', lower)
    if lakh_match:
        return f'{int(float(lakh_match.group(1)) * 100_000)} PKR'

    dot_lakh = re.search(r'(\d+\.\d{1,2})(?:\s*(?:lakh|lac|budget|hai|me))', lower)
    if dot_lakh:
        return f'{int(float(dot_lakh.group(1)) * 100_000)} PKR'

    k_match = re.search(r'(\d{2,3})\s*k\b', lower)
    if k_match:
        return f'{int(k_match.group(1)) * 1000} PKR'

    num_match = re.search(r'\b(\d{5,7})\b', lower)
    if num_match:
        return f'{int(num_match.group(1))} PKR'
    return None


def _is_conversational_only_message(message: str) -> bool:
    """Greetings / vague help without budget or purpose signals in the message itself."""
    msg = re.sub(r'\s+', ' ', (message or '').strip().lower())
    if not msg:
        return True
    cleaned_alpha = re.sub(r'[^\w]', '', msg)
    if 0 < len(cleaned_alpha) <= 3:
        return True
    if _infer_budget_from_text(message) or _infer_purpose_from_text(message):
        return False
    if re.search(r'\b(build|setup|rig|budget|lakh|lac|\d{4,})\b', msg):
        return False
    if any(msg == frag or msg.startswith(frag + ' ') or msg.endswith(' ' + frag) for frag in _GREETING_FRAGMENTS):
        return True
    if not any(fragment in msg for fragment in _GREETING_FRAGMENTS):
        return False
    cleaned = re.sub(r'[^\w\s]', '', msg)
    return len(cleaned.split()) <= 6


def _generate_greeting_markdown() -> str:
    return """### 👋 Hello! Welcome to GenSpark Builds AI Assistant

Yes, I can absolutely help you design and engineer the perfect custom PC setup.

To initialize my building framework, please let me know:
1. 💰 **Your target budget** (e.g. *1.20 lakh budget*, *120k*, or *150000 PKR*)
2. 🛠️ **Your primary deployment purpose** (e.g. *Gaming build*, *Video editing*, or *Office tasking*)

Our vision system can detect parts you already own (mouse, keyboard, monitor, RAM) and exclude them from your quote."""


def _extract_recommend_payload(data: dict) -> dict:
    """
    Vite React payload (builderApi.js):
      { message?, build_requested?, detected_part | detected_parts, budget?, purpose? }
    Defaults budget/purpose only when a build is explicitly requested.
    """
    detected_raw = (
        data.get('detected_parts')
        if data.get('detected_parts') is not None
        else data.get('detectedParts')
    )
    if detected_raw is None:
        detected_raw = data.get('detected_part', data.get('detectedPart', 'None'))

    detected_parts = _parse_detected_parts(detected_raw)
    detected_part = _format_detected_parts_display(detected_parts)

    message = str(data.get('message') or data.get('user_message') or '').strip()
    build_requested = bool(data.get('build_requested') or data.get('buildRequested'))

    budget_raw = data.get('budget')
    purpose_raw = data.get('purpose', data.get('use_case', data.get('useCase')))

    budget_explicit = budget_raw is not None and str(budget_raw).strip() != ''
    purpose_explicit = purpose_raw is not None and str(purpose_raw).strip() != ''

    if message and not budget_explicit:
        inferred_budget = _infer_budget_from_text(message)
        if inferred_budget:
            budget_explicit = True
            budget_raw = inferred_budget

    if message and not purpose_explicit:
        inferred = _infer_purpose_from_text(message)
        if inferred:
            purpose_explicit = True
            purpose_raw = inferred

    greeting_only = bool(message) and _is_conversational_only_message(message)
    # Greetings ignore stale panel budget/purpose from the client unless user clicked Get recommendations.
    if greeting_only and not build_requested:
        want_build = False
    else:
        has_build_signals = build_requested or budget_explicit or purpose_explicit
        want_build = bool(has_build_signals)

    budget_str = ''
    purpose_str = ''
    if want_build:
        budget_str = str(budget_raw).strip() if budget_raw is not None else ''
        if not budget_str:
            budget_num = data.get('budget_pkr') or data.get('budgetPkr')
            if budget_num is not None:
                budget_str = f'{_parse_budget_pkr(budget_num) or budget_num} PKR'
            else:
                budget_str = '100000 PKR'

        purpose_str = str(purpose_raw).strip() if purpose_raw is not None else ''
        if not purpose_str:
            purpose_str = 'Gaming'

    return {
        'detected_part': detected_part,
        'detected_parts': detected_parts,
        'budget': budget_str,
        'purpose': purpose_str,
        'message': message,
        'build_requested': build_requested,
        'want_build': want_build,
    }


def _sanitize_like_term(name: str) -> str:
    """Escape LIKE wildcards; keep a clean substring for %term% queries."""
    cleaned = re.sub(r'\s+', ' ', (name or '').strip())
    cleaned = cleaned.replace('\\', '\\\\').replace('%', r'\%').replace('_', r'\_')
    return cleaned


def _extract_create_build_parts(data: dict) -> dict[str, str]:
    """
    Accept flat Vite payload or nested { parts: { cpu: "...", ... } }.
    Keys: cpu, gpu, motherboard, ram, storage, psu, case
    """
    nested = data.get('parts')
    source = nested if isinstance(nested, dict) else data

    parts: dict[str, str] = {}
    for key in REQUIRED_PART_KEYS:
        raw = source.get(key, source.get(key.capitalize()))
        if raw is None and key == 'case':
            raw = source.get('chassis')
        if raw is None:
            continue
        name = str(raw).strip()
        if name:
            parts[key] = name
    return parts


# ---------------------------------------------------------------------------
# MySQL — local .env (DB_*) or Railway / Hugging Face (MYSQL_* / MYSQLHOST)
# ---------------------------------------------------------------------------
def _env_first(*keys: str, default: str = '') -> str:
    for key in keys:
        raw = os.getenv(key)
        if raw is not None and str(raw).strip() != '':
            return str(raw).strip()
    return default


def resolve_db_config() -> dict[str, str | int]:
    """
    Supports:
      Local: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
      HF guide: MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
      Railway: MYSQLHOST, MYSQLPORT, MYSQLUSER, MYSQLPASSWORD, MYSQLDATABASE
    """
    host = _env_first(
        'DB_HOST', 'MYSQL_HOST', 'MYSQLHOST', default='localhost'
    )
    port_raw = _env_first('DB_PORT', 'MYSQL_PORT', 'MYSQLPORT', default='3306')
    user = _env_first('DB_USER', 'MYSQL_USER', 'MYSQLUSER', default='root')
    password = _env_first(
        'DB_PASSWORD', 'MYSQL_PASSWORD', 'MYSQLPASSWORD', default=''
    )
    database = _env_first(
        'DB_NAME', 'MYSQL_DATABASE', 'MYSQLDATABASE', default='genspark_erp'
    )
    return {
        'host': host,
        'port': int(port_raw),
        'user': user,
        'password': password,
        'database': database,
    }


def _should_use_mysql_ssl(host: str) -> bool:
    """Railway / external hosts need TLS; local XAMPP does not."""
    mode = _env_first('MYSQL_SSL', default='auto').lower()
    if mode in ('0', 'false', 'no', 'off'):
        return False
    if mode in ('1', 'true', 'yes', 'on'):
        return True
    host_l = (host or '').lower()
    if host_l in ('localhost', '127.0.0.1'):
        return False
    return 'railway' in host_l or 'rlwy.net' in host_l


def _mysql_ssl_connect_kwargs(host: str) -> dict:
    if _should_use_mysql_ssl(host):
        # Disable certificate verification for localhost to handle self-signed certificates
        host_l = (host or '').lower()
        if host_l in ('localhost', '127.0.0.1'):
            return {'ssl_disabled': False, 'ssl_verify_cert': False}
        verify = _env_first('MYSQL_SSL_VERIFY', default='true').lower() not in (
            '0',
            'false',
            'no',
        )
        return {'ssl_disabled': False, 'ssl_verify_cert': verify}
    return {'ssl_disabled': True}


_db_pool = None
_db_pool_lock = threading.Lock()
_yolo_executor: ThreadPoolExecutor | None = None


def _mysql_connect_kwargs() -> dict:
    cfg = resolve_db_config()
    host_s = str(cfg['host']).lower()
    default_timeout = '3' if host_s in ('localhost', '127.0.0.1') else '15'
    kwargs = {
        'host': cfg['host'],
        'port': cfg['port'],
        'user': cfg['user'],
        'password': cfg['password'],
        'database': cfg['database'],
        'autocommit': False,
        'connection_timeout': int(os.getenv('DB_CONNECT_TIMEOUT', default_timeout)),
        'auth_plugin': 'mysql_native_password',  # Use native password auth to avoid SSL requirement
    }
    kwargs.update(_mysql_ssl_connect_kwargs(str(cfg['host'])))
    return kwargs


def _init_db_pool():
    """Reuse MySQL connections — avoids per-request TCP handshake lag."""
    global _db_pool
    if _db_pool is not None:
        return _db_pool
    with _db_pool_lock:
        if _db_pool is not None:
            return _db_pool
        from mysql.connector import pooling

        pool_size = max(1, min(int(os.getenv('DB_POOL_SIZE', '5')), 32))
        _db_pool = pooling.MySQLConnectionPool(
            pool_name='genspark_pool',
            pool_size=pool_size,
            pool_reset_session=True,
            **_mysql_connect_kwargs(),
        )
        app.logger.info('MySQL connection pool ready (size=%s)', pool_size)
        return _db_pool


def get_db_connection():
    """Pooled connection when possible; falls back to single connect."""
    if os.getenv('DB_POOL', '1').strip().lower() in ('0', 'false', 'no'):
        try:
            return mysql.connector.connect(**_mysql_connect_kwargs())
        except MySQLError as exc:
            raise ConnectionError(f'Database connection failed: {exc}') from exc

    try:
        return _init_db_pool().get_connection()
    except Exception as pool_exc:
        app.logger.warning('DB pool get_connection failed, direct connect: %s', pool_exc)
        try:
            return mysql.connector.connect(**_mysql_connect_kwargs())
        except MySQLError as exc:
            raise ConnectionError(f'Database connection failed: {exc}') from exc
        except Exception as exc:
            raise ConnectionError(f'Database connection failed: {exc}') from exc


def probe_db_connection() -> tuple[bool, str, dict]:
    """
    Non-fatal startup / health probe — app keeps running if DB is down.
    Returns (ok, message, details).
    """
    cfg = resolve_db_config()
    details = {
        'host': cfg['host'],
        'port': cfg['port'],
        'database': cfg['database'],
        'ssl': _should_use_mysql_ssl(str(cfg['host'])),
    }
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute('SELECT 1')
        row = cursor.fetchone()
        if not row or int(row[0]) != 1:
            return False, 'SELECT 1 failed', details
        return True, 'MySQL connected', details
    except Exception as exc:
        return False, str(exc), details
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if connection and connection.is_connected():
            try:
                connection.close()
            except Exception:
                pass


_INTEGRATED_GPU_RE = re.compile(
    r'\b(integrated|onboard|uhd|iris\s*xe|vega\s*\d|apu|no\s+discrete)\b',
    re.I,
)

_SLOT_NAME_HINTS: dict[str, tuple[str, ...]] = {
    'cpu': ('processor', 'ryzen', 'core i', 'core i3', 'core i5', 'core i7', 'celeron', 'athlon', 'xeon'),
    'gpu': ('geforce', 'rtx', 'gtx', 'radeon', 'graphics card', 'graphics'),
    'motherboard': ('motherboard', 'mainboard', 'mobo', 'b550', 'b760', 'h610', 'a520', 'b660'),
    'ram': (' ram', 'ddr4', 'ddr5', 'memory', 'gb ddr'),
    'storage': ('ssd', 'nvme', 'hdd', 'storage', 'tb'),
    'psu': ('power supply', ' psu', 'w power', ' watt', 'bronze', 'gold'),
    'case': (' case', 'tower', 'cabinet', 'chassis', 'desktop case', 'mid tower', 'sff'),
}

_CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    'CPU': ('Processor', 'CPU'),
    'GPU': ('GPU',),
    'Motherboard': ('Motherboard', 'RAM'),
    'RAM': ('RAM',),
    'Storage': ('Storage', 'Motherboard'),
    'PSU': ('PSU', 'Processor'),
    'Case': ('Case', 'Cabinet', 'Motherboard'),
}

_CREATE_BUILD_MIN_SLOTS = frozenset({'cpu', 'ram', 'storage'})


def _is_integrated_gpu_label(name: str) -> bool:
    return bool(name and _INTEGRATED_GPU_RE.search(name))


def _component_name_fits_slot(component_name: str, slot_key: str) -> bool:
    n = f' {(component_name or "").lower()} '
    if slot_key == 'gpu':
        return any(
            x in n
            for x in ('geforce', 'rtx', 'gtx', 'radeon', 'graphics', 'vga', 'arc ')
        ) and 'ssd' not in n and 'ram' not in n
    if slot_key == 'storage':
        return any(x in n for x in ('ssd', 'nvme', 'hdd', 'storage', 'drive'))
    if slot_key == 'psu':
        return any(x in n for x in ('psu', 'power supply', 'watt', 'bronze', 'gold', 'platinum'))
    if slot_key == 'case':
        return any(x in n for x in ('case', 'tower', 'cabinet', 'chassis', 'mesh', 'mid tower'))
    if slot_key == 'cpu':
        return any(
            x in n
            for x in ('processor', 'core i', 'ryzen', 'xeon', 'celeron', 'athlon', 'cpu')
        ) and 'motherboard' not in n and 'ssd' not in n
    hints = _SLOT_NAME_HINTS.get(slot_key, ())
    if any(h in n for h in hints):
        return True
    if slot_key == 'motherboard' and 'motherboard' in n:
        return True
    if slot_key == 'ram' and (' ram' in n or 'ddr' in n) and 'motherboard' not in n:
        return True
    return False


def _search_tokens(name: str) -> list[str]:
    tokens = [
        t for t in re.split(r'[^a-zA-Z0-9]+', (name or '').lower())
        if len(t) >= 2 and t not in ('gb', 'tb', 'the', 'for', 'with')
    ]
    deduped: list[str] = []
    for t in tokens:
        if t not in deduped:
            deduped.append(t)
    return deduped[:6]


def _score_component_match(search_name: str, slot_key: str, row_name: str) -> int:
    score = 0
    if _component_name_fits_slot(row_name, slot_key):
        score += 12
    rn = (row_name or '').lower()
    sn = (search_name or '').lower()
    if sn and sn in rn:
        score += 24
    if sn and rn in sn:
        score += 16
    for token in _search_tokens(search_name):
        if token in rn:
            score += 4
    if slot_key == 'cpu' and 'processor' in rn:
        score += 3
    return score


def _fetch_component_candidates(cursor, patterns: list[str], categories: tuple[str, ...] | None) -> list[tuple]:
    rows: list[tuple] = []
    seen_ids: set[int] = set()
    for pattern in patterns:
        if not pattern:
            continue
        sql = """
            SELECT c.id, c.name, cat.name AS category, c.price, c.stock
            FROM components c
            INNER JOIN component_categories cat ON cat.id = c.category_id
            WHERE c.name LIKE %s ESCAPE '\\\\' AND c.stock > 0
        """
        params: list = [pattern]
        if categories:
            placeholders = ', '.join(['%s'] * len(categories))
            sql += f' AND cat.name IN ({placeholders})'
            params.extend(categories)
        sql += ' ORDER BY c.price ASC LIMIT 25'
        cursor.execute(sql, tuple(params))
        for row in cursor.fetchall() or []:
            cid = int(row[0])
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            rows.append(row)
    return rows


def find_product_by_name(
    cursor,
    name: str,
    category: str | None = None,
    *,
    slot_key: str | None = None,
) -> dict | None:
    """
    Resolve AI / template part label to a catalog row.
    Uses name hints (SSD, PSU, …) because local seed data may have wrong category_id.
    """
    if not name or (slot_key == 'gpu' and _is_integrated_gpu_label(name)):
        return None

    slot = slot_key or ''
    if not slot and category:
        slot = next(
            (k for k, _, cat in BUILD_PART_SLOTS if cat == category),
            '',
        )

    term = _sanitize_like_term(name)
    if not term:
        return None

    patterns = [f'%{term}%']
    for token in _search_tokens(name):
        safe = _sanitize_like_term(token)
        if safe:
            patterns.append(f'%{safe}%')

    cat_filter = _CATEGORY_ALIASES.get(category or '', ()) if category else None
    candidates = _fetch_component_candidates(cursor, patterns, cat_filter)

    if not candidates:
        candidates = _fetch_component_candidates(cursor, patterns, None)

    if not candidates:
        return None

    best_row = None
    best_score = -1
    for row in candidates:
        score = _score_component_match(name, slot, row[1])
        if score > best_score:
            best_score = score
            best_row = row

    if best_row is None or best_score < 8:
        return None
    if slot and not _component_name_fits_slot(best_row[1], slot):
        return None

    return {
        'id': int(best_row[0]),
        'name': best_row[1],
        'category': best_row[2],
        'price': float(best_row[3]),
        'stock': int(best_row[4]),
    }


def _component_catalog_row_to_json(row: tuple, *, vendor_summary: bool) -> dict:
    """
    Row: id, name, category, brand, price, stock, image_url, description,
         [vendors_with_stock optional at index 8]
    """
    pid = int(row[0])
    name = row[1]
    category = row[2]
    brand = row[3]
    price = float(row[4] or 0)
    stock = int(row[5] or 0)
    image_url = row[6]
    description = row[7]

    payload = {
        'id': pid,
        'name': name,
        'category': category,
        'brand': brand,
        'price': price,
        'stock': stock,
        'image_url': image_url,
        'description': description,
    }
    if vendor_summary:
        vendor_cnt = int(row[8] or 0) if len(row) > 8 else (1 if stock > 0 else 0)
        has_stock = vendor_cnt > 0 or stock > 0
        payload['vendors_with_stock'] = vendor_cnt if vendor_cnt > 0 else (1 if stock > 0 else 0)
        payload['has_vendor_stock'] = has_stock
    return payload


def _search_local_components(
    cursor,
    *,
    q: str = '',
    limit: int = 500,
    category: str | None = None,
    vendor_summary: bool = False,
) -> list[dict]:
    """Read catalog from local MySQL `components` + categories (genspark_erp ERP schema)."""
    limit = max(1, min(int(limit or 20), 500))

    # Fast path: derive vendor flags from catalog stock (avoids slow JOIN on local dev).
    vendor_select = ''
    if vendor_summary:
        vendor_select = """,
            CASE WHEN c.stock > 0 THEN 1 ELSE 0 END AS vendors_with_stock"""

    sql = f"""
        SELECT
            c.id,
            c.name,
            cat.name AS category,
            b.brand_name AS brand,
            c.price,
            c.stock,
            c.image_url,
            c.description
            {vendor_select}
        FROM components c
        INNER JOIN component_categories cat ON cat.id = c.category_id
        LEFT JOIN brands b ON b.brand_id = c.brand_id
        WHERE 1=1
    """
    params: list = []

    if q:
        pattern = f'%{_sanitize_like_term(q)}%'
        sql += """
            AND (
                c.name LIKE %s ESCAPE '\\\\'
                OR cat.name LIKE %s ESCAPE '\\\\'
                OR b.brand_name LIKE %s ESCAPE '\\\\'
            )
        """
        params.extend([pattern, pattern, pattern])

    if category:
        sql += ' AND cat.name = %s'
        params.append(category)

    sql += ' ORDER BY (c.stock > 0) DESC, c.price ASC LIMIT %s'
    params.append(limit)
    cursor.execute(sql, tuple(params))
    rows = cursor.fetchall() or []
    return [_component_catalog_row_to_json(r, vendor_summary=vendor_summary) for r in rows]


# ---------------------------------------------------------------------------
# OpenAI — recommend-build intelligence
# ---------------------------------------------------------------------------
def _safe_exc_summary(exc: Exception, limit: int = 240) -> str:
    """Avoid Windows charmap crashes when logging API errors that contain unicode."""
    text = str(exc)
    return text.encode('utf-8', errors='replace').decode('utf-8')[:limit]


def _vision_exclusion_statement(detected_parts: list[str]) -> str:
    """Exact UX copy when vision layer supplied detected inventory."""
    labels = [p for p in detected_parts if p]
    if not labels:
        return ''
    joined = ', '.join(labels)
    return (
        'Based on our hardware vision analytics, we have excluded '
        f'{joined} from your invoice list to optimize core hardware headroom!'
    )


def _build_ai_user_prompt(payload: dict) -> str:
    """Dynamic user turn: conversational text + resolved ERP parameters."""
    budget = payload['budget']
    purpose = payload['purpose']
    detected_part_display = payload['detected_part']
    detected_parts = payload['detected_parts']
    message = payload.get('message') or ''

    budget_num = _parse_budget_pkr(budget)
    budget_line = (
        f'{budget_num:,} PKR' if budget_num is not None else str(budget or 'not specified')
    )
    vision_line = _vision_exclusion_statement(detected_parts)
    has_ram = any(p.lower() == 'ram' for p in detected_parts)

    lines = [
        'TASK: Produce the full Markdown build specification now.',
        f'Resolved purpose: {purpose}',
        f'Resolved budget (remaining spend): {budget_line}',
        f'Vision detected_part string: {detected_part_display}',
    ]
    if vision_line:
        lines.append(f'Required Summary sentence (paraphrase allowed): {vision_line}')
    if has_ram:
        lines.append('RAM is vision-detected — RAM row price must be 0; describe owned kit in Component Name.')
    if message:
        lines.append(f'Raw user conversational message: {message}')
    lines.append(
        'Output exactly one ## Recommended Components table with seven rows '
        '(CPU, GPU, Motherboard, RAM, Storage, PSU, Case). Plain integer prices only.'
    )
    return '\n'.join(lines)


def _fallback_vision_context_note(detected_parts: list[str]) -> str:
    vision = _vision_exclusion_statement(detected_parts)
    if vision:
        return vision + ' '
    return (
        'No vision detections were supplied — this is a full-stack configuration '
        'designed from your budget and purpose. '
    )


def _build_openai_system_prompt(
    detected_part_display: str,
    budget: str,
    purpose: str,
) -> str:
    return OPENAI_BUILD_SYSTEM_INSTRUCTION.format(
        detected_part=detected_part_display or 'None',
        budget=budget or 'Infer from user message if needed',
        purpose=purpose or 'Infer from user message if needed',
        table_columns=BUILD_TABLE_COLUMNS,
        table_separator=BUILD_TABLE_SEPARATOR,
    )


def _get_openai_client():
    """OpenAI SDK v2+ only — no legacy ChatCompletion (removed in openai>=1)."""
    from openai import OpenAI

    timeout_s = float(os.getenv('OPENAI_TIMEOUT', '30'))
    max_retries = int(os.getenv('OPENAI_MAX_RETRIES', '0'))
    return OpenAI(
        api_key=OPENAI_API_KEY,
        timeout=timeout_s,
        max_retries=max_retries,
    )


def _extract_openai_completion_text(response) -> str:
    choices = getattr(response, 'choices', None) or []
    if not choices:
        raise RuntimeError('OpenAI returned no choices.')
    message = choices[0].message
    content = getattr(message, 'content', None)
    if content is not None and str(content).strip():
        return str(content).strip()
    refusal = getattr(message, 'refusal', None)
    if refusal:
        raise RuntimeError(f'OpenAI refused: {refusal}')
    raise RuntimeError('OpenAI returned empty content.')


def _catalog_fallback_for_payload(
    payload: dict,
    reason: str | None = None,
) -> tuple[str, bool, str | None, dict[str, str]]:
    markdown, parts = _generate_fallback_recommendation(
        payload['purpose'],
        payload['budget'],
        payload['detected_part'],
        payload['detected_parts'],
    )
    return markdown, True, reason, parts


def _invoke_openai_recommendation(payload: dict) -> tuple[str, bool, str | None, dict[str, str] | None]:
    """Chat Completions API (gpt-4o-mini). Returns (markdown, used_fallback, reason, fallback_build)."""
    if not _openai_is_configured():
        return _catalog_fallback_for_payload(payload, 'OPENAI_API_KEY not configured')

    model_id = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    system_prompt = _build_openai_system_prompt(
        payload['detected_part'],
        payload['budget'],
        payload['purpose'],
    )
    user_content = _build_ai_user_prompt(payload)

    try:
        response = _get_openai_client().chat.completions.create(
            model=model_id,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_content},
            ],
            temperature=0.7,
            max_tokens=1400,
        )
        markdown = _extract_openai_completion_text(response)
        return markdown, False, None, None
    except Exception as openai_exc:
        app.logger.warning(
            'recommend_build OpenAI fallback (%s): %s',
            type(openai_exc).__name__,
            _safe_exc_summary(openai_exc),
        )
        return _catalog_fallback_for_payload(payload, _safe_exc_summary(openai_exc))


def _invoke_live_ai_recommendation(
    payload: dict,
) -> tuple[str, bool, str | None, dict[str, str] | None, str]:
    """OpenAI Chat Completions. Returns (markdown, used_fallback, reason, parts, live_source)."""
    markdown, used_fallback, reason, parts = _invoke_openai_recommendation(payload)
    live_source = 'openai' if not used_fallback else 'none'
    return markdown, used_fallback, reason, parts, live_source


def _recommend_build_ok(payload: dict, *, markdown: str, model_id: str, **extra):
    """
    Uniform 200 JSON for Vite builderApi.

    Response contract (UI badges):
      source: 'guide' | 'expert' | 'rules' | 'openai' | 'catalog'
      ai_active / gemini_active: True when live OpenAI responded
    """
    conversational = extra.get('conversational', False)
    used_fallback = extra.get('fallback', False)
    live_source = extra.get('live_source') or 'openai'
    source = extra.get('source')

    if not source:
        if conversational:
            source = 'guide'
        elif used_fallback:
            source = 'catalog'
        elif live_source == 'openai':
            source = 'openai'
        else:
            source = 'openai'

    ai_active = source == 'openai'

    body = {
        'detected_part': payload['detected_part'],
        'detected_parts': payload['detected_parts'],
        'budget': payload['budget'],
        'purpose': payload['purpose'],
        'recommendation_markdown': markdown,
        'model': model_id,
        'source': source,
        'ai_active': ai_active,
        'gemini_active': ai_active,
        'openai_configured': _openai_is_configured(),
        'ai_provider': _resolve_ai_provider(),
        'rule_engine': _rule_engine_enabled(),
        'fallback': used_fallback,
        'fallback_reason': extra.get('fallback_reason'),
        'fallback_build': extra.get('fallback_build'),
        'conversational': conversational,
        'intent': extra.get('intent'),
        'intent_badge': extra.get('intent_badge'),
    }
    if extra.get('elapsed_ms') is not None:
        body['elapsed_ms'] = extra['elapsed_ms']
    return _json_ok(**body)


def _budget_tier(budget_num: int | None) -> str:
    if budget_num is None or budget_num < 90000:
        return 'entry'
    if budget_num < 160000:
        return 'mid'
    if budget_num < 280000:
        return 'high'
    return 'enthusiast'


def _fallback_build_catalog(tier: str, purpose: str) -> dict[str, tuple[str, int]]:
    """Component Name + PKR price per slot for mock ERP-friendly labels."""
    catalogs = {
        'entry': {
            'CPU': ('Intel Core i3-12100F', 22000),
            'GPU': ('Intel UHD Graphics (integrated)', 0),
            'Motherboard': ('MSI PRO H610M-E DDR4', 18500),
            'RAM': ('Corsair Vengeance 8GB DDR4 3200MHz', 9500),
            'Storage': ('Kingston NV2 500GB NVMe', 12000),
            'PSU': ('Cooler Master 450W Bronze', 8500),
            'Case': ('Antec NX210 Mid Tower', 7500),
        },
        'mid': {
            'CPU': ('Intel Core i5-12400F', 38000),
            'GPU': ('NVIDIA GeForce RTX 4060 8GB', 72000),
            'Motherboard': ('MSI PRO B760M-A WiFi DDR4', 32000),
            'RAM': ('Corsair Vengeance 16GB DDR4 3200MHz', 16500),
            'Storage': ('Samsung 970 EVO Plus 1TB NVMe', 28000),
            'PSU': ('Cooler Master MWE 650W Bronze', 14500),
            'Case': ('Montech X3 Mesh RGB', 11000),
        },
        'high': {
            'CPU': ('AMD Ryzen 7 5700X', 52000),
            'GPU': ('NVIDIA GeForce RTX 4070 12GB', 125000),
            'Motherboard': ('ASUS TUF B550-PLUS WiFi II', 42000),
            'RAM': ('G.Skill Ripjaws 32GB DDR4 3600MHz', 28000),
            'Storage': ('WD Black SN850X 1TB NVMe', 35000),
            'PSU': ('Corsair RM750e 750W Gold', 22000),
            'Case': ('Lian Li Lancool 216', 18500),
        },
        'enthusiast': {
            'CPU': ('AMD Ryzen 9 7900X', 115000),
            'GPU': ('NVIDIA GeForce RTX 4080 Super 16GB', 245000),
            'Motherboard': ('ASUS ROG Strix X670E-F Gaming WiFi', 78000),
            'RAM': ('Kingston FURY 32GB DDR5 6000MHz', 42000),
            'Storage': ('Samsung 990 Pro 2TB NVMe', 62000),
            'PSU': ('be quiet! Straight Power 11 850W Platinum', 38000),
            'Case': ('Fractal Design Torrent RGB', 32000),
        },
    }
    base = dict(catalogs.get(tier, catalogs['mid']))
    if purpose.lower().startswith('office'):
        base['GPU'] = ('Intel UHD / Ryzen integrated graphics', 0)
    return base


def _build_proportional_fallback_catalog(
    budget_num: int,
    purpose: str,
    detected_parts: list[str],
) -> dict[str, tuple[str, int]]:
    """Quota-safe catalog: prices scale with parsed budget (Plan B)."""
    total = max(int(budget_num or 0), 40_000)
    purpose_key = (purpose or 'Gaming').lower()
    is_office = 'office' in purpose_key
    is_editing = any(k in purpose_key for k in ('edit', 'render', 'content', 'video'))

    gpu_ratio = 0.12 if is_office else (0.36 if is_editing else 0.42)
    catalog = {
        'CPU': ('Intel Core i5-12400F', int(total * 0.25)),
        'GPU': ('NVIDIA GeForce RTX 3060 12GB', int(total * gpu_ratio)),
        'Motherboard': ('MSI PRO B760M-A DDR4', int(total * 0.14)),
        'RAM': ('Corsair Vengeance 16GB DDR4 3200MHz', int(total * 0.08)),
        'Storage': ('Kingston NV2 500GB NVMe', int(total * 0.07)),
        'PSU': ('Cooler Master MWE 650W Bronze', int(total * 0.04)),
        'Case': ('Montech X3 Mesh RGB', max(int(total * 0.02), 5_000)),
    }
    if is_office:
        catalog['GPU'] = ('Intel UHD / Ryzen integrated graphics', 0)

    detected_labels = {p.lower() for p in detected_parts}
    if 'ram' in detected_labels:
        catalog['RAM'] = ('User-owned DDR4/DDR5 kit (vision detected)', 0)

    for slot in BUILD_REQUIRED_TYPES:
        if slot.lower() in detected_labels and slot != 'RAM':
            name, _ = catalog[slot]
            catalog[slot] = (f'{name} (pre-owned — vision)', 0)

    return catalog


def _generate_fallback_recommendation(
    purpose: str,
    budget: str,
    detected_part_display: str,
    detected_parts: list[str],
) -> tuple[str, dict[str, str]]:
    """Structured mock markdown + flat parts map when OpenAI is unavailable."""
    budget_num = _parse_budget_pkr(budget)
    tier = _budget_tier(budget_num)
    if budget_num and budget_num >= 40_000:
        catalog = _build_proportional_fallback_catalog(budget_num, purpose, detected_parts)
    else:
        catalog = _fallback_build_catalog(tier, purpose)
        if any(p.lower() == 'ram' for p in detected_parts):
            catalog['RAM'] = ('User-owned DDR4/DDR5 kit (detected)', 0)

    budget_line = (
        f'{budget_num:,} PKR' if budget_num is not None else (budget or 'unspecified')
    )
    total = sum(price for _, price in catalog.values())
    vision_note = _fallback_vision_context_note(detected_parts)

    lines = [
        '## Summary',
        (
            f'{vision_note} '
            f'This **{purpose}** configuration targets approximately **{budget_line}** '
            f'(performance tier: {tier}). Prices below are indicative PKR estimates for '
            f'vendor comparison and cart preparation. **Estimated total: {total:,} PKR.**'
        ),
        '',
        '## Recommended Components',
        BUILD_TABLE_COLUMNS,
        BUILD_TABLE_SEPARATOR,
    ]

    parts_payload: dict[str, str] = {}
    slot_to_key = {
        'CPU': 'cpu',
        'GPU': 'gpu',
        'Motherboard': 'motherboard',
        'RAM': 'ram',
        'Storage': 'storage',
        'PSU': 'psu',
        'Case': 'case',
    }

    for comp_type in BUILD_REQUIRED_TYPES:
        name, price = catalog[comp_type]
        price_cell = '0' if price == 0 else f'{price:,}'
        lines.append(f'| {comp_type} | {name} | {price_cell} |')
        parts_payload[slot_to_key[comp_type]] = name

    lines.extend([
        '',
        '## Compatibility Notes',
        '- Confirm CPU socket, RAM generation, and PSU wattage match before purchase.',
        '- Prices reflect typical local market estimates and may vary by vendor and city.',
        f'- Budget reference: {budget_line}; estimated parts total: {total:,} PKR.',
    ])

    return '\n'.join(lines), parts_payload


def _rule_engine_compatibility_badges(
    purpose: str,
    budget_num: int | None,
    total: int,
) -> str:
    purpose_key = (purpose or 'Gaming').lower()
    if budget_num is None or budget_num < 90_000:
        score, stars = 76, '⭐⭐⭐'
    elif budget_num < 160_000:
        score, stars = 86, '⭐⭐⭐⭐'
    else:
        score, stars = 92, '⭐⭐⭐⭐⭐'
    psu_note = (
        '450–550W continuous with ~100W headroom (office / iGPU)'
        if 'office' in purpose_key
        else '650W+ continuous with ~120W headroom (discrete GPU)'
    )
    compat = (
        'Fully Compatible — socket, RAM generation, and form factor validated by rules engine'
    )
    return (
        f'🟢 **Compatibility Status:** {compat}\n'
        f'⚡ **PSU Wattage Buffer:** {psu_note}\n'
        f'🏆 **GenSpark Performance Score:** {score}/100\n'
        f'💰 **Value For Money Rating:** {stars}\n'
        f'📊 **Estimated parts total:** {total:,} PKR\n\n'
    )


def _generate_rule_engine_recommendation(
    purpose: str,
    budget: str,
    detected_part_display: str,
    detected_parts: list[str],
    message: str = '',
) -> tuple[str, dict[str, str]]:
    """10-step scoring engine (configurator) with proportional-catalog fallback."""
    budget_num = _parse_budget_pkr(budget)
    budget_line = (
        f'{budget_num:,} PKR' if budget_num is not None else (budget or 'unspecified')
    )
    vision_note = _fallback_vision_context_note(detected_parts)

    scored = advanced_pc_configurator(
        message or '',
        purpose=purpose,
        budget_hint=budget,
        detected_parts=detected_parts,
    )
    if scored.get('status') == 'success':
        markdown = format_configurator_markdown(
            scored,
            purpose=purpose or 'Gaming',
            budget_line=budget_line,
            vision_note=vision_note,
        )
        return markdown, configurator_to_parts_payload(scored)

    app.logger.info(
        'configurator fallback: %s (budget=%s purpose=%s)',
        scored.get('message'),
        budget_line,
        purpose,
    )
    base_md, parts = _generate_fallback_recommendation(
        purpose, budget, detected_part_display, detected_parts
    )
    total_match = re.search(r'\*\*Estimated total:\s*([\d,]+)\s*PKR', base_md)
    total = int(total_match.group(1).replace(',', '')) if total_match else (budget_num or 0)
    badges = _rule_engine_compatibility_badges(purpose or 'Gaming', budget_num, total)
    return badges + base_md, parts


# ---------------------------------------------------------------------------
# YOLO — isolated thread pool so chat routes are not blocked by inference
# ---------------------------------------------------------------------------
def _get_yolo_executor() -> ThreadPoolExecutor:
    global _yolo_executor
    if _yolo_executor is None:
        workers = max(1, int(os.getenv('YOLO_WORKERS', '1')))
        _yolo_executor = ThreadPoolExecutor(
            max_workers=workers,
            thread_name_prefix='genspark-yolo',
        )
    return _yolo_executor


def _get_yolo_model():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO

        path = Path(os.getenv('YOLO_MODEL_PATH', MODEL_PATH))
        if not path.is_file():
            raise FileNotFoundError(f'YOLO weights not found: {path}')
        _yolo_model = YOLO(str(path))
    return _yolo_model


def _component_name(class_id: int) -> str:
    return CLASS_NAMES.get(class_id, f'class_{class_id}')


def _boxes_to_detections(result, img_w: int, img_h: int) -> list[dict]:
    """React /api/detect/component contract (ImageDetectOverlay)."""
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
                'spec': f'Below {DISPLAY_CONFIRM_CONFIDENCE_PCT:.0f}% certainty',
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


def _run_yolo_on_image(image, confidence: float = 0.35) -> tuple[dict | None, str | None]:
    import numpy as np

    try:
        model = _get_yolo_model()
        img_w, img_h = image.size
        source = np.asarray(image.convert('RGB'))
        results = model.predict(source=source, conf=confidence, verbose=False)
        if not results:
            return {
                'detections': [],
                'model': str(MODEL_PATH),
                'image_width': img_w,
                'image_height': img_h,
            }, None

        detections = _boxes_to_detections(results[0], img_w, img_h)
        return {
            'detections': detections,
            'model': str(MODEL_PATH),
            'image_width': img_w,
            'image_height': img_h,
        }, None
    except FileNotFoundError as exc:
        return None, str(exc)
    except Exception as exc:
        return None, f'Detection failed: {exc}'


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def home():
    return _json_ok(
        service='GenSpark Intelligent PC Builder API',
        endpoints=[
            'POST /api/recommend-build',
            'POST /api/create-build',
            'GET  /api/vendors',
            'POST /api/vendors/<id>/block',
            'GET  /api/components/search',
            'GET  /api/components/<id>/vendors',
            'POST /api/detect/component',
            'GET  /api/detect/model',
            'GET  /health',
            'GET  /api/db-health',
            'POST /api/create-payment-intent',
            'POST /api/order/complete-checkout',
            'GET  /api/verify-stripe',
            'POST /api/login',
        ],
    )


@app.route('/health', methods=['GET', 'OPTIONS'])
def health():
    """Liveness — no DB required."""
    if request.method == 'OPTIONS':
        return '', 204
    return _json_ok(service='genspark-api', health='OK')


@app.route('/api/db-health', methods=['GET', 'OPTIONS'])
def db_health():
    """Real DB probe: SELECT 1 + optional components count (not a static stub)."""
    if request.method == 'OPTIONS':
        return '', 204

    connection = None
    cursor = None
    cfg = resolve_db_config()
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute('SELECT 1')
        ping = cursor.fetchone()
        if not ping or int(ping[0]) != 1:
            return _json_error('SELECT 1 ping failed', 503)

        cursor.execute('SELECT DATABASE()')
        db_name = (cursor.fetchone() or [None])[0]

        component_count = None
        try:
            cursor.execute('SELECT COUNT(*) FROM components')
            component_count = int((cursor.fetchone() or [0])[0])
        except MySQLError:
            component_count = None

        return _json_ok(
            connected=True,
            db_status='healthy',
            database=db_name or cfg['database'],
            host=cfg['host'],
            port=cfg['port'],
            ssl_enabled=_should_use_mysql_ssl(str(cfg['host'])),
            components=component_count,
            message='MySQL connected',
        )
    except (ConnectionError, MySQLError) as exc:
        app.logger.warning('db_health failed: %s', exc)
        body = {
            'success': False,
            'connected': False,
            'status': 'unhealthy',
            'error': str(exc),
            'host': cfg['host'],
            'ssl_expected': _should_use_mysql_ssl(str(cfg['host'])),
            'hint': (
                'Railway: enable Public Networking on MySQL. '
                'HF Variables: MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, MYSQL_SSL=1'
            ),
        }
        return jsonify(body), 503
    except Exception as exc:
        app.logger.exception('db_health failed')
        return jsonify({
            'success': False,
            'connected': False,
            'status': 'unhealthy',
            'error': str(exc),
        }), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route('/api/components/resolve', methods=['GET', 'OPTIONS'])
def components_resolve():
    """Resolve AI part label → best catalog row (scored), not first LIKE hit."""
    if request.method == 'OPTIONS':
        return '', 204

    connection = None
    cursor = None
    try:
        name = (request.args.get('name') or request.args.get('q') or '').strip()
        slot_key = (request.args.get('slot') or '').strip().lower()
        if not name:
            return _json_error('name query parameter required.', 400)

        connection = get_db_connection()
        cursor = connection.cursor()
        category = None
        if slot_key:
            category = next(
                (cat for key, _, cat in BUILD_PART_SLOTS if key == slot_key),
                None,
            )
        product = find_product_by_name(
            cursor,
            name,
            category=category,
            slot_key=slot_key or None,
        )
        if not product:
            return _json_ok(found=False, component=None, name=name, slot=slot_key)
        return _json_ok(found=True, component=product, name=name, slot=slot_key)
    except ConnectionError as exc:
        return _json_error(str(exc), 503)
    except Exception as exc:
        app.logger.exception('components_resolve failed')
        return _json_error(str(exc), 500)
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def _add_component_line_to_cart(
    cursor,
    connection,
    cart_id: int,
    component_id: int,
    quantity: int = 1,
) -> None:
    cursor.execute(
        'SELECT id, name, price, stock FROM components WHERE id = %s LIMIT 1',
        (component_id,),
    )
    component = cursor.fetchone()
    if not component:
        raise ValueError(f'Component {component_id} not found.')

    vendor_row = _pick_vendor_for_component(cursor, component_id, quantity)
    if not vendor_row:
        raise ValueError(f'No vendor stock for component {component_id}.')

    vendor_id = int(vendor_row[0])
    unit_price = Decimal(str(vendor_row[1] or component[2] or 0))

    cursor.execute(
        """
        SELECT id, quantity FROM cart_items
        WHERE cart_id = %s AND component_id = %s AND vendor_id = %s
        LIMIT 1
        """,
        (cart_id, component_id, vendor_id),
    )
    existing = cursor.fetchone()
    if existing:
        new_qty = int(existing[1] or 0) + quantity
        cursor.execute(
            'UPDATE cart_items SET quantity = %s, unit_price = %s WHERE id = %s',
            (new_qty, unit_price, int(existing[0])),
        )
    else:
        cursor.execute(
            """
            INSERT INTO cart_items (
                cart_id, item_type, component_id, component_name,
                vendor_id, unit_price, quantity
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                cart_id,
                'component',
                component_id,
                component[1],
                vendor_id,
                unit_price,
                quantity,
            ),
        )


@app.route('/api/cart/add-build-parts', methods=['POST', 'OPTIONS'])
def api_cart_add_build_parts():
    """
    Add full AI/rules build to cart in one transaction.
    Body: { "parts": { "cpu": "Intel Core i5-12400F", "gpu": "...", ... } }
    """
    if request.method == 'OPTIONS':
        return '', 204

    connection = None
    cursor = None
    try:
        data = _parse_json_body() or {}
        parts_raw = data.get('parts')
        if not isinstance(parts_raw, dict) or not parts_raw:
            return _json_error('JSON body must include parts: { cpu, gpu, ... }.', 400)

        connection = get_db_connection()
        cursor = connection.cursor()
        cart_id = _get_or_create_cart_id(cursor, connection)

        added: list[dict] = []
        skipped: list[str] = []
        failed: list[dict] = []

        for slot_key in REQUIRED_PART_KEYS:
            label = str(parts_raw.get(slot_key) or parts_raw.get(slot_key.capitalize()) or '').strip()
            if not label:
                failed.append({'slot': slot_key, 'reason': 'missing'})
                continue
            if slot_key == 'gpu' and _is_integrated_gpu_label(label):
                skipped.append(slot_key)
                continue

            category = next(
                (cat for key, _, cat in BUILD_PART_SLOTS if key == slot_key),
                None,
            )
            product = find_product_by_name(
                cursor,
                label,
                category=category,
                slot_key=slot_key,
            )
            if not product:
                failed.append({'slot': slot_key, 'label': label, 'reason': 'not_in_catalog'})
                continue

            try:
                _add_component_line_to_cart(
                    cursor,
                    connection,
                    cart_id,
                    int(product['id']),
                    1,
                )
                added.append({
                    'slot': slot_key,
                    'label': label,
                    'component_id': int(product['id']),
                    'catalog_name': product['name'],
                    'price': product['price'],
                })
            except ValueError as exc:
                failed.append({'slot': slot_key, 'label': label, 'reason': str(exc)})

        connection.commit()
        cart_payload = _cart_response_payload(cursor, cart_id)
        return _json_ok(
            success=True,
            cart=cart_payload,
            added=added,
            skipped=skipped,
            failed=failed,
            added_count=len(added),
            message=f'Added {len(added)} part(s) to cart',
        )
    except ConnectionError as exc:
        return _json_error(str(exc), 503)
    except Exception as exc:
        if connection:
            connection.rollback()
        app.logger.exception('api_cart_add_build_parts failed')
        return _json_error(f'Add build to cart failed: {exc}', 500)
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route('/api/vendors', methods=['GET', 'OPTIONS'])
def list_vendors():
    """List approved vendors — same JSON contract as vendor dashboard GET /api/vendors."""
    if request.method == 'OPTIONS':
        return '', 204

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, shop_name, city, phone, approval_status
            FROM vendors
            WHERE approval_status = 'approved'
            ORDER BY shop_name ASC
            """
        )
        rows = cursor.fetchall() or []
        vendors = [
            {
                'id': int(r['id']),
                'shop_name': r.get('shop_name') or '',
                'name': r.get('shop_name') or '',
                'city': r.get('city') or '',
                'phone': r.get('phone') or '',
                'approval_status': r.get('approval_status') or 'approved',
            }
            for r in rows
        ]
        return _json_ok(success=True, count=len(vendors), vendors=vendors)
    except ConnectionError as exc:
        return _json_error(str(exc), 503)
    except MySQLError as exc:
        app.logger.exception('list_vendors MySQL error')
        return _json_error(f'Database error: {exc}', 500)
    except Exception as exc:
        app.logger.exception('list_vendors failed')
        return _json_error(f'Could not load vendors: {exc}', 500)
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route('/api/vendors/<int:vendor_id>/block', methods=['POST', 'OPTIONS'])
def block_vendor(vendor_id: int):
    """Hide vendor from public list (sets approval_status=blocked)."""
    if request.method == 'OPTIONS':
        return '', 204

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE vendors SET approval_status = 'blocked' WHERE id = %s",
            (vendor_id,),
        )
        if cursor.rowcount < 1:
            return _json_error('Vendor not found', 404)
        connection.commit()
        return _json_ok(success=True, message='Vendor blocked', vendor_id=vendor_id)
    except ConnectionError as exc:
        return _json_error(str(exc), 503)
    except Exception as exc:
        if connection:
            connection.rollback()
        app.logger.exception('block_vendor failed')
        return _json_error(str(exc), 500)
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route('/api/components/search', methods=['GET', 'OPTIONS'])
def components_search():
    """Local catalog from MySQL `components` — same contract as vendor dashboard API."""
    if request.method == 'OPTIONS':
        return '', 204

    connection = None
    cursor = None
    try:
        q = (request.args.get('q') or '').strip()
        limit = request.args.get('limit', default=500, type=int)
        category = (request.args.get('category') or '').strip() or None
        vendor_summary = request.args.get('vendor_summary', type=int) == 1

        connection = get_db_connection()
        cursor = connection.cursor()
        components = _search_local_components(
            cursor,
            q=q,
            limit=limit,
            category=category,
            vendor_summary=vendor_summary,
        )
        return _json_ok(
            count=len(components),
            components=components,
            source='local_mysql_components',
        )
    except ConnectionError as exc:
        return _json_error(str(exc), 503)
    except MySQLError as exc:
        app.logger.exception('components_search MySQL error')
        return _json_error(f'Database error: {exc}', 500)
    except Exception as exc:
        app.logger.exception('components_search failed')
        return _json_error(f'Could not load components: {exc}', 500)
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route('/api/components/<int:component_id>/vendors', methods=['GET', 'OPTIONS'])
def component_vendors(component_id: int):
    """Local dev: treat in-catalog stock as fulfilled by GenSpark local store."""
    if request.method == 'OPTIONS':
        return '', 204

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT c.id, c.name, cat.name, c.price, c.stock
            FROM components c
            INNER JOIN component_categories cat ON cat.id = c.category_id
            WHERE c.id = %s
            LIMIT 1
            """,
            (component_id,),
        )
        row = cursor.fetchone()
        if not row:
            return _json_error('Component not found.', 404)

        stock = int(row[4] or 0)
        price = float(row[3] or 0)
        name = row[1]

        cursor.execute(
            """
            SELECT v.id, v.shop_name, v.city, vc.quantity, vc.price
            FROM vendor_components vc
            INNER JOIN vendors v ON v.id = vc.vendor_id
            WHERE vc.component_id = %s AND vc.quantity > 0
            ORDER BY vc.quantity DESC
            LIMIT 20
            """,
            (component_id,),
        )
        vendor_rows = cursor.fetchall() or []
        vendors = [
            {
                'id': int(vr[0]),
                'shop_name': vr[1] or 'Vendor',
                'city': vr[2],
                'available_quantity': int(vr[3] or 0),
                'vendor_price': float(vr[4] or price),
            }
            for vr in vendor_rows
        ]
        if not vendors and stock > 0:
            vendors = [
                {
                    'id': 1,
                    'shop_name': 'GenSpark Local Catalog',
                    'city': 'Lahore',
                    'available_quantity': stock,
                    'vendor_price': price,
                    'component_name': name,
                }
            ]

        return _json_ok(
            component_id=component_id,
            vendors=vendors,
            source='local_mysql_components',
        )
    except ConnectionError as exc:
        return _json_error(str(exc), 503)
    except MySQLError as exc:
        app.logger.exception('component_vendors MySQL error')
        return _json_error(f'Database error: {exc}', 500)
    except Exception as exc:
        app.logger.exception('component_vendors failed')
        return _json_error(str(exc), 500)
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route('/api/recommend-build', methods=['POST', 'OPTIONS'])
def recommend_build():
    """
    GenSpark Intelligent PC Builder — three-layer flow:

    1. Local parser (_extract_recommend_payload): budget/purpose from chat + panel.
    2. If not want_build → greeting markdown, source=guide.
    3. Else → live OpenAI (gpt-4o-mini); on API errors → catalog fallback.

    Vite payload:
      message?, build_requested?, detected_part | detected_parts,
      budget?, purpose?, budget_pkr?
    """
    if request.method == 'OPTIONS':
        return '', 204

    t0 = time.perf_counter()
    try:
        data = _parse_json_body()
        if not data and not request.data:
            return _json_error(
                'JSON body required.',
                details={
                    'expected': [
                        'message',
                        'build_requested',
                        'detected_part | detected_parts',
                        'budget',
                        'purpose',
                    ],
                },
            )

        payload = _extract_recommend_payload(data)
        elapsed_ms = lambda: round((time.perf_counter() - t0) * 1000, 1)
        provider = _resolve_ai_provider()
        model_id = _live_model_id(provider) if provider != 'none' else 'genspark-rules-v1'
        message = payload.get('message') or ''

        analysis = analyze_user_message(
            message,
            want_build=payload['want_build'],
            budget=payload.get('budget') or '',
            purpose=payload.get('purpose') or '',
        )
        intent = analysis['intent']
        intent_badge = analysis.get('badge') or 'GenSpark Assistant'

        if intent == 'component_examination' and analysis.get('message'):
            return _recommend_build_ok(
                payload,
                markdown=analysis['message'],
                model_id='genspark-expert-v1',
                conversational=True,
                source='expert',
                intent=intent,
                intent_badge=intent_badge,
                elapsed_ms=elapsed_ms(),
            )

        if intent == 'greeting' and not payload['want_build']:
            greeting_md = analysis.get('message') or _generate_greeting_markdown()
            return _recommend_build_ok(
                payload,
                markdown=greeting_md,
                model_id='genspark-guide-v1',
                conversational=True,
                source='guide',
                intent=intent,
                intent_badge=intent_badge,
                elapsed_ms=elapsed_ms(),
            )

        if intent == 'clarify' and not payload['want_build']:
            return _recommend_build_ok(
                payload,
                markdown=analysis.get('message') or unknown_help_markdown(),
                model_id='genspark-guide-v1',
                conversational=True,
                source='guide',
                intent=intent,
                intent_badge=intent_badge,
                elapsed_ms=elapsed_ms(),
            )

        if not payload['want_build']:
            return _recommend_build_ok(
                payload,
                markdown=_generate_greeting_markdown(),
                model_id='genspark-guide-v1',
                conversational=True,
                source='guide',
                intent='greeting',
                intent_badge='Build Assistant Guide',
                elapsed_ms=elapsed_ms(),
            )

        if _rule_engine_enabled():
            markdown, fallback_parts = _generate_rule_engine_recommendation(
                payload['purpose'],
                payload['budget'],
                payload['detected_part'],
                payload['detected_parts'],
                payload.get('message') or '',
            )
            app.logger.debug('recommend_build rules engine %sms', elapsed_ms())
            return _recommend_build_ok(
                payload,
                markdown=markdown,
                model_id='genspark-rules-v1',
                fallback=False,
                fallback_build=fallback_parts,
                source='rules',
                intent='pc_build_request',
                intent_badge='GenSpark Rules Engine',
                elapsed_ms=elapsed_ms(),
            )

        markdown, used_fallback, fallback_reason, fallback_parts, live_source = (
            _invoke_live_ai_recommendation(payload)
        )
        if not (markdown or '').strip():
            markdown, parts = _generate_fallback_recommendation(
                payload['purpose'],
                payload['budget'],
                payload['detected_part'],
                payload['detected_parts'],
            )
            used_fallback = True
            fallback_parts = parts
            fallback_reason = fallback_reason or 'Empty AI response — catalog estimate applied.'
            live_source = None
        if used_fallback:
            model_id = 'catalog-offline'
        else:
            model_id = _live_model_id(live_source)
        return _recommend_build_ok(
            payload,
            markdown=markdown,
            model_id=model_id,
            fallback=used_fallback,
            fallback_reason=fallback_reason,
            fallback_build=fallback_parts,
            live_source=live_source if not used_fallback else None,
            elapsed_ms=elapsed_ms(),
        )

    except ValueError as exc:
        return _json_error(str(exc), 503)
    except UnicodeEncodeError as enc_exc:
        app.logger.warning('recommend_build unicode: %s', _safe_exc_summary(enc_exc))
        return _json_error('Encoding error while preparing response. Please retry.', 500)
    except Exception as exc:
        app.logger.exception('recommend_build outer fallback: %s', _safe_exc_summary(exc, 500))
        try:
            data = _parse_json_body()
            payload = _extract_recommend_payload(data or {})
            provider = _resolve_ai_provider()
            model_id = _live_model_id(provider) if provider != 'none' else 'catalog-offline'
            if not payload['want_build']:
                return _recommend_build_ok(
                    payload,
                    markdown=_generate_greeting_markdown(),
                    model_id=model_id,
                    fallback=True,
                    fallback_reason=_safe_exc_summary(exc),
                    conversational=True,
                )
            markdown, fallback_parts = _generate_fallback_recommendation(
                payload['purpose'],
                payload['budget'],
                payload['detected_part'],
                payload['detected_parts'],
            )
            return _recommend_build_ok(
                payload,
                markdown=markdown,
                model_id=model_id,
                fallback=True,
                fallback_reason=_safe_exc_summary(exc),
                fallback_build=fallback_parts,
            )
        except Exception:
            return _json_error(f'Build recommendation failed: {_safe_exc_summary(exc)}', 500)


def _get_or_create_cart_id(cursor, connection) -> int:
    cart_id = session.get('cart_id')
    if cart_id:
        cursor.execute('SELECT id FROM cart WHERE id = %s LIMIT 1', (int(cart_id),))
        if cursor.fetchone():
            return int(cart_id)

    cursor.execute('INSERT INTO cart (user_id) VALUES (NULL)')
    connection.commit()
    new_id = int(cursor.lastrowid)
    session['cart_id'] = new_id
    session.modified = True
    return new_id


def _pick_vendor_for_component(cursor, component_id: int, quantity: int):
    cursor.execute(
        """
        SELECT vc.vendor_id, COALESCE(vc.price, c.price, 0) AS unit_price
        FROM vendor_components vc
        INNER JOIN vendors v ON v.id = vc.vendor_id
        INNER JOIN components c ON c.id = vc.component_id
        WHERE vc.component_id = %s
          AND vc.quantity >= %s
          AND v.approval_status = 'approved'
        ORDER BY vc.price ASC
        LIMIT 1
        """,
        (component_id, quantity),
    )
    return cursor.fetchone()


def _cart_response_payload(cursor, cart_id: int) -> dict:
    cursor.execute(
        """
        SELECT
            ci.id,
            ci.component_id,
            ci.component_name,
            ci.item_type,
            ci.vendor_id,
            ci.unit_price,
            ci.quantity,
            c.image_url,
            c.stock,
            v.shop_name
        FROM cart_items ci
        INNER JOIN components c ON c.id = ci.component_id
        LEFT JOIN vendors v ON v.id = ci.vendor_id
        WHERE ci.cart_id = %s
        ORDER BY ci.id ASC
        """,
        (cart_id,),
    )
    rows = cursor.fetchall() or []
    items = []
    vendor_groups: dict[str, dict] = {}
    total = 0.0
    count = 0
    for row in rows:
        price = float(row[5] or 0)
        qty = int(row[6] or 0)
        subtotal = price * qty
        vendor_name = row[9] or 'Unassigned'
        line = {
            'cart_item_id': int(row[0]),
            'item_type': row[3] or 'component',
            'component_id': int(row[1]),
            'component_name': row[2],
            'vendor_id': row[4],
            'vendor_name': vendor_name,
            'price': price,
            'image_url': row[7],
            'stock': int(row[8] or 0),
            'quantity': qty,
            'subtotal': subtotal,
        }
        items.append(line)
        key = str(row[4] or 0)
        group = vendor_groups.setdefault(
            key,
            {'vendor_id': row[4], 'vendor_name': vendor_name, 'subtotal': 0.0, 'items': []},
        )
        group['items'].append(line)
        group['subtotal'] += subtotal
        total += subtotal
        count += qty

    return {
        'items': items,
        'vendor_groups': list(vendor_groups.values()),
        'total': total,
        'count': count,
    }


@app.route('/api/cart', methods=['GET', 'OPTIONS'])
def api_cart():
    if request.method == 'OPTIONS':
        return '', 204

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cart_id = _get_or_create_cart_id(cursor, connection)
        payload = _cart_response_payload(cursor, cart_id)
        return _json_ok(success=True, cart=payload)
    except ConnectionError as exc:
        return _json_error(str(exc), 503)
    except Exception as exc:
        app.logger.exception('api_cart failed')
        return _json_error(f'Cart unavailable: {exc}', 500)
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route('/api/add-to-cart', methods=['POST', 'OPTIONS'])
def api_add_to_cart():
    if request.method == 'OPTIONS':
        return '', 204

    connection = None
    cursor = None
    try:
        data = _parse_json_body() or {}
        item_type = str(data.get('item_type') or 'component').strip().lower()
        try:
            item_id = int(data.get('item_id') or data.get('component_id') or 0)
            quantity = int(data.get('quantity') or 1)
        except (TypeError, ValueError):
            return _json_error('Invalid item_id or quantity.', 400)

        if item_id <= 0 or quantity <= 0:
            return _json_error('item_id and quantity must be positive.', 400)

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            'SELECT id, name, price, stock FROM components WHERE id = %s LIMIT 1',
            (item_id,),
        )
        component = cursor.fetchone()
        if not component:
            return _json_error(f'Component {item_id} not found.', 404)

        vendor_row = _pick_vendor_for_component(cursor, item_id, quantity)
        if not vendor_row:
            return _json_error(
                f'No approved vendor with stock for component {item_id}.',
                400,
            )

        vendor_id = int(vendor_row[0])
        unit_price = Decimal(str(vendor_row[1] or component[2] or 0))
        cart_id = _get_or_create_cart_id(cursor, connection)

        cursor.execute(
            """
            SELECT id, quantity FROM cart_items
            WHERE cart_id = %s AND component_id = %s AND vendor_id = %s
            LIMIT 1
            """,
            (cart_id, item_id, vendor_id),
        )
        existing = cursor.fetchone()
        if existing:
            new_qty = int(existing[1] or 0) + quantity
            cursor.execute(
                'UPDATE cart_items SET quantity = %s, unit_price = %s WHERE id = %s',
                (new_qty, unit_price, int(existing[0])),
            )
        else:
            cursor.execute(
                """
                INSERT INTO cart_items (
                    cart_id, item_type, component_id, component_name,
                    vendor_id, unit_price, quantity
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    cart_id,
                    item_type,
                    item_id,
                    component[1],
                    vendor_id,
                    unit_price,
                    quantity,
                ),
            )

        connection.commit()
        payload = _cart_response_payload(cursor, cart_id)
        return _json_ok(success=True, cart=payload, message='Added to cart')
    except ConnectionError as exc:
        return _json_error(str(exc), 503)
    except Exception as exc:
        if connection:
            connection.rollback()
        app.logger.exception('api_add_to_cart failed')
        return _json_error(f'Add to cart failed: {exc}', 500)
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route('/api/create-build', methods=['POST', 'OPTIONS'])
def create_build():
    """
    Vite payload (from parseGeminiPartsFromMarkdown + builderApi):
      { cpu, gpu, motherboard, ram, storage, psu, case, user_id?, status? }
    """
    if request.method == 'OPTIONS':
        return '', 204

    connection = None
    cursor = None
    try:
        data = _parse_json_body()
        if not data:
            return _json_error(
                'JSON body required.',
                details={'required_keys': list(REQUIRED_PART_KEYS)},
            )

        part_names = _extract_create_build_parts(data)
        required_keys = [
            k
            for k in REQUIRED_PART_KEYS
            if k != 'gpu' or not _is_integrated_gpu_label(part_names.get('gpu', ''))
        ]
        missing_keys = [
            k for k in required_keys
            if k not in part_names or not str(part_names.get(k, '')).strip()
        ]
        if missing_keys:
            return _json_error(
                'Missing required part names.',
                400,
                missing=missing_keys,
                received=list(part_names.keys()),
            )

        user_id = data.get('user_id')
        if user_id is not None and user_id != '':
            try:
                user_id = int(user_id)
            except (TypeError, ValueError):
                return _json_error('user_id must be an integer or null.')
        else:
            user_id = None

        status = str(data.get('status', 'Pending')).strip() or 'Pending'

        connection = get_db_connection()
        cursor = connection.cursor()

        resolved_by_key: dict[str, dict] = {}
        unresolved: list[dict] = []

        for json_key, _column, category in BUILD_PART_SLOTS:
            search_name = part_names.get(json_key, '')
            if json_key == 'gpu' and _is_integrated_gpu_label(search_name):
                continue
            product = find_product_by_name(
                cursor,
                search_name,
                category,
                slot_key=json_key,
            )
            if product:
                resolved_by_key[json_key] = product
            else:
                unresolved.append({
                    'key': json_key,
                    'search': search_name,
                    'category': category,
                })

        if not _CREATE_BUILD_MIN_SLOTS.issubset(resolved_by_key.keys()):
            return _json_error(
                'Could not match core parts (CPU, RAM, storage) in the components catalog.',
                404,
                missing=unresolved,
                matched={k: v['name'] for k, v in resolved_by_key.items()},
            )

        if len(resolved_by_key) < 4:
            return _json_error(
                'Could not match enough parts in the components catalog.',
                404,
                missing=unresolved,
                matched={k: v['name'] for k, v in resolved_by_key.items()},
            )

        total = sum(float(p['price']) for p in resolved_by_key.values())
        total_decimal = Decimal(str(round(total, 2)))
        build_label = str(data.get('name') or data.get('build_name') or 'AI Custom Build').strip()[:150]

        cursor.execute(
            """
            INSERT INTO custom_builds (user_id, name, total_price)
            VALUES (%s, %s, %s)
            """,
            (user_id, build_label or 'AI Custom Build', total_decimal),
        )
        build_id = int(cursor.lastrowid)

        for _slot_key, product in resolved_by_key.items():
            cursor.execute(
                """
                INSERT INTO custom_build_components (custom_build_id, component_id, quantity)
                VALUES (%s, %s, 1)
                """,
                (build_id, product['id']),
            )

        connection.commit()

        return _json_ok(
            201,
            build_id=build_id,
            total_price=float(total_decimal),
            build_status=status,
            parts_sent={k: v for k, v in part_names.items() if k in resolved_by_key},
            skipped_slots=[u['key'] for u in unresolved],
            matched_products={
                key: {
                    'id': resolved_by_key[key]['id'],
                    'name': resolved_by_key[key]['name'],
                    'category': resolved_by_key[key]['category'],
                    'price': resolved_by_key[key]['price'],
                    'stock': resolved_by_key[key]['stock'],
                }
                for key in resolved_by_key
            },
        )

    except ConnectionError as exc:
        return _json_error(str(exc), 503)
    except MySQLError as exc:
        if connection:
            connection.rollback()
        app.logger.exception('create_build MySQL error')
        return _json_error(f'Database error: {exc}', 500)
    except Exception as exc:
        if connection:
            connection.rollback()
        app.logger.exception('create_build failed')
        return _json_error(f'Create build failed: {exc}', 500)
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route('/api/detect/component', methods=['POST', 'OPTIONS'])
def detect_component():
    """YOLO — multipart `image`, JSON base64, or form data URL (Vite contract)."""
    if request.method == 'OPTIONS':
        return '', 204

    try:
        from detect_image_input import parse_confidence, parse_request_image

        pil_image, parse_error = parse_request_image()
        if parse_error:
            return _json_error(parse_error, 400)
        if pil_image is None:
            return _json_error('No valid image data or file received.', 400)

        confidence = parse_confidence(0.35)
        detect_timeout = int(os.getenv('YOLO_DETECT_TIMEOUT', '90'))
        future = _get_yolo_executor().submit(_run_yolo_on_image, pil_image, confidence)
        payload, error = future.result(timeout=detect_timeout)
        if error:
            return _json_error(error, 500)

        return _json_ok(
            count=len(payload['detections']),
            detections=payload['detections'],
            model=payload['model'],
            image_width=payload.get('image_width'),
            image_height=payload.get('image_height'),
        )

    except Exception as exc:
        app.logger.exception('detect_component failed')
        return _json_error(f'Detection failed: {exc}', 500)


def _masked_openai_key_hint() -> str | None:
    key = OPENAI_API_KEY.strip()
    if not key or not _openai_is_configured():
        return None
    if len(key) <= 12:
        return 'sk-…'
    return f'{key[:7]}…{key[-4:]}'


@app.route('/api/ai-status', methods=['GET', 'OPTIONS'])
def ai_status():
    """OpenAI readiness for Chatbot (no Gemini)."""
    if request.method == 'OPTIONS':
        return '', 204

    provider = _resolve_ai_provider()
    openai_ok = _openai_is_configured()

    if openai_ok:
        message = 'OpenAI is ready — live recommendations use ChatGPT (gpt-4o-mini).'
    else:
        message = (
            'Set OPENAI_API_KEY in backend/.env (https://platform.openai.com/api-keys) '
            'with billing enabled ($5 minimum), then restart the server.'
        )

    return _json_ok(
        ai_provider=provider,
        openai_configured=openai_ok,
        ai_active=provider == 'openai',
        gemini_active=provider == 'openai',
        model=_live_model_id() if openai_ok else None,
        openai_model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
        openai_key_hint=_masked_openai_key_hint(),
        env_file=str(APP_DIR / '.env'),
        message=message,
    )


@app.route('/api/verify-stripe', methods=['GET', 'OPTIONS'])
def verify_stripe():
    """
    Safe connectivity check — lists recent PaymentIntents (no secrets in response).
    Requires STRIPE_SECRET_KEY in backend/.env only.
    """
    if request.method == 'OPTIONS':
        return '', 204
    if not stripe_configured():
        return _json_error(
            'STRIPE_SECRET_KEY is missing or invalid in backend/.env',
            400,
        )
    try:
        intents = stripe_sdk.PaymentIntent.list(limit=5)
        rows = [
            {
                'id': pi.id,
                'status': pi.status,
                'amount': pi.amount,
                'currency': pi.currency,
            }
            for pi in (intents.data or [])
        ]
        return _json_ok(
            message='Stripe connected successfully!',
            payment_intents_count=len(rows),
            recent_payment_intents=rows,
        )
    except Exception as exc:
        app.logger.warning('verify_stripe failed: %s', _safe_exc_summary(exc))
        return _json_error(f'Stripe API error: {_safe_exc_summary(exc)}', 400)


@app.route('/api/create-payment-intent', methods=['POST', 'OPTIONS'])
def create_payment_intent():
    """Stripe PaymentIntent — amount in major currency units (PKR/USD per STRIPE_CURRENCY)."""
    if request.method == 'OPTIONS':
        return '', 204

    stripe_status = stripe_config_status()
    app.logger.info(
        'create_payment_intent %s %s origin=%s stripe=%s',
        request.method,
        request.path,
        request.headers.get('Origin'),
        stripe_status,
    )

    if not stripe_configured():
        app.logger.error(
            'create_payment_intent 503 — Stripe not configured: %s',
            stripe_status,
        )
        return _json_error(
            'Stripe is not configured. Set STRIPE_SECRET_KEY in backend/.env',
            503,
        )

    try:
        raw_json = request.get_json(silent=True)
        app.logger.info('create_payment_intent request.json=%s', raw_json)

        data = _parse_json_body()
        amount = float(data.get('amount') or 0)
        app.logger.info('create_payment_intent amount=%s', amount)

        if amount <= 0:
            return _json_error('amount must be greater than zero', 400)

        payload = stripe_create_payment_intent(amount)
        app.logger.info('create_payment_intent stripe response=%s', payload)
        return jsonify(payload), 200
    except Exception as exc:
        app.logger.exception('create_payment_intent failed')
        return jsonify({'error': str(exc)}), 500


@app.route('/api/order/complete-checkout', methods=['POST', 'OPTIONS'])
def order_complete_checkout():
    """
    After Stripe payment succeeds: lock stock, insert order + items, deduct inventory.
    Body: user_id, items[{product_id, quantity, price, vendor_id?}], total_amount,
          payment_intent_id, shipping_address?, shipping_fee?
    """
    if request.method == 'OPTIONS':
        return '', 204
    if not stripe_configured():
        return _json_error(
            'Stripe is not configured. Set STRIPE_SECRET_KEY in backend/.env',
            503,
        )

    data = _parse_json_body()
    user_id = data.get('user_id')
    cart_items = data.get('items') or []
    total_amount = data.get('total_amount')
    payment_intent_id = (data.get('payment_intent_id') or '').strip()

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'user_id must be an integer'}), 400

    try:
        total_amount = float(total_amount)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'total_amount must be a number'}), 400

    try:
        db_kw = _mysql_connect_kwargs()
        db_kw['autocommit'] = False
        result = stripe_complete_checkout(
            db_config=db_kw,
            user_id=user_id,
            cart_items=cart_items,
            total_amount=total_amount,
            payment_intent_id=payment_intent_id,
            shipping_address=str(data.get('shipping_address') or ''),
            shipping_fee=float(data.get('shipping_fee') or 0),
        )
        return jsonify(result), 200
    except MySQLError as err:
        app.logger.exception('complete_checkout database error')
        return jsonify({
            'success': False,
            'message': f'Database offline: {err}',
        }), 500
    except Exception as exc:
        app.logger.warning('complete_checkout rolled back: %s', exc)
        return jsonify({
            'success': False,
            'message': 'Transaction failed, safely rolled back.',
            'error': str(exc),
        }), 500


@app.route('/api/detect/model', methods=['GET', 'OPTIONS'])
def detect_model_info():
    if request.method == 'OPTIONS':
        return '', 204

    path = Path(os.getenv('YOLO_MODEL_PATH', MODEL_PATH))
    return _json_ok(
        model=str(path),
        exists=path.is_file(),
        openai_configured=_openai_is_configured(),
        openai_model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
        api_version=4,
    )


def _log_startup_db_probe() -> None:
    """Runs on import (gunicorn) and before dev server — never raises."""
    if os.getenv('PROBE_DB_ON_START', '1').strip().lower() in ('0', 'false', 'no'):
        return
    try:
        db_ok, db_msg, db_meta = probe_db_connection()
        if db_ok:
            app.logger.info(
                'Startup DB probe OK host=%s ssl=%s',
                db_meta.get('host'),
                db_meta.get('ssl'),
            )
        else:
            app.logger.warning(
                'Startup DB probe failed (API still starts): %s meta=%s',
                db_msg,
                db_meta,
            )
    except Exception as exc:
        app.logger.warning('Startup DB probe error (ignored): %s', exc)


_log_startup_db_probe()


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    _force_utf8_stdio()
    _log_startup_db_probe()
    register_auth_routes(app, get_db_connection, _json_error, _json_ok)
    
    # Railway passes a dynamic port via environment variables
    port = int(os.environ.get('PORT', 5000))
    
    # host="0.0.0.0" is mandatory for Railway to detect the running container
    app.run(host="0.0.0.0", port=port, debug=False)
