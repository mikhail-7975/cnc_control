"""
Модуль для выравнивания изображений с использованием SIFT.
"""
import cv2
import numpy as np
from typing import Tuple


class SiftImageAligner:
    """
    Класс для выравнивания второго изображения относительно первого с использованием SIFT.
    
    Первое изображение остается неподвижным (эталон), второе изображение трансформируется
    (смещается и обрезается) для совпадения с первым.
    """
    
    def __init__(
        self,
        scale: float = 0.25,
        nfeatures: int = 0,
        contrast_threshold: float = 0.06,
        edge_threshold: float = 15,
        sigma: float = 1.6,
        match_ratio: float = 0.75,
        ransac_threshold: float = 5.0
    ):
        """
        Инициализация выравнивателя изображений.
        
        Args:
            scale: Масштаб для уменьшения изображений при поиске соответствий (для ускорения)
            nfeatures: Максимальное количество ключевых точек SIFT (0 = без ограничений)
            contrast_threshold: Порог контраста для фильтрации ключевых точек
            edge_threshold: Порог краев для фильтрации ключевых точек
            sigma: Сигма для гауссова размытия
            match_ratio: Порог для фильтрации совпадений (Lowe's ratio test)
            ransac_threshold: Порог для RANSAC при вычислении гомографии
        """
        self.scale = scale
        self.nfeatures = nfeatures
        self.contrast_threshold = contrast_threshold
        self.edge_threshold = edge_threshold
        self.sigma = sigma
        self.match_ratio = match_ratio
        self.ransac_threshold = ransac_threshold
        
        # Создаем детектор SIFT
        self.sift = cv2.SIFT_create(
            nfeatures=nfeatures,
            contrastThreshold=contrast_threshold,
            edgeThreshold=edge_threshold,
            sigma=sigma
        )
        
        # Создаем матчер для сопоставления дескрипторов
        self.matcher = cv2.FlannBasedMatcher(
            dict(algorithm=1, trees=5),
            dict(checks=50)
        )
    
    def align(
        self,
        reference_image: np.ndarray,
        image_to_align: np.ndarray
    ) -> np.ndarray:
        """
        Выравнивает второе изображение относительно первого.
        
        Args:
            reference_image: Первое изображение (эталон), остается неподвижным
            image_to_align: Второе изображение, которое будет выровнено
        
        Returns:
            Выровненное второе изображение того же размера, что и reference_image
        """
        # Конвертируем в grayscale для работы с SIFT
        ref_gray = cv2.cvtColor(reference_image, cv2.COLOR_BGR2GRAY) if len(reference_image.shape) == 3 else reference_image
        img_gray = cv2.cvtColor(image_to_align, cv2.COLOR_BGR2GRAY) if len(image_to_align.shape) == 3 else image_to_align
        
        # Уменьшаем изображения для ускорения поиска соответствий
        ref_small = cv2.resize(ref_gray, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_AREA)
        img_small = cv2.resize(img_gray, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_AREA)
        
        # Находим ключевые точки и дескрипторы
        kp_ref, des_ref = self.sift.detectAndCompute(ref_small, None)
        kp_img, des_img = self.sift.detectAndCompute(img_small, None)
        
        if des_ref is None or des_img is None or len(des_ref) < 4 or len(des_img) < 4:
            # Если недостаточно ключевых точек, возвращаем исходное изображение
            # обрезанное до размера эталона
            h_ref, w_ref = reference_image.shape[:2]
            h_img, w_img = image_to_align.shape[:2]
            
            # Центрируем и обрезаем
            start_y = max(0, (h_img - h_ref) // 2)
            start_x = max(0, (w_img - w_ref) // 2)
            end_y = min(h_img, start_y + h_ref)
            end_x = min(w_img, start_x + w_ref)
            
            aligned = image_to_align[start_y:end_y, start_x:end_x]
            
            # Если размеры не совпадают, изменяем размер
            if aligned.shape[:2] != (h_ref, w_ref):
                aligned = cv2.resize(aligned, (w_ref, h_ref), interpolation=cv2.INTER_LINEAR)
            
            return aligned
        
        # Находим соответствия между дескрипторами
        matches = self.matcher.knnMatch(des_img, des_ref, k=2)
        
        # Фильтруем совпадения по соотношению расстояний (Lowe's ratio test)
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < self.match_ratio * n.distance:
                    good_matches.append(m)
        
        if len(good_matches) < 4:
            # Если недостаточно хороших совпадений, возвращаем обрезанное изображение
            h_ref, w_ref = reference_image.shape[:2]
            h_img, w_img = image_to_align.shape[:2]
            
            start_y = max(0, (h_img - h_ref) // 2)
            start_x = max(0, (w_img - w_ref) // 2)
            end_y = min(h_img, start_y + h_ref)
            end_x = min(w_img, start_x + w_ref)
            
            aligned = image_to_align[start_y:end_y, start_x:end_x]
            
            if aligned.shape[:2] != (h_ref, w_ref):
                aligned = cv2.resize(aligned, (w_ref, h_ref), interpolation=cv2.INTER_LINEAR)
            
            return aligned
        
        # Извлекаем координаты соответствующих точек
        pts_img = np.float32([kp_img[m.queryIdx].pt for m in good_matches])
        pts_ref = np.float32([kp_ref[m.trainIdx].pt for m in good_matches])
        
        # Вычисляем гомографию для уменьшенных изображений
        H_small, mask = cv2.findHomography(
            pts_img, pts_ref,
            cv2.RANSAC,
            self.ransac_threshold
        )
        
        if H_small is None:
            # Если не удалось вычислить гомографию, возвращаем обрезанное изображение
            h_ref, w_ref = reference_image.shape[:2]
            h_img, w_img = image_to_align.shape[:2]
            
            start_y = max(0, (h_img - h_ref) // 2)
            start_x = max(0, (w_img - w_ref) // 2)
            end_y = min(h_img, start_y + h_ref)
            end_x = min(w_img, start_x + w_ref)
            
            aligned = image_to_align[start_y:end_y, start_x:end_x]
            
            if aligned.shape[:2] != (h_ref, w_ref):
                aligned = cv2.resize(aligned, (w_ref, h_ref), interpolation=cv2.INTER_LINEAR)
            
            return aligned
        
        # Масштабируем гомографию для исходных размеров изображений
        S = np.array([
            [self.scale, 0, 0],
            [0, self.scale, 0],
            [0, 0, 1]
        ], dtype=np.float64)
        
        S_inv = np.linalg.inv(S)
        H_full = S_inv @ H_small @ S
        
        # Получаем размеры эталонного изображения
        h_ref, w_ref = reference_image.shape[:2]
        
        # Применяем трансформацию ко второму изображению
        aligned = cv2.warpPerspective(
            image_to_align,
            H_full,
            (w_ref, h_ref),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0)
        )
        
        return aligned
    
    def align_with_crop(
        self,
        reference_image: np.ndarray,
        image_to_align: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Выравнивает второе изображение относительно первого с возвратом обрезанной области.
        
        Args:
            reference_image: Первое изображение (эталон), остается неподвижным
            image_to_align: Второе изображение, которое будет выровнено
        
        Returns:
            Tuple[aligned_image, crop_region]:
                - aligned_image: Выровненное второе изображение
                - crop_region: Область обрезки в виде (x, y, width, height)
        """
        aligned = self.align(reference_image, image_to_align)
        h_ref, w_ref = reference_image.shape[:2]
        crop_region = (0, 0, w_ref, h_ref)
        return aligned, crop_region
