"""
GenSpark rule-based chat intelligence — no LLM required.

Handles greetings, component examination (educational), and routes PC build
requests to the catalog engine in app.py.
"""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Component knowledge base (examination / educational)
# ---------------------------------------------------------------------------
COMPONENT_DETAILS: dict[str, dict[str, Any]] = {
    'cpu': {
        'title': 'Central Processing Unit (CPU) — The Brain',
        'use': (
            'Yeh system ka primary engine hai jo computational instructions, game physics, '
            'logic processing, aur OS tasks handle karta hai.'
        ),
        'examination_points': [
            'Socket Compatibility: CPU socket (e.g., LGA1700, AM4) motherboard socket se match hona chahiye.',
            'TDP & Cooling: K-series Intel ya high-end AMD CPUs ke liye aftermarket cooler zaroori ho sakta hai.',
            'Bottleneck Check: GPU tier ke mutabiq CPU select karein (e.g., i5-12400F + RTX 3060).',
        ],
        'aliases': (
            'cpu', 'processor', 'i3', 'i5', 'i7', 'i9', 'ryzen', 'core i5',
            'core i7', 'threadripper',
        ),
    },
    'gpu': {
        'title': 'Graphics Processing Unit (GPU) — Visual Engine',
        'use': (
            '3D graphics rendering, frame generation, texture filtering, aur video encoding ke liye. '
            'Gaming aur video editing ka zyada hissa GPU par depend karta hai.'
        ),
        'examination_points': [
            'VRAM Requirement: 1080p/1440p gaming ke liye 8GB–12GB VRAM (e.g., RTX 3060 12GB) behtar hai.',
            'PSU Clearance: PCIe power connectors aur total PSU wattage (e.g., 650W) verify karein.',
            'Physical Dimensions: GPU length case/chassis clearance ke andar fit honi chahiye.',
        ],
        'aliases': (
            'gpu', 'graphics card', 'graphics', 'vga', 'rtx', 'gtx', 'radeon', 'geforce',
            '3060', '4060', '4070', 'video card',
        ),
    },
    'motherboard': {
        'title': 'Motherboard — Central Nervous System',
        'use': (
            'CPU, RAM, GPU, aur storage ko interconnect karta hai aur power distribute karta hai.'
        ),
        'examination_points': [
            'VRM Quality: High-end CPUs ke liye strong VRM heatsinks voltage stability ke liye.',
            'RAM & PCIe Slots: DDR4 vs DDR5 aur PCIe Gen 4.0/5.0 lanes verify karein.',
            'Form Factor: ATX, Micro-ATX, ya Mini-ITX case size ke mutabiq hona chahiye.',
        ],
        'aliases': ('motherboard', 'mobo', 'mainboard', 'board', 'b760', 'b550', 'h610', 'x670'),
    },
    'ram': {
        'title': 'Random Access Memory (RAM) — Short-term Workspace',
        'use': (
            'Active programs, game assets, aur background tasks ka temporary data store — '
            'CPU ko fast access ke liye.'
        ),
        'examination_points': [
            'Dual Channel: 2 sticks (e.g., 8GB×2) bandwidth double karta hai vs single stick.',
            'Frequency & XMP: Ryzen par 3200/3600MHz DDR4 common sweet spot; XMP/EXPO enable karein.',
            'Clearance: Large air coolers ke sath tall RGB RAM height check karein.',
        ],
        'aliases': ('ram', 'memory', 'ddr4', 'ddr5', 'dimm', 'dram'),
    },
    'storage': {
        'title': 'Storage (NVMe SSD / HDD) — Long-term Memory',
        'use': (
            'OS, games, aur files permanent store karta hai. NVMe SSDs SATA se kaafi tez hoti hain.'
        ),
        'examination_points': [
            'Protocol Type: NVMe M.2 SSDs SATA SSDs se zyada fast hoti hain boot/load ke liye.',
            'DRAM Cache: Boot drive par DRAM cache wali SSD heavy workloads mein stable rehti hai.',
            'Endurance (TBW): Drive lifespan indicator — zyada TBW = zyada reliability margin.',
        ],
        'aliases': ('storage', 'ssd', 'nvme', 'hdd', 'hard disk', 'hard drive', 'm.2', 'sata'),
    },
    'psu': {
        'title': 'Power Supply Unit (PSU) — System Heartbeat',
        'use': (
            'AC ko safe DC mein convert karke har sensitive component ko stable power deta hai.'
        ),
        'examination_points': [
            'Efficiency Rating: Minimum 80 Plus Bronze/Gold certified PSU prefer karein.',
            'Tier List Rating: Reputable tier lists par Tier B ya behtar units safer hain.',
            'Continuous Wattage: Total load se 100W–150W buffer future upgrades ke liye.',
        ],
        'aliases': ('psu', 'power supply', 'smps', 'wattage', '650w', '750w', '80 plus'),
    },
    'case': {
        'title': 'PC Case / Chassis — Enclosure & Airflow',
        'use': (
            'Components ko protect karta hai, airflow route karta hai, aur cable management provide karta hai.'
        ),
        'examination_points': [
            'GPU Length Clearance: Long graphics cards ke liye max GPU length spec check karein.',
            'Airflow Path: Front intake + rear/top exhaust positive pressure airflow ke liye.',
            'Form Factor Support: Motherboard size (ATX/mATX/ITX) case spec se match hona chahiye.',
        ],
        'aliases': ('case', 'chassis', 'cabinet', 'tower', 'mid tower'),
    },
}

