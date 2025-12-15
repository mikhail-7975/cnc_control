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

        # Словарь выровненных контрольных изображений: {img_id: image (numpy array BGR)}
        # Структура аналогична etalon_images
        self.aligned_control_images = {}
        
        # Словарь кропов компонентов контроля: {component_id: {
        #   'image': np.ndarray,
        #   'photo_key': str,  # идентификатор контрольного изображения
        #   'etalon_component_id': str,  # идентификатор соответствующего эталонного компонента
        #   'bbox': dict,
        # }}
        self.control_components = {}

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