"""
Application-wide constants and configuration.
Centralized definitions to avoid magic strings and hardcoded values.
"""

# YOLO Object Detection Classes
YOLO_CLASS_NAMES = {
    0: 'mouse',
    1: 'keyboard',
    2: 'monitor',
    3: 'ram',
}

# PC Build Configuration
BUILD_REQUIRED_TYPES = ('CPU', 'GPU', 'Motherboard', 'RAM', 'Storage', 'PSU', 'Case')

BUILD_PART_SLOTS = (
    ('cpu', 'cpu', 'CPU'),
    ('gpu', 'gpu', 'GPU'),
    ('motherboard', 'motherboard', 'Motherboard'),
    ('ram', 'ram', 'RAM'),
    ('storage', 'storage', 'Storage'),
    ('psu', 'psu', 'PSU'),
    ('case', 'case', 'Case'),
)

CREATE_BUILD_MIN_SLOTS = frozenset({'cpu', 'ram', 'storage'})

# Build table formatting for Markdown output
BUILD_TABLE_COLUMNS = '| Component Type | Component Name | Estimated Price |'
BUILD_TABLE_SEPARATOR = '|----------------|-----------------|------------------|'

# CORS - Frontend Origins
CORS_ORIGINS = [
    'https://genspark-frontend.vercel.app',
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:4173',
    'http://127.0.0.1:4173',
]

# Order Statuses
ORDER_STATUS_PENDING = 'Pending'
ORDER_STATUS_COMPLETED = 'Completed'
ORDER_STATUS_FAILED = 'Failed'

# Component Categories
COMPONENT_CATEGORY_CPU = 'CPU'
COMPONENT_CATEGORY_GPU = 'GPU'
COMPONENT_CATEGORY_RAM = 'RAM'
COMPONENT_CATEGORY_STORAGE = 'Storage'
COMPONENT_CATEGORY_PSU = 'PSU'
COMPONENT_CATEGORY_CASE = 'Case'
COMPONENT_CATEGORY_MOTHERBOARD = 'Motherboard'

# Confidence Threshold for Detection Display
DISPLAY_CONFIDENCE_THRESHOLD_PCT = 60