_USE_PATTERNS = re.compile(
    r'\b(use|used|kyun|kyu|kis\s+liye|kis\s+lye|what\s+is|what\'s|kaam|purpose|'
    r'details|detail|function|explain|btao|btayein|btana|batayein|batana|'
    r'kya\s+hai|kya\s+ha|hot[ae]\s+hai|hoti\s+hai|meaning|role|for\s+what)\b',
    re.I,
)

_BUILD_SIGNAL = re.compile(
    r'\b(build|setup|rig|pc\s+build|banado|bana\s+do|recommend|budget|lakh|lac|'
    r'\d{2,3}\s*k\b|\d{5,7})\b',
    re.I,
)

_GREETING_PATTERNS = (
    re.compile(r'^(hi|hello|hey|yo|sup|aoa|salam|assalam)\b', re.I),
    re.compile(r'\b(how\s+are\s+you|how\s+r\s+u|kaise\s+ho|kaise\s+hain)\b', re.I),
    re.compile(r'\b(kia\s+hal|kya\s+hal|salam\s+alaikum|assalam\s+o\s+alaikum)\b', re.I),
    re.compile(r'^(good\s+(morning|evening|afternoon))\b', re.I),
)

# Rotating professional greetings (deterministic pick by message hash)
GREETING_VARIANTS: tuple[str, ...] = (
    """### 👋 Welcome to GenSpark Builds

Main aapka **professional hardware configurator** hoon. Budget + purpose batayein (e.g. *gaming pc 1.20 lakh*) ya kisi component ka technical use poochhein (*GPU kis liye hota hai?*).

**Shuru karne ke liye:**
1. 💰 Target budget — *80k office setup*, *1.20 lakh gaming*
2. 🛠️ Purpose — Gaming, Office, Editing
3. 📷 Vision se owned parts exclude ho sakte hain (mouse, keyboard, RAM, monitor)""",
    """### 👋 Assalam-o-Alaikum — GenSpark Builds

Aap mujhse **compatible PC builds**, **component examination**, aur **budget planning** ke liye Roman Urdu ya English mein baat kar sakte hain.

*Examples:*
- *"Office work 70k rigid setup"*
- *"RTX 3060 kis liye use hota hai?"*
- *"Explain CPU socket compatibility"*""",
    """### 👋 Hello! Build Assistant Guide

Ready when you are. Mujhe apna **budget (PKR)** aur **workload** bhejein — main structured parts table, compatibility badges, aur vendor-ready estimate return karunga.

Agar sirf learning mode chahiye: component naam + *kis liye / explain* likhein.""",
)


