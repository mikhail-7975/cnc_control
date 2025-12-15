import json

from cnc_control.core.pipeline.board_storage import BoardStorage
from cnc_control.core.utils.crop import crop_by_bbox
from cnc_control.core.utils.image_aligner import SiftImageAligner
from cnc_control.core.algorithms.segmentation.segmentation_inspection import SegmentationInspectionAlgorithm

class InspectionRunner():
    def __init__(self) -> None:
        self.board_storage = BoardStorage()
        self.img_aligner = SiftImageAligner()
        self.inspection_algorithms = {
            "segmentation":SegmentationInspectionAlgorithm(
                "data/extended_many_augs.pth"
            )
        } # inspection_algorithm_name: AlgoritmClass()
        self.etalon_control_mapping = None
        pass

    def set_etalon_control_mapping(self):
        with open("markup_info/etalon_mapping_upd.json") as f:
            etalon_mapping_data = json.load(f)
        self.etalon_control_mapping = etalon_mapping_data

    def add_inspection_algorithm(self, inspector_name, inspector):
        self.inspection_algorithms[inspector_name] = inspector

    def set_etalon_images(self, etalon_images_dict: dict):
        """
        Устанавливает эталонные изображения в хранилище.
        
        Args:
            etalon_images_dict: Словарь {img_id: image}, где image - numpy array (BGR)
        """
        self.board_storage.etalon_images = etalon_images_dict.copy()

    def set_etalon_markup(self, markup_json):
        self.board_storage.etalon_markup = markup_json.copy()

    def set_control_images(self, control_images_dict: dict):
        """
        Устанавливает контрольные изображения для выравнивания.
        
        Args:
            control_images_dict: Словарь {img_id: image}, где image - numpy array (BGR)
        """
        self.control_images_dict = control_images_dict.copy()

    def prepare_etalon(self):
        self.__get_etalon_component_crops()

    def align_control_images(self):
        if not hasattr(self, 'control_images_dict') or not self.control_images_dict:
            print("Предупреждение: контрольные изображения не загружены")
            return
        
        if not self.etalon_control_mapping:
            print("Предупреждение: маппинг эталон-контроль не установлен")
            return
        
        if not self.board_storage.etalon_images:
            print("Предупреждение: эталонные изображения не загружены")
            return
        
        if not self.board_storage.etalon_markup:
            print("Предупреждение: разметка эталона не загружена")
            return
        
        # Шаг 1: Получаем список контролируемых изображений и выравниваем их
        print("Выравнивание контрольных изображений...")
        for mapping_entry in self.etalon_control_mapping:
            etalon_id = mapping_entry[0]
            control_ids = mapping_entry[1]
            
            # Проверяем наличие эталонного изображения
            if etalon_id not in self.board_storage.etalon_images:
                print(f"Предупреждение: эталонное изображение {etalon_id} не найдено")
                continue
            
            etalon_image = self.board_storage.etalon_images[etalon_id]
            
            # Выравниваем каждое контрольное изображение относительно эталонного
            for control_id in control_ids:
                if control_id not in self.control_images_dict:
                    print(f"Предупреждение: контрольное изображение {control_id} не найдено")
                    continue
                
                control_image = self.control_images_dict[control_id]
                
                # Выравниваем контрольное изображение относительно эталонного
                aligned_image = self.img_aligner.align(etalon_image, control_image)
                
                # Сохраняем выровненное изображение
                self.board_storage.aligned_control_images[control_id] = aligned_image
                print(f"Выровнено контрольное изображение {control_id} относительно {etalon_id}")
        

    def get_control_components_crop(self):
        # Шаг 2: Получаем кропы контрольных компонентов по разметке эталона
        print("\nПолучение кропов контрольных компонентов...")
        for mapping_entry in self.etalon_control_mapping:
            etalon_id = mapping_entry[0]
            control_ids = mapping_entry[1]
            
            # Проверяем наличие разметки для эталонного изображения
            if etalon_id not in self.board_storage.etalon_markup:
                continue
            
            bboxes = self.board_storage.etalon_markup[etalon_id]
            
            # Для каждого контрольного изображения получаем кропы компонентов
            for control_id in control_ids:
                if control_id not in self.board_storage.aligned_control_images:
                    continue
                
                control_image = self.board_storage.aligned_control_images[control_id]
                
                # Обрабатываем каждый bbox из разметки эталона
                for idx, bbox in enumerate(bboxes):
                    # Формируем component_id так же, как в prepare_etalon
                    etalon_component_id = bbox.get('bbox_id', f"{etalon_id}_component_{idx}")
                    
                    # Извлекаем кроп компонента из контрольного изображения
                    crop = crop_by_bbox(control_image, bbox)
                    
                    if crop is not None:
                        # Формируем уникальный идентификатор для контрольного компонента
                        control_component_id = f"{control_id}_{etalon_component_id}"
                        
                        # Сохраняем кроп в хранилище
                        self.board_storage.control_components[control_component_id] = {
                            'image': crop,
                            'photo_key': control_id,
                            'etalon_component_id': etalon_component_id,
                            'bbox': bbox.copy(),
                        }
                        print(f"Создан кроп контрольного компонента {control_component_id} из {control_id} (эталон: {etalon_component_id})")
                    else:
                        print(f"Предупреждение: не удалось создать кроп для контрольного компонента {control_id}_{etalon_component_id}")
        
        print(f"\nПодготовка контроля завершена:")
        print(f"  - Выровнено контрольных изображений: {len(self.board_storage.aligned_control_images)}")
        print(f"  - Создано кропов контрольных компонентов: {len(self.board_storage.control_components)}")

    def prepare_control(self):
        """
        Подготавливает контрольные изображения:
        1. Получает список контролируемых изображений из etalon_control_mapping
        2. Выравнивает контролируемые изображения относительно эталонных
        3. Сохраняет выровненные изображения в board_storage.aligned_control_images
        4. Получает кропы контрольных компонентов по разметке эталона
        5. Сохраняет контрольные компоненты в board_storage.control_components
        """
        self.align_control_images()
        self.get_control_components_crop()
        
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

    def run_inspection(self):
        """
        Запускает инспекцию компонентов:
        1. Итерируется по кропам эталонных компонентов
        2. Для каждого эталонного компонента находит соответствующие контрольные компоненты
        3. Запускает алгоритм инспекции для каждой пары
        4. Определяет результат инспекции (не дефект / подозрение на дефект / дефект)
        5. Сохраняет результаты в board_storage.inspection_results
        """
        if not self.board_storage.etalon_components:
            print("Предупреждение: нет эталонных компонентов для инспекции")
            return
        
        if not self.board_storage.control_components:
            print("Предупреждение: нет контрольных компонентов для инспекции")
            return
        
        if not self.inspection_algorithms:
            print("Предупреждение: нет алгоритмов инспекции")
            return
        
        print("Запуск инспекции компонентов...")
        inspection_count = 0
        defect_count = 0
        suspicion_count = 0
        ok_count = 0
        
        # Итерируемся по эталонным компонентам
        for num, (etalon_component_id, etalon_component_data) in enumerate(self.board_storage.etalon_components.items()):
            print(num, etalon_component_id)
            etalon_crop = etalon_component_data['image']
            # etalon_photo_key = etalon_component_data['photo_key']
            etalon_bbox = etalon_component_data.get('bbox', {})
            
            # Определяем алгоритм инспекции из разметки
            algorithm_name = etalon_bbox.get('algorithm', 'segmentation')
            
            # Проверяем наличие алгоритма
            if algorithm_name not in self.inspection_algorithms:
                print(f"Предупреждение: алгоритм {algorithm_name} не найден, пропускаем компонент {etalon_component_id}")
                continue
            
            inspection_algorithm = self.inspection_algorithms[algorithm_name]
            
            # Находим все контрольные компоненты, соответствующие этому эталонному
            for control_component_id, control_component_data in self.board_storage.control_components.items():
                if control_component_data['etalon_component_id'] != etalon_component_id:
                    continue
                
                control_crop = control_component_data['image']
                control_photo_key = control_component_data['photo_key']
                
                # Запускаем алгоритм инспекции
                try:
                    # Алгоритм возвращает кортеж (результат, (метрики и другая информация))
                    # результат: 'не дефект', 'подозрение на дефект' или 'дефект'
                    algorithm_result = inspection_algorithm(etalon_crop, control_crop)
                    
                    # Ожидаем формат: (result, metrics_tuple)
                    if len(algorithm_result) >= 2:
                        inspection_result = algorithm_result[0]
                        metrics = algorithm_result[1]
                    else:
                        # Если алгоритм возвращает старый формат, обрабатываем как ошибку
                        print(f"Предупреждение: алгоритм {algorithm_name} вернул неожиданный формат результата")
                        continue
                    
                    # Формируем уникальный идентификатор для результата инспекции
                    inspection_id = f"{etalon_component_id}_{control_component_id}"
                    
                    # Сохраняем результат инспекции
                    self.board_storage.inspection_results[inspection_id] = {
                        'result': inspection_result,
                        'metrics': metrics,
                        'etalon_component_id': etalon_component_id,
                        'control_component_id': control_component_id,
                        'algorithm': algorithm_name,
                    }
                    
                    inspection_count += 1
                    if inspection_result == 'дефект':
                        defect_count += 1
                    elif inspection_result == 'подозрение на дефект':
                        suspicion_count += 1
                    else:
                        ok_count += 1
                    
                    if inspection_count <= 10:  # Показываем первые 10 для краткости
                        print(f"  ✓ Инспекция {inspection_id}: {inspection_result}")
                    
                except Exception as e:
                    print(f"Ошибка при инспекции {etalon_component_id} vs {control_component_id}: {e}")
                    import traceback
                    traceback.print_exc()
        
        print(f"\nИнспекция завершена:")
        print(f"  - Всего проверок: {inspection_count}")
        print(f"  - Не дефект: {ok_count}")
        print(f"  - Подозрение на дефект: {suspicion_count}")
        print(f"  - Дефект: {defect_count}")