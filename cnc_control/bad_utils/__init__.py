"""
Утилиты для работы с данными.
"""

from .bbox_utils import (
    validate_bbox,
    normalize_bbox,
    get_bbox_center,
    get_bbox_size,
    rotate_bbox
)

__all__ = [
    'validate_bbox',
    'normalize_bbox',
    'get_bbox_center',
    'get_bbox_size',
    'rotate_bbox',
]