def _normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', (text or '').strip().lower())


def _word_count(text: str) -> int:
    return len(re.sub(r'[^\w\s]', '', text).split())


def _has_use_question(text: str) -> bool:
    return bool(_USE_PATTERNS.search(text))


def _has_build_signal(text: str) -> bool:
    return bool(_BUILD_SIGNAL.search(text))


def _is_pure_greeting(text: str) -> bool:
    if not text:
        return True
    if _has_build_signal(text) or _has_use_question(text):
        return False
    if any(p.search(text) for p in _GREETING_PATTERNS):
        return _word_count(text) <= 8
    cleaned = re.sub(r'[^\w]', '', text)
    if 0 < len(cleaned) <= 3:
        return True
    return False


def _pick_greeting_markdown(message: str) -> str:
    idx = sum(ord(c) for c in message) % len(GREETING_VARIANTS)
    return GREETING_VARIANTS[idx]


def _match_component_key(text: str) -> str | None:
    """Return component key if aliases match (word boundaries)."""
    for key, details in COMPONENT_DETAILS.items():
        for alias in details['aliases']:
            if re.search(rf'\b{re.escape(alias)}\b', text, re.I):
                return key
    return None


def _format_examination_markdown(component_key: str) -> str:
    details = COMPONENT_DETAILS[component_key]
    lines = [
        f"### 🛠️ Professional Hardware Examination: {details['title']}",
        '',
        '**Core Purpose & Functionality:**',
        f"> {details['use']}",
        '',
        '**Critical Examination & Compatibility Points:**',
    ]
    for point in details['examination_points']:
        if ':' in point:
            label, body = point.split(':', 1)
            lines.append(f'* **{label.strip()}:**{body.strip()}')
        else:
            lines.append(f'* {point}')
    lines.extend([
        '',
        '---',
        '*GenSpark Rules Engine · deterministic hardware advisory — no external AI.*',
    ])
    return '\n'.join(lines)


def unknown_help_markdown() -> str:
    return """### 📋 GenSpark — How can I help?

Main aapka message poori tarah match nahi kar saka. Yeh formats try karein:

1. **Budget PC:** `gaming pc build 1.20 lakh` ya `office setup 80k`
2. **Component info:** `GPU kis liye use hota hai?` · `Explain CPU socket`
3. **Greeting:** `salam` · `how are you`

Left panel se purpose/budget set karke **Get recommendations** bhi use kar sakte hain."""


# ---------------------------------------------------------------------------
# Upgrade compatibility — rule-based validation (no LLM, no ML)
#
# The user's CURRENT configuration and the REQUESTED upgrade are parsed straight
# from the chat message ("I have a B550 DDR4 board with 16GB, upgrade to 32GB").
# The combination is then checked against fixed platform rules — memory
# generation and CPU socket. Compatible -> upgrade options; otherwise a
# highlighted "Incompatible Configuration" warning. Fast, deterministic.
# ---------------------------------------------------------------------------

_UPGRADE_SIGNAL = re.compile(
    r'\b(?:'
    r'upgrade[ds]?|upgradation|increase|bump|raise|barha\w*|'        # explicit upgrade
    r'switch\s+to|move\s+to|change\s+to|swap|'                       # swap phrasing
    r'install|fit|fits|fitting|support|supports|supported|'         # EN: will it fit/support
    r'compatib\w*|'                                                  # compatible/compatibility
    r'lag\w*|daal\w*|'                                               # Roman Urdu: lagao/lagega/lagti/install
    r'chalega|chalegi|'                                              # Roman Urdu: will it run
    r'use\s+kar\w*|kaam\s+kar\w*'                                    # Roman Urdu: will it work
    r')\b'
    r'|\blag\s+(?:sak|ja)\w*|\bchal\s+sak\w*',                       # "lag sakti", "lag jayegi", "chal sakta"
    re.I,
)

