import cv2
import numpy as np

def crop_by_bbox(image: np.ndarray, bbox: dict) -> np.ndarray:
    """
    Извлекает кроп компонента из изображения по bbox.
    Если в bbox указан угол, сначала поворачивает всё изображение относительно центра bbox,
    затем делает кроп из повернутого изображения.
    
    Args:
        image: Изображение (numpy array, BGR)
        bbox: Словарь с координатами bbox (x1, y1, x2, y2, angle)
    
    Returns:
        Кроп изображения или None если кроп пустой
    """
    try:
        x1, y1, x2, y2 = int(bbox['x1']), int(bbox['y1']), int(bbox['x2']), int(bbox['y2'])
        angle = bbox.get('angle', 0.0)
        
        # Проверяем границы изображения
        h, w = image.shape[:2]
        
        # Ограничиваем координаты границами изображения
        x1_safe = max(0, min(x1, w))
        y1_safe = max(0, min(y1, h))
        x2_safe = max(x1_safe + 1, min(x2, w))
        y2_safe = max(y1_safe + 1, min(y2, h))
        
        # Если есть угол, сначала поворачиваем всё изображение относительно центра bbox
        if abs(angle) > 0.1:
            # Вычисляем центр bbox
            bbox_center_x = (x1_safe + x2_safe) / 2.0
            bbox_center_y = (y1_safe + y2_safe) / 2.0
            bbox_center = (bbox_center_x, bbox_center_y)
            
            # Вычисляем размеры bbox
            bbox_width = x2_safe - x1_safe
            bbox_height = y2_safe - y1_safe
            
            # Вычисляем размеры повернутого изображения
            # Поворачиваем углы изображения, чтобы найти новые границы
            corners = np.array([
                [0, 0],
                [w, 0],
                [w, h],
                [0, h]
            ], dtype=np.float32)
            
            # Создаем матрицу поворота вокруг центра bbox
            M_rotation = cv2.getRotationMatrix2D(bbox_center, angle, 1.0)
            
            # Поворачиваем углы изображения
            ones = np.ones(shape=(len(corners), 1))
            corners_ones = np.hstack([corners, ones])
            rotated_corners = M_rotation @ corners_ones.T
            rotated_corners = rotated_corners.T
            
            # Находим новые границы
            x_coords = rotated_corners[:, 0]
            y_coords = rotated_corners[:, 1]
            min_x, max_x = int(np.floor(x_coords.min())), int(np.ceil(x_coords.max()))
            min_y, max_y = int(np.floor(y_coords.min())), int(np.ceil(y_coords.max()))
            
            # Вычисляем размеры нового изображения
            new_w = max_x - min_x
            new_h = max_y - min_y
            
            # Вычисляем смещение для центрирования повернутого изображения
            offset_x = -min_x
            offset_y = -min_y
            
            # Корректируем матрицу поворота для учета смещения
            M = M_rotation.copy()
            M[0, 2] += offset_x
            M[1, 2] += offset_y
            
            # Поворачиваем изображение
            rotated_image = cv2.warpAffine(image, M, (new_w, new_h), 
                                          flags=cv2.INTER_LINEAR, 
                                          borderMode=cv2.BORDER_CONSTANT,
                                          borderValue=(0, 0, 0))
            
            # Вычисляем новые координаты центра bbox в повернутом изображении
            # Центр bbox поворачивается вместе с изображением
            # Используем матрицу поворота для вычисления новых координат центра
            center_point = np.array([bbox_center_x, bbox_center_y, 1.0])
            rotated_center = M_rotation @ center_point
            new_center_x = rotated_center[0] + offset_x
            new_center_y = rotated_center[1] + offset_y
            
            # Вычисляем новые координаты bbox относительно повернутого центра
            new_x1 = int(new_center_x - bbox_width / 2.0)
            new_y1 = int(new_center_y - bbox_height / 2.0)
            new_x2 = int(new_center_x + bbox_width / 2.0)
            new_y2 = int(new_center_y + bbox_height / 2.0)
            
            # Ограничиваем координаты границами повернутого изображения
            new_x1_safe = max(0, min(new_x1, new_w))
            new_y1_safe = max(0, min(new_y1, new_h))
            new_x2_safe = max(new_x1_safe + 1, min(new_x2, new_w))
            new_y2_safe = max(new_y1_safe + 1, min(new_y2, new_h))
            
            # Делаем кроп из повернутого изображения
            crop = rotated_image[new_y1_safe:new_y2_safe, new_x1_safe:new_x2_safe].copy()
        else:
            # Если угла нет, просто делаем кроп
            crop = image[y1_safe:y2_safe, x1_safe:x2_safe].copy()
        
        # Проверяем, что кроп не пустой
        if crop.size == 0:
            return None
        
        return crop
        
    except Exception as e:
        print(f"Ошибка при извлечении кропа компонента: {str(e)}")
        import traceback
        traceback.print_exc()
        return None