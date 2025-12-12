"""
Модуль для препроцессинга изображений перед сегментацией.
"""
import cv2
import numpy as np
from typing import Tuple


class ImagePreprocessor:
    """Класс для препроцессинга изображений перед сегментацией."""
    
    def prepare_image_for_segmentation(self, image_bgr: np.ndarray) -> Tuple[np.ndarray, int, int]:
        """
        Подготавливает изображение для сегментации: конвертирует в grayscale и поворачивает при необходимости.
        
        Args:
            image_bgr: Изображение в формате BGR (numpy array)
        
        Returns:
            Tuple[gray_image, width, height]: Градационное изображение и его размеры
        """
        h, w = image_bgr.shape[:2]
        # Поворачиваем, если высота больше ширины
        if h > w:
            image_bgr = cv2.rotate(image_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
            h, w = w, h
        
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        return gray, w, h
