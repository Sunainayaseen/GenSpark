"""
Component knowledge base — answers "what is / use of / explain <component>"
questions in the GenSpark chatbot (deterministic, no LLM).

Returns clean professional Markdown (no decorative emojis) that the React
BuildRecommendationCard renders as a normal chat reply.
"""
from __future__ import annotations

import re

# key -> {title, aliases, use, points[], tips[]}
COMPONENT_INFO = {
    'cpu': {
        'title': 'CPU — Central Processing Unit',
        'aliases': ('cpu', 'processor', 'ryzen', 'core i', 'i3', 'i5', 'i7', 'i9', 'xeon', 'athlon'),
        'use': ('The CPU is the brain of the PC. It executes the operating system, '
                'application logic, and game simulation/AI — anything that is not pure graphics.'),
        'points': [
            'Cores & threads decide multitasking and how well it handles heavy apps (editing, compiling, VMs).',
            'Clock speed (GHz) and IPC drive single-thread performance — important for gaming and everyday snappiness.',
            'Must match the motherboard socket (e.g. AM5 for Ryzen 7000/9000, LGA1700 for Intel 12–14th gen).',
        ],
        'tips': [
            'Pair the CPU tier with the GPU to avoid a bottleneck (e.g. Ryzen 5 7600 + RTX 4060).',
            'High-TDP / K-series chips need a capable cooler and a stronger-VRM motherboard.',
        ],
    },
    'gpu': {
        'title': 'GPU — Graphics Processing Unit',
        'aliases': ('gpu', 'graphics card', 'graphics', 'vga', 'rtx', 'gtx', 'radeon', 'geforce', 'video card'),
        'use': ('The GPU renders everything you see in 3D — games, ray tracing, video playback — and '
                'accelerates video editing, 3D rendering, and AI/ML workloads.'),
        'points': [
            'It is the single biggest factor for gaming FPS and resolution (1080p / 1440p / 4K).',
            'VRAM (e.g. 8–16 GB) matters for high textures, higher resolutions, and AI models.',
            'Check physical length vs your case clearance and the PSU power connectors it needs.',
        ],
        'tips': [
            'For 1080p gaming an RTX 4060 / RX 7600 class card is a strong value pick.',
            'Office/basic builds can skip a discrete GPU and use the CPU’s integrated graphics.',
        ],
    },
    'motherboard': {
        'title': 'Motherboard — The Mainboard',
        'aliases': ('motherboard', 'mainboard', 'mobo', 'b550', 'b650', 'x670', 'b760', 'a520', 'h610'),
        'use': ('The motherboard connects every component together — CPU, RAM, GPU, storage — and '
                'distributes power and data between them.'),
        'points': [
            'The socket + chipset must match the CPU (AM5 → B650/X670, LGA1700 → B760/Z790).',
            'Decides RAM type/speed support (DDR4 vs DDR5), PCIe version, and number of M.2/expansion slots.',
            'Form factor (ATX / mATX / ITX) must fit your case.',
        ],
        'tips': [
            'Stronger VRMs give stable power for high-end or overclocked CPUs.',
            'Look for the I/O you need: Wi‑Fi, USB-C, enough M.2 slots.',
        ],
    },
    'ram': {
        'title': 'RAM — Memory',
        'aliases': ('ram', 'memory', 'ddr4', 'ddr5', 'dimm'),
        'use': ('RAM is fast, temporary workspace that holds your open apps, game assets, and active '
                'data so the CPU can reach them instantly.'),
        'points': [
            '16 GB is the comfortable baseline today; 32 GB+ suits editing, heavy multitasking, and VMs.',
            'Run two sticks (dual-channel) for noticeably better bandwidth than a single stick.',
            'Generation must match the platform — DDR4 or DDR5 depending on the motherboard.',
        ],
        'tips': [
            'Enable XMP/EXPO in BIOS to actually run RAM at its rated speed.',
            'Faster RAM (e.g. DDR5-6000) helps Ryzen and 1% lows in games.',
        ],
    },
    'storage': {
        'title': 'Storage — SSD / NVMe / HDD',
        'aliases': ('storage', 'ssd', 'nvme', 'hdd', 'hard disk', 'hard drive', 'm.2', 'sata'),
        'use': ('Storage permanently keeps your OS, programs, games, and files. An NVMe SSD makes the '
                'whole system boot and load dramatically faster than a hard drive.'),
        'points': [
            'NVMe (M.2) SSD is the best choice for your OS/boot drive — much faster than SATA or HDD.',
            'Capacity: 500 GB–1 TB is a sensible start; add a large HDD only for bulk archival storage.',
            'Endurance (TBW) indicates how long a drive will reliably last.',
        ],
        'tips': [
            'Put Windows + your main apps/games on the NVMe SSD for the biggest speed gain.',
        ],
    },
    'psu': {
        'title': 'PSU — Power Supply Unit',
        'aliases': ('psu', 'power supply', 'smps', 'wattage', '80 plus', 'bronze', 'gold'),
        'use': ('The PSU converts wall AC into the clean, stable DC power every component needs. A weak '
                'or low-quality PSU can crash or even damage the system.'),
        'points': [
            'Size the wattage to CPU + GPU power plus ~100–150 W headroom for spikes and upgrades.',
            'Prefer an 80 PLUS Bronze/Gold unit from a reputable brand for efficiency and safety.',
            'Make sure it has the right PCIe connectors for your GPU.',
        ],
        'tips': [
            'A mid-range gaming build is usually happy on a quality 650 W Gold PSU.',
        ],
    },
    'case': {
        'title': 'Case — Chassis & Airflow',
        'aliases': ('case', 'chassis', 'cabinet', 'tower', 'mid tower', 'full tower'),
        'use': ('The case houses and protects your parts, routes airflow to keep them cool, and helps '
                'with cable management for a clean build.'),
        'points': [
            'Check GPU length and CPU-cooler height clearance before buying.',
            'Good front-to-back/top airflow (mesh fronts) keeps temperatures and noise down.',
            'It must support your motherboard size (ATX / mATX / ITX).',
        ],
        'tips': [
            'A mesh mid-tower with 2–3 fans is the safe, cool, quiet default for most builds.',
        ],
    },
    'cooler': {
        'title': 'CPU Cooler — Air / Liquid',
        'aliases': ('cooler', 'cpu cooler', 'air cooler', 'liquid cooler', 'aio', 'heatsink', 'thermal paste'),
        'use': ('The cooler removes heat from the CPU so it can hold high clock speeds without throttling.'),
        'points': [
            'A good air cooler handles most CPUs; high-end/overclocked chips benefit from a 240–360 mm AIO.',
            'Make sure the cooler supports your CPU socket and fits the case height/radiator space.',
            'Quality thermal paste and correct mounting matter as much as the cooler size.',
        ],
        'tips': [
            'Stock coolers are fine for low-TDP CPUs; upgrade for hot, many-core chips.',
        ],
    },
}

