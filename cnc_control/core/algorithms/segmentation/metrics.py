"""
Модуль для вычисления метрик качества сегментации.
"""
import cv2
import numpy as np


def calculate_iou(mask1: np.ndarray, mask2: np.ndarray) -> float:
    """
    Вычисляет Intersection over Union (IoU) между двумя масками.
    
    Args:
        mask1: Первая маска (бинарная или булева)
        mask2: Вторая маска (бинарная или булева)
    
    Returns:
        float: Значение IoU от 0 до 1 (1.0 если обе маски пустые)
    """
    mask1 = mask1.astype(bool)
    mask2 = mask2.astype(bool)
    
    intersection = np.logical_and(mask1, mask2).sum()
    union = np.logical_or(mask1, mask2).sum()
    
    if union == 0:
        return 1.0
    
    return intersection / union


def get_bottom_edge_angle(contour: np.ndarray) -> float:
    """
    Вычисляет угол нижнего края компонента относительно горизонтали.
    
    Args:
        contour: Контур компонента
    
    Returns:
        float: Угол в градусах от -90 до 90
    """
    # Находим минимальный ограничивающий прямоугольник
    rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rect)
    box = np.array(box)
    
    # Сортируем точки по Y координате
    sorted_by_y = box[box[:, 1].argsort()]
    
    # Берем две нижние точки
    bottom_two = sorted_by_y[-2:]
    bottom_two = bottom_two[bottom_two[:, 0].argsort()]
    left_pt, right_pt = bottom_two
    
    # Вычисляем угол
    dy = right_pt[1] - left_pt[1]
    dx = right_pt[0] - left_pt[0]
    
    if dx == 0:
        angle = 90.0 if dy >= 0 else -90.0
    else:
        angle = np.degrees(np.arctan2(dy, dx))
    
    # Нормализуем угол в диапазон [-90, 90]
    if angle > 90:
        angle -= 180
    elif angle < -90:
        angle += 180
    
    return angle


def calculate_angle_difference(angle1: float, angle2: float) -> float:
    """
    Вычисляет абсолютную разницу между двумя углами.
    
    Args:
        angle1: Первый угол в градусах
        angle2: Второй угол в градусах
    
    Returns:
        float: Абсолютная разница углов в градусах
    """
    return abs(angle1 - angle2)
