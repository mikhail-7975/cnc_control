"""
Утилиты для работы с изображениями и создания коллажей.
"""
import cv2
import numpy as np
import matplotlib.pyplot as plt


def create_component_collage(etalon_image, control_image, bboxes, col, row, data_folder, photo_key):
    """
    Создать коллаж с кропами компонентов из эталонного и контрольного изображений.
    
    Args:
        etalon_image: Эталонное изображение (numpy array, BGR)
        control_image: Контрольное изображение (numpy array, BGR)
        bboxes: Список словарей с bboxes компонентов
        col: Столбец контрольного изображения
        row: Строка контрольного изображения
        data_folder: Путь к папке для сохранения
        photo_key: Ключ для логирования (например, "photo_0_0")
    
    Returns:
        int: 1 если успешно, 0 если ошибка
    """
    try:
        num_components = len(bboxes)
        if num_components == 0:
            return 0
        
        # Определяем размер сетки для коллажа
        cols_per_row = min(4, num_components)  # Максимум 4 компонента в ряд
        rows_count = (num_components + cols_per_row - 1) // cols_per_row
        
        # Вычисляем размер каждого кропа (берем максимальный размер из всех bboxes)
        max_crop_width = 0
        max_crop_height = 0
        for bbox in bboxes:
            x1, y1, x2, y2 = int(bbox['x1']), int(bbox['y1']), int(bbox['x2']), int(bbox['y2'])
            crop_width = abs(x2 - x1)
            crop_height = abs(y2 - y1)
            max_crop_width = max(max_crop_width, crop_width)
            max_crop_height = max(max_crop_height, crop_height)
        
        # Добавляем отступы
        padding = 20
        crop_size = max(max_crop_width, max_crop_height) + padding * 2
        
        # Создаем фигуру matplotlib
        total_cols = cols_per_row * 2  # *2 потому что эталон + контроль
        fig_width = total_cols * (crop_size + padding) / 100
        fig_height = rows_count * (crop_size + padding) / 100
        
        # Создаем subplots с правильной обработкой одномерных массивов
        if rows_count == 1 and total_cols == 1:
            fig, ax = plt.subplots(figsize=(fig_width, fig_height))
            axes = np.array([[ax]])
        elif rows_count == 1:
            fig, axes = plt.subplots(1, total_cols, figsize=(fig_width, fig_height))
            # Преобразуем в двумерный массив, если нужно
            if not isinstance(axes, np.ndarray):
                axes = np.array([axes])
            elif axes.ndim == 1:
                axes = axes.reshape(1, -1)
        elif total_cols == 1:
            fig, axes = plt.subplots(rows_count, 1, figsize=(fig_width, fig_height))
            # Преобразуем в двумерный массив, если нужно
            if not isinstance(axes, np.ndarray):
                axes = np.array([[axes]])
            elif axes.ndim == 1:
                axes = axes.reshape(-1, 1)
        else:
            fig, axes = plt.subplots(rows_count, total_cols, figsize=(fig_width, fig_height))
            # Убеждаемся, что axes - двумерный массив
            if axes.ndim == 1:
                axes = axes.reshape(rows_count, total_cols)
        
        # Обрабатываем каждый компонент
        for idx, bbox in enumerate(bboxes):
            x1, y1, x2, y2 = int(bbox['x1']), int(bbox['y1']), int(bbox['x2']), int(bbox['y2'])
            component_name = bbox.get('name', f'Component_{idx+1}')
            angle = bbox.get('angle', 0.0)
            
            # Определяем позицию в сетке
            row_idx = idx // cols_per_row
            col_idx = (idx % cols_per_row) * 2  # *2 потому что эталон + контроль
            
            # Проверяем границы изображения
            etalon_h, etalon_w = etalon_image.shape[:2]
            control_h, control_w = control_image.shape[:2]
            
            # Ограничиваем координаты границами изображения
            x1_safe = max(0, min(x1, etalon_w, control_w))
            y1_safe = max(0, min(y1, etalon_h, control_h))
            x2_safe = max(x1_safe + 1, min(x2, etalon_w, control_w))
            y2_safe = max(y1_safe + 1, min(y2, etalon_h, control_h))
            
            # Делаем кроп из эталонного изображения
            etalon_crop = etalon_image[y1_safe:y2_safe, x1_safe:x2_safe].copy()
            
            # Делаем кроп из контрольного изображения
            control_crop = control_image[y1_safe:y2_safe, x1_safe:x2_safe].copy()
            
            # Проверяем, что кропы не пустые
            if etalon_crop.size == 0 or control_crop.size == 0:
                print(f"Предупреждение: пустой кроп для компонента {component_name} в {photo_key}")
                continue
            
            # Если нужно, применяем поворот
            if abs(angle) > 0.1:
                center = (etalon_crop.shape[1] // 2, etalon_crop.shape[0] // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                etalon_crop = cv2.warpAffine(etalon_crop, M, (etalon_crop.shape[1], etalon_crop.shape[0]))
                control_crop = cv2.warpAffine(control_crop, M, (control_crop.shape[1], control_crop.shape[0]))
            
            # Конвертируем BGR в RGB для matplotlib
            etalon_crop_rgb = cv2.cvtColor(etalon_crop, cv2.COLOR_BGR2RGB)
            control_crop_rgb = cv2.cvtColor(control_crop, cv2.COLOR_BGR2RGB)
            
            # Отображаем эталонный кроп
            # Безопасный доступ к axes
            if isinstance(axes, np.ndarray) and axes.ndim == 2:
                ax_etalon = axes[row_idx, col_idx]
                ax_control = axes[row_idx, col_idx + 1]
            else:
                # Fallback для одномерных массивов
                ax_etalon = axes[col_idx] if rows_count == 1 else axes[row_idx]
                ax_control = axes[col_idx + 1] if rows_count == 1 else axes[row_idx]
            
            ax_etalon.imshow(etalon_crop_rgb)
            ax_etalon.set_title(f'Etalon: {component_name}', fontsize=8)
            ax_etalon.axis('off')
            
            # Отображаем контрольный кроп
            ax_control.imshow(control_crop_rgb)
            ax_control.set_title(f'Control: {component_name}', fontsize=8)
            ax_control.axis('off')
        
        # Скрываем пустые оси
        for idx in range(num_components, rows_count * cols_per_row):
            row_idx = idx // cols_per_row
            col_idx = (idx % cols_per_row) * 2
            if isinstance(axes, np.ndarray) and axes.ndim == 2:
                if row_idx < axes.shape[0]:
                    if col_idx < axes.shape[1]:
                        axes[row_idx, col_idx].axis('off')
                    if col_idx + 1 < axes.shape[1]:
                        axes[row_idx, col_idx + 1].axis('off')
            else:
                # Для одномерных массивов
                if rows_count == 1:
                    if col_idx < len(axes):
                        axes[col_idx].axis('off')
                    if col_idx + 1 < len(axes):
                        axes[col_idx + 1].axis('off')
                elif total_cols == 1:
                    if row_idx < len(axes):
                        axes[row_idx].axis('off')
        
        plt.tight_layout()
        
        # Сохраняем коллаж
        new_filename = f"tmp_photo_{col}_{row}.png"
        new_file_path = data_folder / new_filename
        
        plt.savefig(str(new_file_path), dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        print(f"Сохранено: {new_filename}")
        return 1
        
    except Exception as e:
        print(f"Ошибка при создании коллажа для ({col}, {row}): {str(e)}")
        import traceback
        traceback.print_exc()
        return 0
