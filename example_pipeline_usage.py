import json
import cv2
import numpy as np
from pathlib import Path

from cnc_control.core.pipeline.pipeline_runner import InspectionRunner

def load_etalon_images_from_folder(folder_path: str) -> dict:
    """
    Загружает эталонные изображения из папки с помощью OpenCV.
    
    Args:
        folder_path: Путь к папке с изображениями
    
    Returns:
        Словарь {img_id: image}, где img_id - имя файла без расширения,
        image - numpy array (BGR формат OpenCV)
    """
    images_dict = {}
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"Ошибка: папка {folder_path} не существует")
        return images_dict
    
    # Поддерживаемые форматы изображений
    image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif'}
    
    for image_file in folder.iterdir():
        if image_file.suffix.lower() in image_extensions:
            # Загружаем изображение через OpenCV
            image = cv2.imread(str(image_file))
            
            if image is not None:
                # Используем имя файла без расширения как img_id
                img_id = image_file.stem
                images_dict[img_id] = image
                print(f"Загружено изображение: {image_file.name} (размер: {image.shape})")
            else:
                print(f"Предупреждение: не удалось загрузить {image_file.name}")
    
    return images_dict


if __name__ == "__main__":
    print("Пример использования пайплайна оптической инспекции")
    
    # Создаем runner для подготовки эталона
    runner = InspectionRunner()
    
    # Загружаем эталонные изображения через OpenCV
    etalon_folder = "data/plate_3/etalon_2/images"  # Путь к папке с эталонными изображениями
    etalon_images_dict = load_etalon_images_from_folder(etalon_folder)
    
    if not etalon_images_dict:
        print(f"Ошибка: не найдено изображений в папке {etalon_folder}")
        print("Убедитесь, что папка существует и содержит изображения")
    else:
        print(f"Загружено {len(etalon_images_dict)} эталонных изображений")
        
        # Загружаем изображения в хранилище
        runner.set_etalon_images(etalon_images_dict)
        
        # Загружаем разметку
        with open("markup_info/bboxes.json") as f:
            markup = json.load(f)
        runner.set_etalon_markup(markup)
        
        # Подготавливаем эталон (создаем кропы компонентов)
        print("\nПодготовка эталонной платы...")
        runner.prepare_etalon()
        
        print(f"\nПодготовка завершена:")
        print(f"  - Загружено изображений: {len(runner.board_storage.etalon_images)}")
        print(f"  - Создано кропов компонентов: {len(runner.board_storage.etalon_components)}")
    