# Motherboard chipset -> CPU socket platform.
_CHIPSET_SOCKET: dict[str, str] = {
    'a320': 'AM4', 'b350': 'AM4', 'b450': 'AM4', 'b550': 'AM4',
    'x370': 'AM4', 'x470': 'AM4', 'x570': 'AM4', 'a520': 'AM4',
    'a620': 'AM5', 'b650': 'AM5', 'x670': 'AM5', 'b840': 'AM5',
    'b850': 'AM5', 'x870': 'AM5',
    'h410': 'LGA1200', 'b460': 'LGA1200', 'h470': 'LGA1200', 'z490': 'LGA1200',
    'h510': 'LGA1200', 'b560': 'LGA1200', 'h570': 'LGA1200', 'z590': 'LGA1200',
    'h610': 'LGA1700', 'b660': 'LGA1700', 'h670': 'LGA1700', 'b760': 'LGA1700',
    'h770': 'LGA1700', 'z690': 'LGA1700', 'z790': 'LGA1700',
}

# Socket -> memory generation. LGA1700 boards ship as EITHER DDR4 or DDR5, so for
# that platform the generation must come from an explicit DDR mention (omitted).
_SOCKET_RAM_GEN: dict[str, str] = {
    'AM4': 'DDR4',
    'AM5': 'DDR5',
    'LGA1200': 'DDR4',
    'LGA1151': 'DDR4',
}

_CHIPSET_RE = re.compile(
    r'\b(a320|b350|b450|b550|x370|x470|x570|a520|a620|b650|x670|b840|b850|x870|'
    r'h410|b460|h470|z490|h510|b560|h570|z590|h610|b660|h670|b760|h770|z690|z790)\b',
    re.I,
)
_SOCKET_RE = re.compile(r'\b(am4|am5|lga\s*1200|lga\s*1700|lga\s*1151)\b', re.I)
_DDR_RE = re.compile(r'\bddr\s*([345])\b', re.I)
_RAM_SIZE_RE = re.compile(r'(\d{1,3})\s*gb\b', re.I)
_RAM_KEYWORD_RE = re.compile(r'\b(ram|memory|ddr\s*[345]|dimm)\b', re.I)
_GPU_KEYWORD_RE = re.compile(r'\b(gpu|graphics\s*card|rtx|gtx|radeon|geforce|arc)\b', re.I)
_STORAGE_KEYWORD_RE = re.compile(r'\b(ssd|nvme|hdd|storage|hard\s*disk|m\.?2)\b', re.I)


def _platform_socket_from_board(text: str) -> str | None:
    """Socket implied by a stated motherboard chipset or explicit socket only."""
    m = _CHIPSET_RE.search(text)
    if m:
        return _CHIPSET_SOCKET[m.group(1).lower()]
    m = _SOCKET_RE.search(text)
    if m:
        return re.sub(r'\s+', '', m.group(1).upper())
    return None


def _board_label(text: str, socket: str | None) -> str:
    """Human-friendly board name — the chipset the user named (B550), else socket."""
    m = _CHIPSET_RE.search(text)
    if m:
        return m.group(0).upper()
    return socket or ''


def _requested_cpu_socket(text: str) -> str | None:
    """Socket of a concrete CPU model named in the message, else None."""
    # AMD Ryzen — socket by thousands digit of the model number.
    m = re.search(r'ryzen\s*[3579]?\s*(\d)\d{3}', text)
    if m:
        series = m.group(1)
        if series in ('1', '2', '3', '4', '5'):
            return 'AM4'
        if series in ('7', '8', '9'):
            return 'AM5'
    # Intel Core — socket by generation (first 1-2 digits of the model number).
    m = re.search(r'(?:core\s*)?i[3579]\D*?(\d{4,5})\b', text)
    if m:
        model = m.group(1)
        gen = int(model[:2]) if len(model) == 5 else int(model[0])
        if gen in (8, 9):
            return 'LGA1151'
        if gen in (10, 11):
            return 'LGA1200'
        if gen in (12, 13, 14):
            return 'LGA1700'
    return None


def _upgrade_result(message: str, component: str) -> dict[str, Any]:
    return {
        'intent': 'upgrade_request',
        'badge': 'GenSpark Upgrade Validator',
        'message': message,
        'component': component,
    }


