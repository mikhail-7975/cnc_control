"""
Модуль для проверки соответствия компонентов путём сегментации и сравнения метриками.
"""
import cv2
import numpy as np
from typing import Tuple, Optional

from cnc_control.core.algorithms.segmentation import (
    ComponentSegmenter,
    ImagePreprocessor,
    MaskPostprocessor,
    calculate_iou,
    calculate_angle_difference
)


class SegmentationInspectionAlgorithm:
    """
    Класс-алгоритм для проверки соответствия компонентов путём сегментации
    и сравнения их хитмапов метриками IoU, расстояние между центрами масс,
    разница в угле поворота прямоугольника минимальной площади.
    """
    
    def __init__(
        self,
        model_path: str,
        device: str = 'cuda',
    ):
        # Инициализация модели сегментации
        self.segmenter = ComponentSegmenter(
            model_path=model_path,
            device=device,
        )
        
        # Инициализация препроцессора
        self.preprocessor = ImagePreprocessor()
        
        # Инициализация постпроцессора
        self.postprocessor = MaskPostprocessor(
            threshold=0.5,
            min_contour_area=100
        )
    
    def __call__(
        self,
        etalon_image: np.ndarray,
        control_image: np.ndarray
    ) -> Tuple[float, Optional[float], Optional[float], dict]:
        """
        Выполняет проверку соответствия компонентов.
        
        Args:
            etalon_image: Эталонное изображение компонента (BGR формат)
            control_image: Контрольное изображение компонента (BGR формат)
        
        Returns:
            Tuple[iou, center_distance, angle_diff, details]:
                - iou: Значение IoU между масками (0-1)
                - center_distance: Расстояние между центрами масс в пикселях
                - angle_diff: Разница в угле поворота прямоугольника минимальной площади в градусах
                - details: Словарь с дополнительной информацией:
                    - etalon_mask: Маска эталонного компонента
                    - control_mask: Маска контрольного компонента
                    - etalon_center: Центр масс эталонного компонента (x, y)
                    - control_center: Центр масс контрольного компонента (x, y)
                    - etalon_angle: Угол поворота эталонного компонента в градусах
                    - control_angle: Угол поворота контрольного компонента в градусах
        """
        # Препроцессинг изображений
        etalon_gray, etalon_w, etalon_h = self.preprocessor.prepare_image_for_segmentation(etalon_image)
        control_gray, control_w, control_h = self.preprocessor.prepare_image_for_segmentation(control_image)
        
        # Сегментация
        etalon_mask_raw = self.segmenter.predict_mask(etalon_gray, (etalon_w, etalon_h))
        control_mask_raw = self.segmenter.predict_mask(control_gray, (control_w, control_h))
        
        # Постпроцессинг масок
        etalon_mask, etalon_contours = self.postprocessor.process_mask(etalon_mask_raw, return_largest_contour=True)
        control_mask, control_contours = self.postprocessor.process_mask(control_mask_raw, return_largest_contour=True)
        
        # Приводим маски к одному размеру для корректного сравнения
        # Используем максимальные размеры
        max_h = max(etalon_mask.shape[0], control_mask.shape[0])
        max_w = max(etalon_mask.shape[1], control_mask.shape[1])
        
        # Создаем маски одинакового размера
        etalon_mask_padded = np.zeros((max_h, max_w), dtype=etalon_mask.dtype)
        control_mask_padded = np.zeros((max_h, max_w), dtype=control_mask.dtype)
        
        etalon_mask_padded[:etalon_mask.shape[0], :etalon_mask.shape[1]] = etalon_mask
        control_mask_padded[:control_mask.shape[0], :control_mask.shape[1]] = control_mask
        
        # Вычисление метрик
        iou = self._calculate_iou(etalon_mask_padded, control_mask_padded)
        
        # Вычисление центров масс
        etalon_center = self._calculate_center_of_mass(etalon_mask)
        control_center = self._calculate_center_of_mass(control_mask)
        
        # Расстояние между центрами масс
        center_distance = self._calculate_distance(etalon_center, control_center)
        
        # Вычисление углов поворота прямоугольников минимальной площади
        etalon_angle = self._calculate_min_area_rect_angle(etalon_contours)
        control_angle = self._calculate_min_area_rect_angle(control_contours)
        
        # Разница в углах
        angle_diff = calculate_angle_difference(etalon_angle, control_angle) if etalon_angle is not None and control_angle is not None else None
        
        # Формирование детальной информации
        details = {
            'etalon_mask': etalon_mask,
            'control_mask': control_mask,
            'etalon_center': etalon_center,
            'control_center': control_center,
            'etalon_angle': etalon_angle,
            'control_angle': control_angle
        }
        
        result = "ok"
        
        try:
            iou_missing_check = iou < 0.5
            shifted_check = iou > 0.5 and iou < 0.65
            if control_angle:
                control_angle_check = control_angle < 5
            else:
                control_angle_check = False
        except:
            iou_missing_check = True

        if iou_missing_check:
            result = "missing"
        elif control_angle_check or shifted_check:
            result = "shifted"
        
        return result, (iou, center_distance, angle_diff, details)
    
    def _calculate_iou(self, mask1: np.ndarray, mask2: np.ndarray) -> float:
        """
        Вычисляет IoU между двумя масками.
        
        Args:
            mask1: Первая маска
            mask2: Вторая маска
        
        Returns:
            float: Значение IoU от 0 до 1
        """
        return calculate_iou(mask1, mask2)
    
    def _calculate_center_of_mass(self, mask: np.ndarray) -> Optional[Tuple[float, float]]:
        """
        Вычисляет центр масс маски.
        
        Args:
            mask: Бинарная маска
        
        Returns:
            Optional[Tuple[float, float]]: Координаты центра масс (x, y) или None, если маска пустая
        """
        # Вычисляем моменты
        moments = cv2.moments(mask)
        
        if moments['m00'] == 0:
            return None
        
        # Центр масс
        cx = moments['m10'] / moments['m00']
        cy = moments['m01'] / moments['m00']
        
        return (cx, cy)
    
    def _calculate_distance(
        self,
        point1: Optional[Tuple[float, float]],
        point2: Optional[Tuple[float, float]]
    ) -> Optional[float]:
        """
        Вычисляет евклидово расстояние между двумя точками.
        
        Args:
            point1: Первая точка (x, y) или None
            point2: Вторая точка (x, y) или None
        
        Returns:
            Optional[float]: Расстояние в пикселях или None, если одна из точек отсутствует
        """
        if point1 is None or point2 is None:
            return None
        
        dx = point2[0] - point1[0]
        dy = point2[1] - point1[1]
        
        return np.sqrt(dx * dx + dy * dy)
    
    def _calculate_min_area_rect_angle(self, contours: list) -> Optional[float]:
        """
        Вычисляет угол поворота прямоугольника минимальной площади для наибольшего контура.
        
        Args:
            contours: Список контуров
        
        Returns:
            Optional[float]: Угол поворота в градусах или None, если контуров нет
        """
        if not contours:
            return None
        
        # Берем наибольший контур
        largest_contour = self.postprocessor.get_largest_contour(contours)
        if largest_contour is None:
            return None
        
        # Находим минимальный ограничивающий прямоугольник
        rect = cv2.minAreaRect(largest_contour)
        angle = rect[2]  # Угол поворота прямоугольника
        
        # OpenCV возвращает угол в диапазоне [-90, 0], нормализуем в [-90, 90]
        if angle < -45:
            angle += 90
        elif angle > 45:
            angle -= 90
        
        return angle