# Map every alias to its component key (longest aliases first for accuracy).
_ALIAS_TO_KEY = []
for _k, _info in COMPONENT_INFO.items():
    for _a in _info['aliases']:
        _ALIAS_TO_KEY.append((_a, _k))
_ALIAS_TO_KEY.sort(key=lambda t: len(t[0]), reverse=True)

# "what is / use of / explain / kis liye / kya hai / details / function / role"
_QUESTION_RE = re.compile(
    r'\b(use|used|uses|what\s+is|what\'?s|explain|detail|details|function|purpose|role|'
    r'kis\s+liye|kis\s+lie|kya\s+ha|kya\s+hai|kaam|kaam\s+kya|btao|bta|batao|meaning|'
    r'kyun|kyu|hota\s+hai|hoti\s+hai|difference|vs)\b',
    re.I,
)


def detect_component_query(message: str) -> str | None:
    """Return a component key if the message is an info question about it, else None."""
    text = re.sub(r'\s+', ' ', (message or '').strip().lower())
    if not text:
        return None
    key = None
    for alias, ckey in _ALIAS_TO_KEY:
        if re.search(rf'(?<![a-z]){re.escape(alias)}(?![a-z])', text):
            key = ckey
            break
    if not key:
        return None
    # Treat as an info request when it's a question OR a very short lookup ("gpu", "use of gpu").
    word_count = len(text.split())
    if _QUESTION_RE.search(text) or word_count <= 4:
        return key
    return None


def render_component_info(key: str) -> str:
    info = COMPONENT_INFO.get(key)
    if not info:
        return ''
    lines = [
        f'## {info["title"]}',
        '',
        f'**What it does:** {info["use"]}',
        '',
        '**Why it matters:**',
    ]
    lines += [f'- {p}' for p in info['points']]
    if info.get('tips'):
        lines += ['', '**Tips:**']
        lines += [f'- {t}' for t in info['tips']]
    lines += [
        '',
        '_Tell me your budget and purpose (e.g. “gaming build 150k”) and I’ll recommend a full, '
        'compatible, in-stock configuration._',
    ]
    return '\n'.join(lines)