def _compat_table(rows: list[tuple[str, str, bool]]) -> str:
    """Scannable ✓/✗ table; the conflicting row's spec is bolded to stand out."""
    out = ['| Component | Spec | Status |', '|---|---|:--:|']
    for component, spec, ok in rows:
        spec_cell = spec if ok else f'**{spec}**'
        out.append(f'| {component} | {spec_cell} | {"✅" if ok else "❌"} |')
    return '\n'.join(out)


def _evaluate_ram_upgrade(text: str) -> dict[str, Any]:
    sizes = [int(s) for s in _RAM_SIZE_RE.findall(text)]
    ddr_gens = ['DDR' + g for g in _DDR_RE.findall(text)]
    # Platform generation: chipset/socket first, then any current CPU mentioned.
    socket = _platform_socket_from_board(text) or _requested_cpu_socket(text)
    board_gen = _SOCKET_RAM_GEN.get(socket) if socket else None

    target_cap = max(sizes) if sizes else None
    current_cap = min(sizes) if len(sizes) >= 2 else None
    # Current generation = the board's fixed generation, else the first DDR named.
    current_gen = board_gen or (ddr_gens[0] if ddr_gens else None)
    requested_gen = ddr_gens[-1] if ddr_gens else None

    # Incompatible: requested memory generation ≠ the board's fixed generation.
    if current_gen and requested_gen and current_gen != requested_gen:
        label = _board_label(text, socket)
        board_spec = f'{label} · {current_gen}' if label else current_gen
        ram_spec = f'{target_cap}GB {requested_gen}' if target_cap else requested_gen
        table = _compat_table([
            ('Motherboard', board_spec, True),
            ('RAM', ram_spec, False),
        ])
        msg = (
            '### ⚠️ Incompatible\n\n'
            f'{table}\n\n'
            f'**{requested_gen} RAM {current_gen} board pe nahi lagti** — alag slot.\n\n'
            f'✅ Instead: bara **{current_gen}** kit, ya {requested_gen} board + naya CPU.'
        )
        return _upgrade_result(msg, 'ram')

    gen = current_gen or requested_gen or 'DDR4/DDR5'
    gen_txt = '' if gen == 'DDR4/DDR5' else f' {gen}'

    # Not actually an increase (e.g. 32GB → 16GB).
    if target_cap and current_cap and target_cap <= current_cap:
        msg = (
            '### 🟢 Compatible\n\n'
            f'**{target_cap}GB{gen_txt}** chal jayega, par ye {current_cap}GB se zyada nahi. '
            f'Bara target batayein (e.g. {current_cap * 2}GB).'
        )
        return _upgrade_result(msg, 'ram')

    cap = target_cap or 32
    speed = '5600MHz' if gen == 'DDR5' else '3200MHz'
    msg = (
        '### 🟢 Compatible — RAM\n\n'
        f'**{cap}GB{gen_txt}** aapke platform pe lag jayegi ✅\n\n'
        f'- Best: 2×{cap // 2}GB {gen if gen != "DDR4/DDR5" else "DDR4"}-{speed} dual-channel (XMP/EXPO on).'
    )
    return _upgrade_result(msg, 'ram')


def _evaluate_cpu_upgrade(text: str, want_socket: str) -> dict[str, Any]:
    board = _platform_socket_from_board(text)

    if board and board != want_socket:
        board_spec = f'{_board_label(text, board)} · {board}'
        table = _compat_table([
            ('Motherboard', board_spec, True),
            ('CPU', f'requested {want_socket}', False),
        ])
        msg = (
            '### ⚠️ Incompatible\n\n'
            f'{table}\n\n'
            f'**{want_socket} CPU {board} board pe fit nahi hoti** — socket alag.\n\n'
            f'✅ Instead: koi **{board}** CPU, ya {want_socket} board + matching RAM.'
        )
        return _upgrade_result(msg, 'cpu')

    if not board:
        msg = (
            '### 🟢 Likely Compatible — CPU\n\n'
            f'Agar aapka board **{want_socket}** hai to lag jayega ✅ (latest BIOS flash karein). '
            'Pukka confirm ke liye board chipset batayein (e.g. B550, B760).'
        )
        return _upgrade_result(msg, 'cpu')

    msg = (
        '### 🟢 Compatible — CPU\n\n'
        f'CPU aapke **{board}** board pe lag jayega ✅ Latest BIOS flash karein.'
    )
    return _upgrade_result(msg, 'cpu')


