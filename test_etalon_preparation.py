"""
Тест для проверки загрузки изображений и сохранения кропов компонентов по разметке.
Использует реальные данные: bboxes из markup_info/bboxes.json и изображения из data/plate_3/etalon_2/images
"""
import cv2
import numpy as np
import json
from pathlib import Path
from example_pipeline_usage import InspectionRunner, load_etalon_images_from_folder


def test_etalon_preparation():
    """Тест загрузки изображений и создания кропов компонентов из реальных данных."""
    print("=" * 60)
    print("Тест подготовки эталонной платы")
    print("=" * 60)
    
    # Пути к данным
    images_folder = Path("data/plate_3/etalon_2/images")
    bboxes_file = Path("markup_info/bboxes.json")
    save_dir = Path("/tmp/inspection_tmp_data")
    
    # Проверяем наличие файлов и папок
    print("\n1. Проверка наличия данных...")
    if not images_folder.exists():
        print(f"   ✗ Папка с изображениями не найдена: {images_folder}")
        print(f"   Убедитесь, что папка существует и содержит изображения")
        return
    
    if not bboxes_file.exists():
        print(f"   ✗ Файл разметки не найден: {bboxes_file}")
        return
    
    print(f"   ✓ Папка с изображениями: {images_folder}")
    print(f"   ✓ Файл разметки: {bboxes_file}")
    
    # Загружаем разметку
    print("\n2. Загрузка разметки...")
    with open(bboxes_file, 'r', encoding='utf-8') as f:
        bboxes_data = json.load(f)
    
    print(f"   ✓ Загружено {len(bboxes_data)} изображений в разметке")
    total_components = sum(len(bboxes) for bboxes in bboxes_data.values())
    print(f"   ✓ Всего компонентов в разметке: {total_components}")
    for photo_key, bboxes in bboxes_data.items():
        print(f"   - {photo_key}: {len(bboxes)} компонентов")
    
    # Загружаем изображения
    print("\n3. Загрузка изображений...")
    etalon_images_dict = load_etalon_images_from_folder(str(images_folder))
    
    if not etalon_images_dict:
        print(f"   ✗ Не найдено изображений в папке {images_folder}")
        print(f"   Убедитесь, что папка содержит изображения в форматах: .png, .jpg, .jpeg, .bmp, .tiff, .tif")
        return
    
    print(f"   ✓ Загружено {len(etalon_images_dict)} изображений")
    for photo_key, image in etalon_images_dict.items():
        print(f"   ✓ {photo_key}: размер {image.shape}")
    
    # Проверяем соответствие изображений и разметки
    print("\n4. Проверка соответствия изображений и разметки...")
    missing_images = []
    for photo_key in bboxes_data.keys():
        if photo_key not in etalon_images_dict:
            missing_images.append(photo_key)
            print(f"   ⚠ Изображение {photo_key} есть в разметке, но не найдено в папке")
    
    if missing_images:
        print(f"   ⚠ Всего отсутствует изображений: {len(missing_images)}")
    else:
        print(f"   ✓ Все изображения из разметки найдены")
    
    # Создаем runner и загружаем данные
    print("\n5. Загрузка данных в InspectionRunner...")
    runner = InspectionRunner()
    runner.set_etalon_images(etalon_images_dict)
    runner.set_etalon_markup()
    
    print(f"   ✓ Изображения загружены в хранилище: {len(runner.board_storage.etalon_images)}")
    print(f"   ✓ Разметка загружена: {len(runner.board_storage.etalon_markup)} изображений")
    
    # Создаем кропы компонентов
    print("\n6. Создание кропов компонентов...")
    runner.prepare_etalon()
    
    actual_crops = len(runner.board_storage.etalon_components)
    print(f"   ✓ Создано {actual_crops} кропов компонентов")
    
    if actual_crops == 0:
        print("   ⚠ Предупреждение: не создано ни одного кропа")
        return
    
    # Сохранение кропнутых компонентов в /tmp/inspection_tmp_data
    print("\n7. Сохранение кропнутых компонентов...")
    save_dir.mkdir(parents=True, exist_ok=True)
    
    saved_count = 0
    failed_count = 0
    
    for component_id, component_data in runner.board_storage.etalon_components.items():
        crop_image = component_data['image']
        if crop_image is not None and crop_image.size > 0:
            try:
                # Формируем имя файла: используем name из bbox, если есть, иначе component_id
                bbox = component_data.get('bbox', {})
                component_name = bbox.get('name', component_id)
                photo_key = component_data.get('photo_key', '')
                
                # Создаем безопасное имя файла: photo_key_name.png
                safe_name = str(component_name).replace('/', '_').replace('\\', '_')
                safe_photo_key = str(photo_key).replace('/', '_').replace('\\', '_')
                filename = f"{safe_photo_key}_{safe_name}.png"
                save_path = save_dir / filename
                
                # Сохраняем кроп
                success = cv2.imwrite(str(save_path), crop_image)
                if success:
                    saved_count += 1
                    if saved_count <= 10:  # Показываем первые 10 для краткости
                        print(f"   ✓ Сохранен кроп: {save_path.name} ({crop_image.shape[1]}x{crop_image.shape[0]})")
                else:
                    failed_count += 1
                    print(f"   ✗ Ошибка сохранения: {save_path.name}")
            except Exception as e:
                failed_count += 1
                print(f"   ✗ Ошибка при сохранении {component_id}: {e}")
        else:
            failed_count += 1
            print(f"   ⚠ Пустой кроп для компонента {component_id}")
    
    print(f"\n   ✓ Сохранено {saved_count} кропов в {save_dir}")
    if failed_count > 0:
        print(f"   ⚠ Не удалось сохранить {failed_count} кропов")
    
    # Проверяем структуру кропов
    print("\n8. Проверка структуры кропов...")
    checked_count = 0
    for photo_key, bboxes in bboxes_data.items():
        if photo_key not in etalon_images_dict:
            continue  # Пропускаем, если изображение не загружено
        
        for idx, bbox in enumerate(bboxes):
            # Формируем component_id так же, как в prepare_etalon
            component_id = bbox.get('bbox_id', f"{photo_key}_component_{idx}")
            
            if component_id in runner.board_storage.etalon_components:
                component_data = runner.board_storage.etalon_components[component_id]
                
                # Проверяем наличие всех необходимых полей
                required_fields = ['image', 'photo_key', 'bbox']
                for field in required_fields:
                    if field not in component_data:
                        print(f"   ⚠ Поле {field} отсутствует в данных компонента {component_id}")
                
                # Проверяем, что кроп не пустой
                crop_image = component_data['image']
                if crop_image is not None and crop_image.size > 0:
                    checked_count += 1
                    if checked_count <= 5:  # Показываем первые 5 для краткости
                        h, w = crop_image.shape[:2]
                        print(f"   ✓ Компонент {component_id}: кроп {w}x{h}")
    
    print(f"   ✓ Проверено {checked_count} кропов")
    
    print("\n" + "=" * 60)
    print("✓ Тест завершен!")
    print(f"  - Загружено изображений: {len(etalon_images_dict)}")
    print(f"  - Компонентов в разметке: {total_components}")
    print(f"  - Создано кропов: {actual_crops}")
    print(f"  - Сохранено кропов: {saved_count}")
    print("=" * 60)


if __name__ == "__main__":
    test_etalon_preparation()
