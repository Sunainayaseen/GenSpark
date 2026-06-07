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
