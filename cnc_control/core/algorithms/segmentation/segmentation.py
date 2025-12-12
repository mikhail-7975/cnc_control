"""
Модуль для сегментации компонентов с использованием нейронной сети.
"""
import cv2
import numpy as np
import torch
import segmentation_models_pytorch as smp
from typing import Tuple


class ComponentSegmenter:
    """
    Класс для сегментации компонентов на изображениях с использованием U-Net.
    """
    
    def __init__(
        self,
        model_path: str,
        device: str = 'cpu',
        encoder_name: str = "resnet101",
        encoder_weights: str = "imagenet",
        input_size: Tuple[int, int] = (224, 224)
    ):
        """
        Инициализация сегментатора компонентов.
        
        Args:
            model_path: Путь к файлу с весами модели
            device: Устройство для вычислений ('cpu' или 'cuda')
            encoder_name: Имя энкодера для U-Net
            encoder_weights: Веса для инициализации энкодера
            input_size: Размер входного изображения для модели
        """
        self.device = device
        self.input_size = input_size
        
        # Создаем модель U-Net
        self.model = smp.Unet(
            encoder_name=encoder_name,
            encoder_weights=encoder_weights,
            in_channels=1,
            classes=1,
            activation=None
        )
        
        # Загружаем веса модели
        self.model.load_state_dict(torch.load(model_path, map_location=device))
        self.model.to(device)
        self.model.eval()
    
    def predict_mask(self, image_gray: np.ndarray, original_size: Tuple[int, int] = None) -> np.ndarray:
        """
        Предсказывает маску компонента на изображении.
        
        Args:
            image_gray: Градационное изображение (numpy array)
            original_size: Исходный размер изображения (width, height) для восстановления размера маски
        
        Returns:
            np.ndarray: Предсказанная маска (нормализованная, значения от 0 до 1)
        """
        # Изменяем размер изображения до размера входа модели
        resized = cv2.resize(image_gray, self.input_size, interpolation=cv2.INTER_LINEAR)
        
        # Нормализуем в диапазон [0, 1] и конвертируем в тензор
        # Формат: (1, 1, H, W) - batch, channels, height, width
        resized_normalized = resized.astype(np.float32) / 255.0
        tensor = torch.from_numpy(resized_normalized).unsqueeze(0).unsqueeze(0).to(self.device)
        
        # Предсказание
        with torch.no_grad():
            output = self.model(tensor).squeeze(0).cpu().numpy()
        
        # Извлекаем маску (если выход многоканальный, берем первый канал)
        mask = output[0] if output.shape[0] == 1 else output
        
        # Восстанавливаем исходный размер, если указан
        if original_size is not None:
            w, h = original_size
            mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
        
        return mask
