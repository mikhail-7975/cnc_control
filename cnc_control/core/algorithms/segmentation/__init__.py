"""
Модули для сегментации компонентов на изображениях.
"""
from cnc_control.core.algorithms.segmentation.preprocessing import ImagePreprocessor
from cnc_control.core.algorithms.segmentation.segmentation import ComponentSegmenter
from cnc_control.core.algorithms.segmentation.postprocessing import MaskPostprocessor
from cnc_control.core.algorithms.segmentation.metrics import (
    calculate_iou,
    get_bottom_edge_angle,
    calculate_angle_difference
)

__all__ = [
    'ImagePreprocessor',
    'ComponentSegmenter',
    'MaskPostprocessor',
    'calculate_iou',
    'get_bottom_edge_angle',
    'calculate_angle_difference'
]
