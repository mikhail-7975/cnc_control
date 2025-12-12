"""
Модуль для постпроцессинга масок после сегментации.
"""
import cv2
import numpy as np
from typing import Tuple, List


class MaskPostprocessor:
    """Класс для постпроцессинга масок сегментации."""
    
    def __init__(
        self,
        threshold: float = 0.5,
        min_contour_area: int = 100
    ):
        """
        Инициализация постпроцессора масок.
        
        Args:
            threshold: Порог для бинаризации маски
            min_contour_area: Минимальная площадь контура для фильтрации
        """
        self.threshold = threshold
        self.min_contour_area = min_contour_area
    
    def process_mask(
        self,
        mask: np.ndarray,
        return_largest_contour: bool = True
    ) -> Tuple[np.ndarray, List[np.ndarray]]:
        """
        Обрабатывает предсказанную маску: бинаризует, находит контуры, фильтрует и очищает.
        
        Args:
            mask: Предсказанная маска (нормализованная, значения от 0 до 1)
            return_largest_contour: Если True, возвращает только наибольший контур
        
        Returns:
            Tuple[cleaned_mask, contours]:
                - cleaned_mask: Очищенная бинарная маска (0 или 255)
                - contours: Список найденных контуров
        """
        # Бинаризация маски
        _, binary_mask = cv2.threshold(
            mask,
            self.threshold,
            1,
            cv2.THRESH_BINARY
        )
        binary_mask = (binary_mask * 255).astype(np.uint8)
        
        # Поиск контуров
        contours, _ = cv2.findContours(
            binary_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Фильтрация контуров по минимальной площади
        filtered_contours = [
            c for c in contours
            if cv2.contourArea(c) >= self.min_contour_area
        ]
        
        if not filtered_contours:
            # Если контуров нет, возвращаем пустую маску
            cleaned = np.zeros_like(binary_mask)
            return cleaned, []
        
        # Если нужно вернуть только наибольший контур
        if return_largest_contour:
            largest = max(filtered_contours, key=cv2.contourArea)
            cleaned = np.zeros_like(binary_mask)
            cv2.drawContours(cleaned, [largest], -1, 255, thickness=cv2.FILLED)
            return cleaned, [largest]
        
        # Иначе возвращаем все контуры
        cleaned = np.zeros_like(binary_mask)
        cv2.drawContours(cleaned, filtered_contours, -1, 255, thickness=cv2.FILLED)
        return cleaned, filtered_contours
    
    def get_largest_contour(self, contours: List[np.ndarray]) -> np.ndarray:
        """
        Возвращает наибольший контур из списка.
        
        Args:
            contours: Список контуров
        
        Returns:
            np.ndarray: Наибольший контур или None, если список пуст
        """
        if not contours:
            return None
        return max(contours, key=cv2.contourArea)
