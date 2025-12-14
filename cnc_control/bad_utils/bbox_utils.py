"""
Утилиты для работы с bounding boxes (bbox).
"""
import numpy as np
import cv2
from typing import Dict, Tuple, Optional


def validate_bbox(bbox: Dict) -> bool:
    """
    Проверяет корректность bbox.
    
    Args:
        bbox: Словарь с ключами x1, y1, x2, y2, angle
        
    Returns:
        bool: True если bbox корректен
    """
    required_keys = ['x1', 'y1', 'x2', 'y2']
    if not all(key in bbox for key in required_keys):
        return False
    
    x1, y1, x2, y2 = bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2']
    
    if x1 >= x2 or y1 >= y2:
        return False
    
    if 'angle' in bbox:
        angle = bbox['angle']
        if not (-90 <= angle <= 90):
            return False
    
    return True


def normalize_bbox(bbox: Dict) -> Dict:
    """
    Нормализует bbox, гарантируя что x1 < x2 и y1 < y2.
    
    Args:
        bbox: Словарь с координатами bbox
        
    Returns:
        Dict: Нормализованный bbox
    """
    x1, y1 = bbox['x1'], bbox['y1']
    x2, y2 = bbox['x2'], bbox['y2']
    
    normalized = {
        'x1': min(x1, x2),
        'y1': min(y1, y2),
        'x2': max(x1, x2),
        'y2': max(y1, y2),
    }
    
    if 'angle' in bbox:
        normalized['angle'] = bbox['angle']
    if 'bbox_id' in bbox:
        normalized['bbox_id'] = bbox['bbox_id']
    
    return normalized


def get_bbox_center(bbox: Dict) -> Tuple[float, float]:
    """
    Вычисляет центр bbox.
    
    Args:
        bbox: Словарь с координатами bbox
        
    Returns:
        Tuple[float, float]: Координаты центра (x, y)
    """
    x_center = (bbox['x1'] + bbox['x2']) / 2.0
    y_center = (bbox['y1'] + bbox['y2']) / 2.0
    return (x_center, y_center)


def get_bbox_size(bbox: Dict) -> Tuple[int, int]:
    """
    Вычисляет размер bbox (ширина, высота).
    
    Args:
        bbox: Словарь с координатами bbox
        
    Returns:
        Tuple[int, int]: Размер (width, height)
    """
    width = bbox['x2'] - bbox['x1']
    height = bbox['y2'] - bbox['y1']
    return (width, height)


def rotate_bbox(bbox: Dict, angle: float, center: Optional[Tuple[float, float]] = None) -> Dict:
    """
    Поворачивает bbox на заданный угол вокруг центра.
    
    Args:
        bbox: Словарь с координатами bbox
        angle: Угол поворота в градусах
        center: Центр поворота (если None, используется центр bbox)
        
    Returns:
        Dict: Повернутый bbox
    """
    if center is None:
        center = get_bbox_center(bbox)
    
    cx, cy = center
    angle_rad = np.radians(angle)
    cos_a = np.cos(angle_rad)
    sin_a = np.sin(angle_rad)
    
    # Углы bbox
    corners = [
        (bbox['x1'], bbox['y1']),
        (bbox['x2'], bbox['y1']),
        (bbox['x2'], bbox['y2']),
        (bbox['x1'], bbox['y2'])
    ]
    
    # Поворачиваем углы
    rotated_corners = []
    for x, y in corners:
        dx = x - cx
        dy = y - cy
        rx = dx * cos_a - dy * sin_a + cx
        ry = dx * sin_a + dy * cos_a + cy
        rotated_corners.append((rx, ry))
    
    # Находим новый ограничивающий прямоугольник
    xs = [p[0] for p in rotated_corners]
    ys = [p[1] for p in rotated_corners]
    
    return {
        'x1': int(min(xs)),
        'y1': int(min(ys)),
        'x2': int(max(xs)),
        'y2': int(max(ys)),
        'angle': bbox.get('angle', 0) + angle,
        'bbox_id': bbox.get('bbox_id', '')
    }
