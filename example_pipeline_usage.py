import json
import cv2
import numpy as np
from pathlib import Path



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

    def set_etalon_markup(self):
        with open("markup_info/bboxes.json") as f:
            markup = json.load(f)
        self.board_storage.etalon_markup = markup.copy()

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


    def process_board(self, crop_components_list, heatmap_list, anomaly_map_list, ):
        
        pass

    def compare_metrics(self):
        pass

    def inspect():
        pass

class BoardComparer():
    def __init__(self):
        pass

    def add_cmp_rule(self, component_id, rule):
        pass

    def compare(self):
        pass

class BoardStorage():
    def __init__(self) -> None:
        # Словарь эталонных изображений: {img_id: image (numpy array BGR)}
        self.etalon_images = {}
        
        # Словарь кропов компонентов эталона: {component_id: {
        #   'image': np.ndarray,
        #   'photo_key': str,
        #   'component_name': str,
        #   'bbox': dict,
        #   'center': tuple,
        #   'angle': float
        # }}
        self.etalon_components = {} 
        
        # Разметка эталона: {photo_key: [bbox1, bbox2, ...]}
        self.etalon_markup = {}

        self.control_images = []
        self.control_crops = []
        self.control_ids = []

        # Сохраняем, какой фрагмент эталона соответствует какому фрагменту контроля
        self.img_ids_matching = {}

    def add_etalon_crop(self, crop_img, crop_id):
        """
        Добавляет кроп компонента эталона в хранилище.
        
        Args:
            crop_img: Кроп изображения (numpy array)
            crop_id: Идентификатор компонента
        """
        if crop_id not in self.etalon_components:
            self.etalon_components[crop_id] = {}
        self.etalon_components[crop_id]['image'] = crop_img
    


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
    etalon_folder = "etalon_images"  # Путь к папке с эталонными изображениями
    etalon_images_dict = load_etalon_images_from_folder(etalon_folder)
    
    if not etalon_images_dict:
        print(f"Ошибка: не найдено изображений в папке {etalon_folder}")
        print("Убедитесь, что папка существует и содержит изображения")
    else:
        print(f"Загружено {len(etalon_images_dict)} эталонных изображений")
        
        # Загружаем изображения в хранилище
        runner.set_etalon_images(etalon_images_dict)
        
        # Загружаем разметку
        runner.set_etalon_markup()
        
        # Подготавливаем эталон (создаем кропы компонентов)
        print("\nПодготовка эталонной платы...")
        runner.prepare_etalon()
        
        print(f"\nПодготовка завершена:")
        print(f"  - Загружено изображений: {len(runner.board_storage.etalon_images)}")
        print(f"  - Создано кропов компонентов: {len(runner.board_storage.etalon_components)}")
    
    # Старый код (закомментирован, так как классы не определены)
    # image_provider = FileImageProvider()
    # annotation_manager = AnnotationManager()
    # database = InspectionDatabase()
    # config_manager = AlgorithmConfigManager()
    # 
    # inspection_executor = InspectionExecutor(config_manager=config_manager)
    # inspection_executor.register_inspector(
    #     "segmentation",
    #     SegmentationInspector(model_path="models/segmentation_model.pth", device="cpu")
    # )
    # 
    # pipeline_manager = PipelineManager(
    #     image_provider=image_provider,
    #     annotation_manager=annotation_manager,
    #     inspection_executor=inspection_executor,
    #     database=database,
    #     config_manager=config_manager
    # )
    # 
    # result = pipeline_manager.run_full_inspection(
    #     reference_source="path/to/reference/images",
    #     control_source="path/to/control/images",
    #     annotation_file="markup_info/bboxes.json",
    #     algorithms=["segmentation"],
    #     save_image_data=False
    # )
    # 
    # print(f"Результат полной инспекции: {result}")
    # pipeline_manager.save_database("inspection_results.db", format="pickle")