def _evaluate_simple_upgrade(component: str) -> dict[str, Any]:
    if component == 'gpu':
        msg = (
            '### 🟢 Compatible — GPU\n\n'
            'GPU PCIe slot mein fit hai ✅ Bas **PSU wattage + PCIe connectors** aur **case length** confirm karein.'
        )
        return _upgrade_result(msg, 'gpu')
    msg = (
        '### 🟢 Compatible — Storage\n\n'
        'Storage upgrade compatible hai ✅ NVMe ke liye free **M.2 slot**, SATA ke liye koi bhi board.'
    )
    return _upgrade_result(msg, 'storage')


def evaluate_upgrade_request(user_input: str) -> dict[str, Any] | None:
    """
    Validate a stated upgrade against fixed platform rules.

    Returns an intent dict (intent='upgrade_request', badge, message, component)
    when the message is a parseable upgrade request, else None so the caller can
    fall through to its normal intent handling.
    """
    text = _normalize(user_input)
    if not text or not _UPGRADE_SIGNAL.search(text):
        return None

    has_ram = bool(_RAM_KEYWORD_RE.search(text)) and bool(_RAM_SIZE_RE.search(text))
    if has_ram:
        return _evaluate_ram_upgrade(text)

    cpu_socket = _requested_cpu_socket(text)
    if cpu_socket:
        return _evaluate_cpu_upgrade(text, cpu_socket)

    if _GPU_KEYWORD_RE.search(text):
        return _evaluate_simple_upgrade('gpu')
    if _STORAGE_KEYWORD_RE.search(text):
        return _evaluate_simple_upgrade('storage')

    return None


def analyze_user_message(
    user_input: str,
    *,
    want_build: bool = False,
    budget: str = '',
    purpose: str = '',
) -> dict[str, Any]:
    """
    Deep rule-based intent analysis.

    Returns:
        intent: greeting | component_examination | pc_build_request | clarify | unknown
        badge: UI label string
        message: markdown response (may be empty for pc_build_request)
        component: matched component key or None
    """
    text = _normalize(user_input)
    response: dict[str, Any] = {
        'intent': 'unknown',
        'badge': 'GenSpark Assistant',
        'message': '',
        'component': None,
    }

    if not text:
        response['intent'] = 'greeting'
        response['badge'] = 'Build Assistant Guide'
        response['message'] = _pick_greeting_markdown('')
        return response

    upgrade = evaluate_upgrade_request(user_input)
    if upgrade is not None:
        return {**response, **upgrade}

    component_key = _match_component_key(text)
    short_component_query = component_key and _word_count(text) <= 4
    if component_key and (_has_use_question(text) or short_component_query):
        response['intent'] = 'component_examination'
        response['badge'] = f'{component_key.upper()} Expert Guide'
        response['component'] = component_key
        response['message'] = _format_examination_markdown(component_key)
        return response

    if _is_pure_greeting(text) and not want_build:
        response['intent'] = 'greeting'
        response['badge'] = 'Build Assistant Guide'
        response['message'] = _pick_greeting_markdown(user_input)
        return response

    if want_build or _has_build_signal(text) or (budget or '').strip() or (purpose or '').strip():
        response['intent'] = 'pc_build_request'
        response['badge'] = 'GenSpark Rules Engine'
        response['message'] = ''
        return response

    if component_key:
        response['intent'] = 'component_examination'
        response['badge'] = f'{component_key.upper()} Expert Guide'
        response['component'] = component_key
        response['message'] = _format_examination_markdown(component_key)
        return response

    response['intent'] = 'clarify'
    response['badge'] = 'Build Assistant Guide'
    response['message'] = unknown_help_markdown()
    return response
