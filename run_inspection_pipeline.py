"""
Пример создания и запуска пайплайна оптической инспекции компонентов.

Этот скрипт демонстрирует полный цикл работы пайплайна:
1. Загрузка эталонных и контрольных изображений
2. Загрузка разметки и маппинга
3. Подготовка эталона (создание кропов компонентов)
4. Подготовка контроля (выравнивание и создание кропов)
5. Запуск инспекции компонентов
6. Вывод результатов
7. Визуализация результатов на выровненных изображениях
"""
import json
import cv2
import numpy as np
from pathlib import Path

from cnc_control.core.pipeline.pipeline_runner import InspectionRunner
from example_pipeline_usage import load_etalon_images_from_folder


def create_component_visualization_collage(
    etalon_crop,
    control_crop,
    etalon_mask,
    control_mask,
    iou,
    angle_diff,
    etalon_angle,
    control_angle,
    inspection_result,
    component_id,
    output_path
):
    """
    Создает коллаж визуализации компонента с хитмапами сегментации.
    
    Args:
        etalon_crop: Кроп эталонного компонента (numpy array, BGR)
        control_crop: Кроп контрольного компонента (numpy array, BGR)
        etalon_mask: Хитмапа сегментации эталонного компонента (numpy array)
        control_mask: Хитмапа сегментации контрольного компонента (numpy array)
        iou: Значение IoU
        angle_diff: Разница в угле поворота
        etalon_angle: Угол поворота эталонного компонента
        control_angle: Угол поворота контрольного компонента
        inspection_result: Результат инспекции ('ok', 'shifted', 'missing')
        component_id: Идентификатор компонента
        output_path: Путь для сохранения коллажа
    
    Returns:
        bool: True если успешно, False если ошибка
    """
    try:
        # Получаем размеры кропов
        etalon_h, etalon_w = etalon_crop.shape[:2]
        control_h, control_w = control_crop.shape[:2]
        
        # Определяем максимальную высоту для выравнивания
        max_height = max(etalon_h, control_h, etalon_mask.shape[0], control_mask.shape[0])
        
        # Изменяем размеры до одинаковой высоты (сохраняя пропорции)
        if etalon_h != max_height:
            scale = max_height / etalon_h
            new_w = int(etalon_w * scale)
            etalon_crop = cv2.resize(etalon_crop, (new_w, max_height), interpolation=cv2.INTER_LINEAR)
            etalon_h, etalon_w = etalon_crop.shape[:2]
        
        if control_h != max_height:
            scale = max_height / control_h
            new_w = int(control_w * scale)
            control_crop = cv2.resize(control_crop, (new_w, max_height), interpolation=cv2.INTER_LINEAR)
            control_h, control_w = control_crop.shape[:2]
        
        # Преобразуем маски в цветные изображения (heatmap)
        # Нормализуем маски к диапазону 0-255
        etalon_mask_norm = (etalon_mask * 255).astype(np.uint8) if etalon_mask.max() <= 1.0 else etalon_mask.astype(np.uint8)
        control_mask_norm = (control_mask * 255).astype(np.uint8) if control_mask.max() <= 1.0 else control_mask.astype(np.uint8)
        
        # Применяем цветовую карту для визуализации (JET colormap)
        etalon_heatmap = cv2.applyColorMap(etalon_mask_norm, cv2.COLORMAP_JET)
        control_heatmap = cv2.applyColorMap(control_mask_norm, cv2.COLORMAP_JET)
        
        # Изменяем размеры хитмап до нужной высоты
        if etalon_heatmap.shape[0] != max_height:
            scale = max_height / etalon_heatmap.shape[0]
            new_w = int(etalon_heatmap.shape[1] * scale)
            etalon_heatmap = cv2.resize(etalon_heatmap, (new_w, max_height), interpolation=cv2.INTER_LINEAR)
        
        if control_heatmap.shape[0] != max_height:
            scale = max_height / control_heatmap.shape[0]
            new_w = int(control_heatmap.shape[1] * scale)
            control_heatmap = cv2.resize(control_heatmap, (new_w, max_height), interpolation=cv2.INTER_LINEAR)
        
        # Определяем ширину каждого изображения (берем максимальную)
        img_width = max(etalon_w, control_w, etalon_heatmap.shape[1], control_heatmap.shape[1])
        
        # Изменяем размеры всех изображений до одинаковой ширины
        if etalon_crop.shape[1] != img_width:
            etalon_crop = cv2.resize(etalon_crop, (img_width, max_height), interpolation=cv2.INTER_LINEAR)
        if control_crop.shape[1] != img_width:
            control_crop = cv2.resize(control_crop, (img_width, max_height), interpolation=cv2.INTER_LINEAR)
        if etalon_heatmap.shape[1] != img_width:
            etalon_heatmap = cv2.resize(etalon_heatmap, (img_width, max_height), interpolation=cv2.INTER_LINEAR)
        if control_heatmap.shape[1] != img_width:
            control_heatmap = cv2.resize(control_heatmap, (img_width, max_height), interpolation=cv2.INTER_LINEAR)
        
        # Создаем коллаж: 4 изображения в ряд
        padding = 10
        text_height = 60
        collage_height = max_height + text_height + padding * 2
        collage_width = img_width * 4 + padding * 5  # 4 изображения + отступы
        
        # Создаем белый фон
        collage = np.ones((collage_height, collage_width, 3), dtype=np.uint8) * 255
        
        # Размещаем изображения
        y_offset = text_height + padding
        x_offset = padding
        
        # 1. Эталонный компонент
        collage[y_offset:y_offset + max_height, x_offset:x_offset + img_width] = etalon_crop
        x_offset += img_width + padding
        
        # 2. Хитмапа эталонного компонента
        collage[y_offset:y_offset + max_height, x_offset:x_offset + img_width] = etalon_heatmap
        x_offset += img_width + padding
        
        # 3. Контрольный компонент
        collage[y_offset:y_offset + max_height, x_offset:x_offset + img_width] = control_crop
        x_offset += img_width + padding
        
        # 4. Хитмапа контрольного компонента
        collage[y_offset:y_offset + max_height, x_offset:x_offset + img_width] = control_heatmap
        
        # Добавляем подписи под изображениями
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        color = (0, 0, 0)
        thickness = 2
        
        labels = ["Etalon", "Etalon Heatmap", "Control", "Control Heatmap"]
        x_offset = padding
        for label in labels:
            text_size = cv2.getTextSize(label, font, font_scale, thickness)[0]
            text_x = x_offset + (img_width - text_size[0]) // 2
            text_y = text_height - 10
            cv2.putText(collage, label, (text_x, text_y), font, font_scale, color, thickness)
            x_offset += img_width + padding
        
        # Добавляем информацию о IoU, углах поворота и результате инспекции сверху
        info_text = f"Result: {inspection_result.upper()}" if inspection_result else "Result: N/A"
        info_text += f"  |  IoU: {iou:.3f}" if iou is not None else "  |  IoU: N/A"
        if angle_diff is not None:
            info_text += f"  |  Angle diff: {angle_diff:.2f} grad"
        else:
            info_text += "  |  Angle diff: N/A"
        
        # Добавляем информацию об углах эталонного и контрольного компонентов
        if etalon_angle is not None:
            info_text += f"  |  Etalon angle: {etalon_angle:.2f} grad"
        else:
            info_text += "  |  Etalon angle: N/A"
        
        if control_angle is not None:
            info_text += f"  |  Control angle: {control_angle:.2f} grad"
        else:
            info_text += "  |  Control angle: N/A"
        
        # Определяем цвет текста в зависимости от результата
        if inspection_result == 'missing':
            text_color = (0, 0, 255)  # Красный
        elif inspection_result == 'shifted':
            text_color = (255, 0, 0)  # Синий
        elif inspection_result == 'ok':
            text_color = (0, 255, 0)  # Зеленый
        else:
            text_color = (0, 0, 255)  # Красный по умолчанию
        
        info_font_scale = 0.7
        info_text_size = cv2.getTextSize(info_text, font, info_font_scale, thickness)[0]
        info_text_x = (collage_width - info_text_size[0]) // 2
        info_text_y = 30
        cv2.putText(collage, info_text, (info_text_x, info_text_y), font, info_font_scale, text_color, thickness)
        
        # Добавляем идентификатор компонента
        component_text = f"Component: {component_id}"
        component_text_size = cv2.getTextSize(component_text, font, 0.5, 1)[0]
        component_text_x = (collage_width - component_text_size[0]) // 2
        component_text_y = collage_height - 10
        cv2.putText(collage, component_text, (component_text_x, component_text_y), font, 0.5, (100, 100, 100), 1)
        
        # Сохраняем коллаж
        cv2.imwrite(str(output_path), collage)
        return True
        
    except Exception as e:
        print(f"Ошибка при создании коллажа компонента {component_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def visualize_inspection_results(runner, output_dir):
    """
    Визуализирует результаты инспекции на выровненных контрольных изображениях.
    
    Внешний цикл проходит по выровненным контрольным изображениям и ищет дефекты
    среди результатов инспекции. Если дефектов нет - сохраняет изображение как есть.
    Если есть дефекты - отмечает их и сохраняет изображение.
    
    Args:
        runner: Экземпляр InspectionRunner с выполненной инспекцией
        output_dir: Директория для сохранения визуализированных изображений
    
    Returns:
        int: Количество сохраненных изображений
    """
    if not runner.board_storage.aligned_control_images:
        print("   ⚠ Нет выровненных контрольных изображений")
        return 0
    
    print("\n11. Визуализация результатов инспекции...")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    saved_count = 0
    images_with_defects = 0
    images_without_defects = 0
    
    # Внешний цикл по выровненным контрольным изображениям
    for control_id, aligned_image in runner.board_storage.aligned_control_images.items():
        # Копируем изображение для рисования
        image_to_save = aligned_image.copy()
        
        # Ищем дефекты для текущего контрольного изображения
        defects_found = []
        
        if runner.board_storage.inspection_results:
            for inspection_id, result_data in runner.board_storage.inspection_results.items():
                result = result_data['result']
                control_component_id = result_data['control_component_id']
                
                # Пропускаем результаты 'ok'
                if result not in ['missing', 'shifted']:
                    continue
                
                # Находим контрольный компонент для получения bbox и проверки photo_key
                if control_component_id not in runner.board_storage.control_components:
                    continue
                
                control_component = runner.board_storage.control_components[control_component_id]
                component_control_id = control_component['photo_key']  # Идентификатор контрольного изображения
                
                # Проверяем, относится ли этот компонент к текущему изображению
                if component_control_id != control_id:
                    continue
                
                # Нашли дефект для текущего изображения
                bbox = control_component.get('bbox', {})
                defects_found.append((result, bbox))
        
        # Если есть дефекты - отмечаем их на изображении
        if defects_found:
            images_with_defects += 1
            
            for result, bbox in defects_found:
                x1 = int(bbox.get('x1', 0))
                y1 = int(bbox.get('y1', 0))
                x2 = int(bbox.get('x2', 0))
                y2 = int(bbox.get('y2', 0))
                
                # Определяем цвет в зависимости от результата
                if result == 'missing':
                    color = (0, 0, 255)  # Красный (BGR)
                    label = 'Missing'
                elif result == 'shifted':
                    color = (255, 0, 0)  # Синий (BGR)
                    label = 'Shifted'
                else:
                    continue
                
                # Рисуем прямоугольник
                thickness = 3
                cv2.rectangle(image_to_save, (x1, y1), (x2, y2), color, thickness)
                
                # Добавляем подпись
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.7
                text_thickness = 2
                
                # Размещаем текст над прямоугольником
                text_size = cv2.getTextSize(label, font, font_scale, text_thickness)[0]
                text_x = x1
                text_y = max(y1 - 10, text_size[1] + 10)
                
                # Рисуем фон для текста
                cv2.rectangle(
                    image_to_save,
                    (text_x, text_y - text_size[1] - 5),
                    (text_x + text_size[0] + 5, text_y + 5),
                    color,
                    -1
                )
                
                # Рисуем текст белым цветом
                cv2.putText(
                    image_to_save,
                    label,
                    (text_x + 2, text_y),
                    font,
                    font_scale,
                    (255, 255, 255),
                    text_thickness
                )
        else:
            images_without_defects += 1
        
        # Сохраняем изображение (с дефектами или без)
        safe_control_id = str(control_id).replace('/', '_').replace('\\', '_')
        output_path = output_dir / f"{safe_control_id}_inspection_result.png"
        
        if cv2.imwrite(str(output_path), image_to_save):
            saved_count += 1
            if defects_found:
                print(f"   ✓ Сохранено изображение с дефектами: {output_path.name} ({len(defects_found)} дефектов)")
            else:
                print(f"   ✓ Сохранено изображение без дефектов: {output_path.name}")
        else:
            print(f"   ✗ Ошибка сохранения: {output_path.name}")
    
    print(f"\n   ✓ Сохранено {saved_count} визуализированных изображений в {output_dir}")
    print(f"   ✓ Изображений с дефектами: {images_with_defects}")
    print(f"   ✓ Изображений без дефектов: {images_without_defects}")
    return saved_count


def visualize_component_inspection_results(runner, output_dir):
    """
    Создает коллажи визуализации для каждого компонента с хитмапами сегментации.
    
    Args:
        runner: Экземпляр InspectionRunner с выполненной инспекцией
        output_dir: Директория для сохранения коллажей
    
    Returns:
        int: Количество сохраненных коллажей
    """
    if not runner.board_storage.inspection_results:
        print("   ⚠ Нет результатов инспекции для визуализации компонентов")
        return 0
    
    print("\n12. Создание коллажей компонентов с хитмапами...")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    saved_count = 0
    failed_count = 0
    
    for inspection_id, result_data in runner.board_storage.inspection_results.items():
        etalon_component_id = result_data['etalon_component_id']
        control_component_id = result_data['control_component_id']
        inspection_result = result_data['result']
        metrics = result_data['metrics']
        
        # Проверяем наличие компонентов
        if etalon_component_id not in runner.board_storage.etalon_components:
            continue
        
        if control_component_id not in runner.board_storage.control_components:
            continue
        
        # Получаем кропы компонентов
        etalon_component = runner.board_storage.etalon_components[etalon_component_id]
        control_component = runner.board_storage.control_components[control_component_id]
        
        etalon_crop = etalon_component['image']
        control_crop = control_component['image']
        
        # Извлекаем метрики и хитмапы из metrics
        # Формат metrics: (iou, center_distance, angle_diff, details)
        # где details содержит маски и углы
        if len(metrics) >= 4:
            iou = metrics[0]
            angle_diff = metrics[2]
            details = metrics[3]
            
            # Получаем маски из details
            etalon_mask = details.get('etalon_mask')
            control_mask = details.get('control_mask')
            
            # Получаем углы из details
            etalon_angle = details.get('etalon_angle')
            control_angle = details.get('control_angle')
            
            if etalon_mask is None or control_mask is None:
                print(f"   ⚠ Маски не найдены для {inspection_id}")
                failed_count += 1
                continue
        else:
            print(f"   ⚠ Неожиданный формат метрик для {inspection_id}")
            failed_count += 1
            continue
        
        # Создаем безопасное имя файла
        safe_component_id = str(control_component_id).replace('/', '_').replace('\\', '_')
        output_path = output_dir / f"{safe_component_id}_component_visualization.png"
        
        # Создаем коллаж
        if create_component_visualization_collage(
            etalon_crop,
            control_crop,
            etalon_mask,
            control_mask,
            iou,
            angle_diff,
            etalon_angle,
            control_angle,
            inspection_result,
            control_component_id,
            output_path
        ):
            saved_count += 1
            if saved_count <= 10:  # Показываем первые 10 для краткости
                print(f"   ✓ Создан коллаж компонента: {output_path.name}")
        else:
            failed_count += 1
    
    print(f"   ✓ Сохранено {saved_count} коллажей компонентов в {output_dir}")
    if failed_count > 0:
        print(f"   ⚠ Не удалось создать {failed_count} коллажей")
    
    return saved_count


def main():
    """Основная функция запуска пайплайна инспекции."""
    print("=" * 60)
    print("Запуск пайплайна оптической инспекции компонентов")
    print("=" * 60)
    
    # Пути к данным
    etalon_folder = Path("data/plate_3/etalon_2/images")
    control_folder = Path("data/plate_3/control_4/images")
    bboxes_file = Path("markup_info/bboxes.json")
    etalon_mapping_file = Path("markup_info/etalon_mapping_upd.json")
    output_dir = Path("/tmp/inspection_tmp_data")
    
    # Проверяем наличие файлов и папок
    print("\n1. Проверка наличия данных...")
    if not etalon_folder.exists():
        print(f"   ✗ Папка с эталонными изображениями не найдена: {etalon_folder}")
        return
    
    if not control_folder.exists():
        print(f"   ✗ Папка с контрольными изображениями не найдена: {control_folder}")
        return
    
    if not bboxes_file.exists():
        print(f"   ✗ Файл разметки не найден: {bboxes_file}")
        return
    
    if not etalon_mapping_file.exists():
        print(f"   ✗ Файл маппинга не найден: {etalon_mapping_file}")
        return
    
    print(f"   ✓ Папка с эталонными изображениями: {etalon_folder}")
    print(f"   ✓ Папка с контрольными изображениями: {control_folder}")
    print(f"   ✓ Файл разметки: {bboxes_file}")
    print(f"   ✓ Файл маппинга: {etalon_mapping_file}")
    
    # Создаем runner
    print("\n2. Инициализация InspectionRunner...")
    runner = InspectionRunner()
    print("   ✓ InspectionRunner создан")
    print(f"   ✓ Доступные алгоритмы инспекции: {list(runner.inspection_algorithms.keys())}")
    
    # Загружаем эталонные изображения
    print("\n3. Загрузка эталонных изображений...")
    etalon_images_dict = load_etalon_images_from_folder(str(etalon_folder))
    
    if not etalon_images_dict:
        print(f"   ✗ Не найдено эталонных изображений в папке {etalon_folder}")
        return
    
    print(f"   ✓ Загружено {len(etalon_images_dict)} эталонных изображений")
    runner.set_etalon_images(etalon_images_dict)
    
    # Загружаем контрольные изображения
    print("\n4. Загрузка контрольных изображений...")
    control_images_dict = load_etalon_images_from_folder(str(control_folder))
    
    if not control_images_dict:
        print(f"   ✗ Не найдено контрольных изображений в папке {control_folder}")
        return
    
    print(f"   ✓ Загружено {len(control_images_dict)} контрольных изображений")
    runner.set_control_images(control_images_dict)
    
    # Загружаем разметку
    print("\n5. Загрузка разметки...")
    with open(bboxes_file, 'r', encoding='utf-8') as f:
        markup = json.load(f)
    runner.set_etalon_markup(markup)
    print(f"   ✓ Загружена разметка для {len(markup)} изображений")
    
    # Загружаем маппинг
    print("\n6. Загрузка маппинга эталон-контроль...")
    runner.set_etalon_control_mapping()
    print(f"   ✓ Загружен маппинг: {len(runner.etalon_control_mapping)} записей")
    
    # Подготавливаем эталон
    print("\n7. Подготовка эталона...")
    runner.prepare_etalon()
    print(f"   ✓ Создано {len(runner.board_storage.etalon_components)} эталонных компонентов")
    
    # Подготавливаем контроль
    print("\n8. Подготовка контроля...")
    runner.prepare_control()
    print(f"   ✓ Выровнено {len(runner.board_storage.aligned_control_images)} контрольных изображений")
    print(f"   ✓ Создано {len(runner.board_storage.control_components)} контрольных компонентов")
    
    # Запускаем инспекцию
    print("\n9. Запуск инспекции компонентов...")
    runner.run_inspection()
    
    # Выводим статистику результатов
    print("\n10. Статистика результатов инспекции...")
    if runner.board_storage.inspection_results:
        total_results = len(runner.board_storage.inspection_results)
        missing_results = sum(1 for r in runner.board_storage.inspection_results.values() 
                           if r['result'] == 'missing')
        shifted_results = sum(1 for r in runner.board_storage.inspection_results.values() 
                              if r['result'] == 'shifted')
        ok_results = sum(1 for r in runner.board_storage.inspection_results.values() 
                        if r['result'] == 'ok')
        
        print(f"   ✓ Всего проверок: {total_results}")
        print(f"   ✓ Не дефект: {ok_results}")
        print(f"   ✓ Отсутствие: {missing_results}")
        print(f"   ✓ Смещение: {shifted_results}")
        
        # Показываем примеры результатов
        print("\n   Примеры результатов инспекции:")
        count = 0
        for inspection_id, result_data in runner.board_storage.inspection_results.items():
            if count >= 5:  # Показываем первые 5
                break
            print(f"     - {inspection_id}: {result_data['result']} (алгоритм: {result_data['algorithm']})")
            count += 1
    else:
        print("   ⚠ Результаты инспекции отсутствуют")
    
    # Визуализируем результаты инспекции на выровненных изображениях
    visualize_inspection_results(runner, output_dir)
    
    # Создаем коллажи компонентов с хитмапами
    visualize_component_inspection_results(runner, output_dir)
    
    print("\n" + "=" * 60)
    print("✓ Пайплайн завершен успешно!")
    print("=" * 60)
    
    # Возвращаем runner для дальнейшего использования результатов
    return runner


if __name__ == "__main__":
    runner = main()
    
    # Пример доступа к результатам после выполнения пайплайна
    if runner and runner.board_storage.inspection_results:
        print("\nДоступ к результатам инспекции:")
        print("  runner.board_storage.inspection_results - словарь всех результатов")
        print("  runner.board_storage.etalon_components - словарь эталонных компонентов")
        print("  runner.board_storage.control_components - словарь контрольных компонентов")
        print("  runner.board_storage.aligned_control_images - словарь выровненных контрольных изображений")
