from cnc_control.core.pipeline.board_storage import BoardStorage
from cnc_control.core.pipeline.utils import crop_by_bbox

class InspectionRunner():
    def __init__(self) -> None:
        self.board_storage = BoardStorage()
        pass

    def set_etalon_images(self, etalon_images_dict: dict):
        """
        Устанавливает эталонные изображения в хранилище.
        
        Args:
            etalon_images_dict: Словарь {img_id: image}, где image - numpy array (BGR)
        """
        self.board_storage.etalon_images = etalon_images_dict.copy()

    def set_etalon_markup(self, markup_json):
        
        self.board_storage.etalon_markup = markup_json.copy()

    def prepare_etalon(self):
        self.__get_etalon_component_crops()

    
    def __get_etalon_component_crops(self):
        """
        Создает кропы компонентов из эталонных изображений по разметке.
        Сохраняет кропы в board_storage.etalon_components.
        """
        if not self.board_storage.etalon_images:
            print("Предупреждение: нет эталонных изображений")
            return
        
        if not self.board_storage.etalon_markup:
            print("Предупреждение: нет разметки эталона")
            return
        
        # Проходим по всем изображениям в разметке
        for photo_key, bboxes in self.board_storage.etalon_markup.items():
            # Проверяем наличие изображения для этого photo_key
            if photo_key not in self.board_storage.etalon_images:
                print(f"Предупреждение: изображение {photo_key} не найдено в эталонных изображениях")
                continue
            
            etalon_image = self.board_storage.etalon_images[photo_key]
            
            # Обрабатываем каждый bbox
            for idx, bbox in enumerate(bboxes):
                component_id = bbox.get('bbox_id', f"{photo_key}_component_{idx}")
                
                # Извлекаем кроп компонента
                crop = crop_by_bbox(etalon_image, bbox)
                
                if crop is not None:
                    # Сохраняем кроп в хранилище
                    self.board_storage.etalon_components[component_id] = {
                        'image': crop,
                        'photo_key': photo_key,
                        'bbox': bbox.copy(),
                    }
                    print(f"Создан кроп компонента {component_id} из {photo_key}")
                else:
                    print(f"Предупреждение: не удалось создать кроп для компонента {component_id}")