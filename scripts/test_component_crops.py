"""
Тест для проверки получения кропов эталонных и контролируемых компонентов
и создания коллажей из пар компонентов.
"""
import json
import cv2
import numpy as np
from pathlib import Path

from cnc_control.core.pipeline.pipeline_runner import InspectionRunner
from example_pipeline_usage import load_etalon_images_from_folder


def create_aligned_images_collage(etalon_image, aligned_control_image, etalon_id, control_id, output_path):
    """
    Создает коллаж из эталонного и выровненного контрольного изображений.
    
    Args:
        etalon_image: Эталонное изображение (numpy array, BGR)
        aligned_control_image: Выровненное контрольное изображение (numpy array, BGR)
        etalon_id: Идентификатор эталонного изображения
        control_id: Идентификатор контрольного изображения
        output_path: Путь для сохранения коллажа
    
    Returns:
        bool: True если успешно, False если ошибка
    """
    try:
        # Получаем размеры изображений
        etalon_h, etalon_w = etalon_image.shape[:2]
        control_h, control_w = aligned_control_image.shape[:2]
        
        # Определяем максимальную высоту для выравнивания
        max_height = max(etalon_h, control_h)
        
        # Если нужно, изменяем размеры изображений до одинаковой высоты (сохраняя пропорции)
        if etalon_h != max_height:
            scale = max_height / etalon_h
            new_w = int(etalon_w * scale)
            etalon_image = cv2.resize(etalon_image, (new_w, max_height), interpolation=cv2.INTER_LINEAR)
            etalon_h, etalon_w = etalon_image.shape[:2]
        
        if control_h != max_height:
            scale = max_height / control_h
            new_w = int(control_w * scale)
            aligned_control_image = cv2.resize(aligned_control_image, (new_w, max_height), interpolation=cv2.INTER_LINEAR)
            control_h, control_w = aligned_control_image.shape[:2]
        
        # Создаем коллаж: эталон слева, контроль справа
        padding = 10
        text_height = 50
        collage_height = max_height + text_height + padding * 2
        collage_width = etalon_w + control_w + padding * 3
        
        # Создаем белый фон
        collage = np.ones((collage_height, collage_width, 3), dtype=np.uint8) * 255
        
        # Размещаем эталонное изображение
        y_offset = text_height + padding
        x_offset = padding
        collage[y_offset:y_offset + etalon_h, x_offset:x_offset + etalon_w] = etalon_image
        
        # Размещаем выровненное контрольное изображение
        x_offset = etalon_w + padding * 2
        collage[y_offset:y_offset + control_h, x_offset:x_offset + control_w] = aligned_control_image
        
        # Добавляем подписи
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        color = (0, 0, 0)
        thickness = 2
        
        # Подпись для эталона
        etalon_text = f"Etalon: {etalon_id}"
        text_size = cv2.getTextSize(etalon_text, font, font_scale, thickness)[0]
        text_x = padding + (etalon_w - text_size[0]) // 2
        text_y = 35
        cv2.putText(collage, etalon_text, (text_x, text_y), font, font_scale, color, thickness)
        
        # Подпись для контроля
        control_text = f"Control (Aligned): {control_id}"
        text_size = cv2.getTextSize(control_text, font, font_scale, thickness)[0]
        text_x = etalon_w + padding * 2 + (control_w - text_size[0]) // 2
        cv2.putText(collage, control_text, (text_x, text_y), font, font_scale, color, thickness)
        
        # Сохраняем коллаж
        cv2.imwrite(str(output_path), collage)
        return True
        
    except Exception as e:
        print(f"Ошибка при создании коллажа выровненных изображений {etalon_id}-{control_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_component_collage(etalon_crop, control_crop, component_id, output_path):
    """
    Создает коллаж из эталонного и контрольного кропов компонента.
    
    Args:
        etalon_crop: Кроп эталонного компонента (numpy array, BGR)
        control_crop: Кроп контрольного компонента (numpy array, BGR)
        component_id: Идентификатор компонента для имени файла
        output_path: Путь для сохранения коллажа
    
    Returns:
        bool: True если успешно, False если ошибка
    """
    try:
        # Получаем размеры кропов
        etalon_h, etalon_w = etalon_crop.shape[:2]
        control_h, control_w = control_crop.shape[:2]
        
        # Определяем максимальную высоту для выравнивания
        max_height = max(etalon_h, control_h)
        
        # Если нужно, изменяем размеры кропов до одинаковой высоты (сохраняя пропорции)
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
        
        # Создаем коллаж: эталон слева, контроль справа
        padding = 10
        text_height = 40
        collage_height = max_height + text_height + padding * 2
        collage_width = etalon_w + control_w + padding * 3
        
        # Создаем белый фон
        collage = np.ones((collage_height, collage_width, 3), dtype=np.uint8) * 255
        
        # Размещаем эталонный кроп
        y_offset = text_height + padding
        x_offset = padding
        collage[y_offset:y_offset + etalon_h, x_offset:x_offset + etalon_w] = etalon_crop
        
        # Размещаем контрольный кроп
        x_offset = etalon_w + padding * 2
        collage[y_offset:y_offset + control_h, x_offset:x_offset + control_w] = control_crop
        
        # Добавляем подписи
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        color = (0, 0, 0)
        thickness = 2
        
        # Подпись для эталона
        etalon_text = "Etalon"
        text_size = cv2.getTextSize(etalon_text, font, font_scale, thickness)[0]
        text_x = padding + (etalon_w - text_size[0]) // 2
        text_y = 30
        cv2.putText(collage, etalon_text, (text_x, text_y), font, font_scale, color, thickness)
        
        # Подпись для контроля
        control_text = "Control"
        text_size = cv2.getTextSize(control_text, font, font_scale, thickness)[0]
        text_x = etalon_w + padding * 2 + (control_w - text_size[0]) // 2
        cv2.putText(collage, control_text, (text_x, text_y), font, font_scale, color, thickness)
        
        # Добавляем идентификатор компонента внизу
        component_text = f"Component: {component_id}"
        text_size = cv2.getTextSize(component_text, font, 0.5, 1)[0]
        text_x = (collage_width - text_size[0]) // 2
        text_y = collage_height - 10
        cv2.putText(collage, component_text, (text_x, text_y), font, 0.5, (100, 100, 100), 1)
        
        # Сохраняем коллаж
        cv2.imwrite(str(output_path), collage)
        return True
        
    except Exception as e:
        print(f"Ошибка при создании коллажа для {component_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_component_crops():
    """Тест получения кропов и создания коллажей."""
    print("=" * 60)
    print("Тест получения кропов эталонных и контрольных компонентов")
    print("=" * 60)
    
    # Пути к данным
    etalon_folder = Path("data/plate_3/etalon_2/images")
    control_folder = Path("data/plate_3/control_4/images")  # Измените на нужный путь
    bboxes_file = Path("markup_info/bboxes.json")
    etalon_mapping_file = Path("markup_info/etalon_mapping_upd.json")
    output_dir = Path("/tmp/inspection_tmp_data")
    
    # Создаем выходную директорию
    output_dir.mkdir(parents=True, exist_ok=True)
    
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
    print(f"   ✓ Создано {len(runner.board_storage.control_components)} контрольных компонентов")
    
    # Создаем коллажи из выровненных изображений
    print("\n9. Создание коллажей из выровненных пар изображений...")
    aligned_collage_count = 0
    aligned_collage_failed = 0
    
    # Проходим по маппингу и создаем коллажи для каждой пары
    for mapping_entry in runner.etalon_control_mapping:
        etalon_id = mapping_entry[0]
        control_ids = mapping_entry[1]
        
        # Проверяем наличие эталонного изображения
        if etalon_id not in runner.board_storage.etalon_images:
            continue
        
        etalon_image = runner.board_storage.etalon_images[etalon_id]
        
        # Для каждого контрольного изображения создаем коллаж
        for control_id in control_ids:
            if control_id not in runner.board_storage.aligned_control_images:
                continue
            
            aligned_control_image = runner.board_storage.aligned_control_images[control_id]
            
            # Создаем безопасное имя файла
            safe_etalon_id = str(etalon_id).replace('/', '_').replace('\\', '_')
            safe_control_id = str(control_id).replace('/', '_').replace('\\', '_')
            output_path = output_dir / f"{safe_etalon_id}_{safe_control_id}_aligned_collage.png"
            
            # Создаем коллаж
            if create_aligned_images_collage(etalon_image, aligned_control_image, etalon_id, control_id, output_path):
                aligned_collage_count += 1
                if aligned_collage_count <= 10:  # Показываем первые 10 для краткости
                    print(f"   ✓ Создан коллаж выровненных изображений: {output_path.name}")
            else:
                aligned_collage_failed += 1
    
    print(f"\n   ✓ Сохранено {aligned_collage_count} коллажей выровненных изображений в {output_dir}")
    if aligned_collage_failed > 0:
        print(f"   ⚠ Не удалось создать {aligned_collage_failed} коллажей выровненных изображений")
    
    # Создаем коллажи из пар компонентов
    print("\n10. Создание коллажей из пар компонентов...")
    saved_count = 0
    failed_count = 0
    
    # Проходим по всем контрольным компонентам
    for control_component_id, control_data in runner.board_storage.control_components.items():
        etalon_component_id = control_data['etalon_component_id']
        
        # Проверяем наличие соответствующего эталонного компонента
        if etalon_component_id not in runner.board_storage.etalon_components:
            print(f"   ⚠ Эталонный компонент {etalon_component_id} не найден для {control_component_id}")
            failed_count += 1
            continue
        
        etalon_component = runner.board_storage.etalon_components[etalon_component_id]
        etalon_crop = etalon_component['image']
        control_crop = control_data['image']
        
        # Создаем безопасное имя файла
        safe_component_id = str(control_component_id).replace('/', '_').replace('\\', '_')
        output_path = output_dir / f"{safe_component_id}_collage.png"
        
        # Создаем коллаж
        if create_component_collage(etalon_crop, control_crop, control_component_id, output_path):
            saved_count += 1
            if saved_count <= 10:  # Показываем первые 10 для краткости
                print(f"   ✓ Создан коллаж: {output_path.name}")
        else:
            failed_count += 1
    
    print(f"\n   ✓ Сохранено {saved_count} коллажей в {output_dir}")
    if failed_count > 0:
        print(f"   ⚠ Не удалось создать {failed_count} коллажей")
    
    print("\n" + "=" * 60)
    print("✓ Тест завершен!")
    print(f"  - Эталонных компонентов: {len(runner.board_storage.etalon_components)}")
    print(f"  - Контрольных компонентов: {len(runner.board_storage.control_components)}")
    print(f"  - Создано коллажей выровненных изображений: {aligned_collage_count}")
    print(f"  - Создано коллажей компонентов: {saved_count}")
    print("=" * 60)


if __name__ == "__main__":
    test_component_crops()
