"""
MainWindow Controller V2

Контроллер для работы с mainwindow_ui_v2.py.
Содержит все обработчики из старого контроллера и заготовки для новых кнопок.

Если имя класса UI отличается от Ui_MainWindowV2, измените импорт в начале файла.
"""
import sys
import cv2
import time
import json
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QLabel, QListWidget,
    QAbstractItemView, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QWidget, QInputDialog, QScrollArea,
    QAbstractItemView, QVBoxLayout, QFileDialog, QMessageBox, QWidget, QInputDialog
)

import re
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QLabel, QListWidget,
    QAbstractItemView, QVBoxLayout, QFileDialog, QMessageBox, QWidget, QInputDialog,
    QScrollArea, QGridLayout, QTreeView, QCheckBox
)
from PyQt6.QtCore import QTimer, Qt, QPoint, QRectF
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QPolygonF, QCursor, QFont, QShortcut, QKeySequence, QStandardItemModel, QStandardItem, QBrush
import math
# Try to import UI v2 - adjust class name if needed
# Add project root to path for UI imports
# project_root = Path(__file__).parent.parent.parent
# if str(project_root) not in sys.path:
#     sys.path.insert(0, str(project_root))

from ui.generated.mainwindow_ui_v2 import Ui_MainWindow as Ui_MainWindowV2
from cnc_control.core.cnc.drivers.grbl_driver import CncMachineDriver
from cnc_control.core.camera.camera_reader import ThreadSafeCameraReader
from cnc_control.utils import create_component_collage, save_component_crops, get_component_crop
from cnc_control.core.algorithms import SiftImageAligner
from cnc_control.core.algorithms.segmentation import (
    ImagePreprocessor,
    ComponentSegmenter,
    MaskPostprocessor,
    calculate_iou,
    get_bottom_edge_angle
)


class ComponentTreeView(QTreeView):
    """Кастомный QTreeView для списка компонентов с поддержкой переименования по Enter."""
    
    def __init__(self, parent=None, main_window_ref=None):
        super().__init__(parent)
        self.main_window_ref = main_window_ref
    
    def keyPressEvent(self, event):
        """Обработка нажатия клавиш."""
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # Если нажат Enter, пытаемся переименовать выбранный компонент
            selection = self.selectedIndexes()
            if selection:
                index = selection[0]
                model = self.model()
                if model:
                    item = model.itemFromIndex(index)
                    if item and item.parent():  # Это дочерний элемент (компонент, а не изображение)
                        if self.main_window_ref:
                            self.main_window_ref._rename_component_from_tree(item)
                        return
        elif event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            # Если нажат Delete/Backspace, удаляем выбранный компонент
            selection = self.selectedIndexes()
            if selection:
                index = selection[0]
                model = self.model()
                if model:
                    item = model.itemFromIndex(index)
                    if item and item.parent():  # Это дочерний элемент (компонент, а не изображение)
                        if self.main_window_ref:
                            self.main_window_ref._delete_component_from_tree(item)
                        return
        
        # Вызываем стандартный обработчик для других клавиш
        super().keyPressEvent(event)


class MainWindowControllerV2(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindowV2()
        self.ui.setupUi(self)

        # === Replace scroll area contents with QListWidget ===
        # For take image points
        self.take_image_points_list = QListWidget()
        self.take_image_points_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.ui.take_image_points_display_area.setWidget(self.take_image_points_list)

        # For component coordinates
        self.component_coordinates_list = QListWidget()
        self.component_coordinates_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # self.ui.component_coordinates_display_area.setWidget(self.component_coordinates_list)

        # Camera variables
        self.cam = None
        self.timer = QTimer(self)

        # image_label
        self.image_label = QLabel(self.ui.image_displayer)
        self.image_arch = None
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(False)
        self.image_label.resize(self.ui.image_displayer.size())
        self.clear_image_display()

        # CNC-related variables
        self.cnc_connected = False
        self.driver = None

        # Etalon images variables
        self.etalon_images = []  # Список загруженных эталонных изображений (numpy arrays)
        self.etalon_image_names = []  # Список имен файлов изображений
        self.current_etalon_index = -1  # Индекс текущего изображения (-1 если нет изображений)
        
        # Control images data
        self.images_data = []  # [(row, col, file_path, image), ...] - данные контрольных изображений
        
        # Component crops data
        # Список словарей с информацией о кропах компонентов:
        # {
        #   'etalon_crop': np.ndarray,
        #   'control_crop': np.ndarray,
        #   'photo_key': str,  # например, "photo_0_0"
        #   'component_name': str,  # имя компонента
        #   'component_id': int,  # индекс компонента
        #   'col': int,  # столбец контрольного изображения
        #   'row': int,  # строка контрольного изображения
        #   'etalon_col': int,  # столбец эталонного изображения
        #   'etalon_row': int,  # строка эталонного изображения
        #   'bbox': dict  # исходный bbox с координатами
        # }
        self.component_crops = []
        
        # Reference to marking window to prevent garbage collection
        self.marking_window = None
        
        # Preference: don't ask for delete confirmation
        self.skip_delete_confirmation = False
        
        # Etalon image display widget with markup support
        self.etalon_image_widget = ImageDisplayWidget(self.ui.display_etalon_image_widget)
        self.etalon_image_widget.resize(self.ui.display_etalon_image_widget.size())
        # Store reference to main window for bbox updates and auto-save
        self.etalon_image_widget.main_window_ref = self
        # Enable focus for keyboard events
        self.etalon_image_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # Zoom settings for etalon preview
        self.etalon_zoom_scale = 1.0
        self.etalon_min_zoom = 0.1
        self.etalon_max_zoom = 10.0
        self.etalon_zoom_step = 0.1
        self.etalon_initial_zoom_calculated = False
        self.etalon_original_pixmap = None  # Store original unscaled pixmap
        
        self.clear_etalon_display()
        
        # Replace QTableView with QTreeView for hierarchical component list
        # Store reference to original table view
        if hasattr(self.ui, 'component_tableView'):
            # Create custom QTreeView to replace QTableView
            self.component_tree_view = ComponentTreeView(main_window_ref=self)
            self.component_tree_view.setObjectName("component_treeView")
            # Replace the table view in the layout
            layout = self.ui.component_scrollAreaWidgetContents.layout()
            if layout:
                # Find the table view in the layout
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item and item.widget() == self.ui.component_tableView:
                        # Remove old table view
                        layout.removeWidget(self.ui.component_tableView)
                        self.ui.component_tableView.setParent(None)
                        # Add tree view at the same position
                        layout.insertWidget(i, self.component_tree_view)
                        break
                else:
                    # If not found, just add it
                    layout.addWidget(self.component_tree_view)
        
        # Initialize component list
        self.update_component_list()

        # Connect signals
        self.setup_connections()

    def setup_connections(self):
        # Camera
        self.ui.connect_camera_button.clicked.connect(self.toggle_camera)
        self.timer.timeout.connect(self.update_frame)

        # Joystick buttons (X-axis)
        self.ui.left_1_button.clicked.connect(lambda: self.move_axis('X', -1))
        self.ui.left_10_button.clicked.connect(lambda: self.move_axis('X', -10))
        self.ui.left_50_button.clicked.connect(lambda: self.move_axis('X', -50))
        self.ui.right_1_button.clicked.connect(lambda: self.move_axis('X', 1))
        self.ui.right_10_button.clicked.connect(lambda: self.move_axis('X', 10))
        self.ui.right_50_button.clicked.connect(lambda: self.move_axis('X', 50))

        # Joystick buttons (Y-axis)
        self.ui.up_1_button.clicked.connect(lambda: self.move_axis('Y', 1))
        self.ui.up10_button.clicked.connect(lambda: self.move_axis('Y', 10))
        self.ui.up50_button.clicked.connect(lambda: self.move_axis('Y', 50))
        
        # Y-axis buttons (down movement)
        self.ui.down_1_button.clicked.connect(lambda: self.move_axis('Y', -1))
        self.ui.down_10_button.clicked.connect(lambda: self.move_axis('Y', -10))
        self.ui.down_50_button.clicked.connect(lambda: self.move_axis('Y', -50))

        # Zeroing buttons
        self.ui.zero_x_button.clicked.connect(lambda: self.zero_axis('X'))
        self.ui.zero_y_button.clicked.connect(lambda: self.zero_axis('Y'))
        self.ui.zero_all_button.clicked.connect(self.zero_all)

        # Initialize coordinate labels
        self.ui.cur_x_label.setText("0.0")
        self.ui.cur_y_label.setText("0.0")

        # CNC connection
        self.ui.connect_cnc_button.clicked.connect(self.toggle_cnc_connection)

        # Coordinate list management
        self.ui.add_point_button.clicked.connect(self.add_image_point)
        self.ui.delete_point_button.clicked.connect(self.delete_selected_image_point)
        
        # Etalon images management
        self.ui.load_etalon_images_button.clicked.connect(self.load_etalon_images)
        self.ui.next_etalonimage_button.clicked.connect(self.next_etalon_image)
        self.ui.prev_etalon_image_button.clicked.connect(self.prev_etalon_image)
        # Hide the markup button - markup is now done directly on preview
        self.ui.mark_image_button.setVisible(False)
        # Connect keyboard shortcuts for saving bboxes and zooming
        from PyQt6.QtGui import QShortcut, QKeySequence
        self.save_bboxes_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.save_bboxes_shortcut.activated.connect(self.save_current_etalon_bboxes)
        # Zoom shortcuts
        self.zoom_in_shortcut = QShortcut(QKeySequence("Ctrl+="), self)
        self.zoom_in_shortcut.activated.connect(self.etalon_zoom_in)
        self.zoom_in_plus_shortcut = QShortcut(QKeySequence("Ctrl++"), self)
        self.zoom_in_plus_shortcut.activated.connect(self.etalon_zoom_in)
        self.zoom_out_shortcut = QShortcut(QKeySequence("Ctrl+-"), self)
        self.zoom_out_shortcut.activated.connect(self.etalon_zoom_out)
        
        # Inspection buttons
        self.ui.load_control_photo_pushButton.clicked.connect(self.load_control_photo)
        self.ui.run_inspection_pushButton.clicked.connect(self.run_inspection)

    # === Coordinate list functionality ===

    def add_image_point(self):
        """Добавить текущую позицию как точку съёмки."""
        x = self.ui.cur_x_label.text()
        y = self.ui.cur_y_label.text()
        item_text = f"({x}, {y})"
        self.take_image_points_list.addItem(item_text)

    def delete_selected_image_point(self):
        """Удалить выбранную точку съёмки."""
        row = self.take_image_points_list.currentRow()
        if row >= 0:
            self.take_image_points_list.takeItem(row)
        else:
            self.show_error("Нет выбранной точки для удаления.")

    def add_component_coordinate(self):
        """Добавить текущую позицию как координату компонента."""
        x = self.ui.cur_x_label.text()
        y = self.ui.cur_y_label.text()
        item_text = f"Комп: ({x}, {y})"
        self.component_coordinates_list.addItem(item_text)

    def delete_selected_component(self):
        """Удалить выбранную координату компонента."""
        row = self.component_coordinates_list.currentRow()
        if row >= 0:
            self.component_coordinates_list.takeItem(row)
        else:
            self.show_error("Нет выбранной координаты компонента для удаления.")

    # === New button handlers (заготовки) ===

    def load_component_coordinates_from_file(self):
        """Загрузить координаты компонентов из файла."""
        # TODO: Реализовать загрузку координат из файла
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить координаты компонентов", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                # Заглушка для реализации
                print(f"Загрузка координат из файла: {file_path}")
                # TODO: Реализовать парсинг файла и загрузку в список
                self.show_error("Функция загрузки из файла ещё не реализована")
            except Exception as e:
                self.show_error(f"Ошибка при загрузке файла: {str(e)}")

    def save_component_coordinates_to_file(self):
        """Сохранить координаты компонентов в файл."""
        # TODO: Реализовать сохранение координат в файл
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить координаты компонентов", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                # Заглушка для реализации
                print(f"Сохранение координат в файл: {file_path}")
                # TODO: Реализовать сохранение списка координат в файл
                self.show_error("Функция сохранения в файл ещё не реализована")
            except Exception as e:
                self.show_error(f"Ошибка при сохранении файла: {str(e)}")

    def save_image_points_to_file(self):
        """Сохранить точки съёмки в файл."""
        # TODO: Реализовать сохранение точек съёмки в файл
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить точки съёмки", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                # Заглушка для реализации
                print(f"Сохранение точек съёмки в файл: {file_path}")
                # TODO: Реализовать сохранение списка точек в файл
                self.show_error("Функция сохранения точек ещё не реализована")
            except Exception as e:
                self.show_error(f"Ошибка при сохранении файла: {str(e)}")

    def load_image_points_from_file(self):
        """Загрузить точки съёмки из файла."""
        # TODO: Реализовать загрузку точек съёмки из файла
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить точки съёмки", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                # Заглушка для реализации
                print(f"Загрузка точек съёмки из файла: {file_path}")
                # TODO: Реализовать парсинг файла и загрузку в список
                self.show_error("Функция загрузки точек ещё не реализована")
            except Exception as e:
                self.show_error(f"Ошибка при загрузке файла: {str(e)}")

    def edit_selected_component(self):
        """Редактировать выбранную координату компонента."""
        # TODO: Реализовать редактирование координаты компонента
        row = self.component_coordinates_list.currentRow()
        if row >= 0:
            item = self.component_coordinates_list.item(row)
            print(f"Редактирование компонента: {item.text()}")
            # TODO: Открыть диалог редактирования
            self.show_error("Функция редактирования компонента ещё не реализована")
        else:
            self.show_error("Выберите компонент для редактирования.")

    def edit_selected_image_point(self):
        """Редактировать выбранную точку съёмки."""
        # TODO: Реализовать редактирование точки съёмки
        row = self.take_image_points_list.currentRow()
        if row >= 0:
            item = self.take_image_points_list.item(row)
            print(f"Редактирование точки съёмки: {item.text()}")
            # TODO: Открыть диалог редактирования
            self.show_error("Функция редактирования точки ещё не реализована")
        else:
            self.show_error("Выберите точку для редактирования.")

    def clear_all_components(self):
        """Очистить все координаты компонентов."""
        reply = QMessageBox.question(
            self, "Подтверждение", "Очистить все координаты компонентов?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.component_coordinates_list.clear()
            print("Все координаты компонентов очищены.")

    def clear_all_image_points(self):
        """Очистить все точки съёмки."""
        reply = QMessageBox.question(
            self, "Подтверждение", "Очистить все точки съёмки?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.take_image_points_list.clear()
            print("Все точки съёмки очищены.")

    def open_camera_settings(self):
        """Открыть настройки камеры."""
        # TODO: Реализовать диалог настроек камеры
        print("Открытие настроек камеры")
        self.show_error("Диалог настроек камеры ещё не реализован")

    def open_cnc_settings(self):
        """Открыть настройки CNC."""
        # TODO: Реализовать диалог настроек CNC
        print("Открытие настроек CNC")
        self.show_error("Диалог настроек CNC ещё не реализован")

    def go_to_selected_point(self):
        """Переместиться к выбранной точке съёмки."""
        # TODO: Реализовать автоматическое перемещение к точке
        row = self.take_image_points_list.currentRow()
        if row >= 0:
            item = self.take_image_points_list.item(row)
            print(f"Перемещение к точке: {item.text()}")
            # TODO: Парсить координаты из текста и переместить станок
            self.show_error("Функция перемещения к точке ещё не реализована")
        else:
            self.show_error("Выберите точку для перемещения.")

    def go_to_selected_component(self):
        """Переместиться к выбранному компоненту."""
        # TODO: Реализовать автоматическое перемещение к компоненту
        row = self.component_coordinates_list.currentRow()
        if row >= 0:
            item = self.component_coordinates_list.item(row)
            print(f"Перемещение к компоненту: {item.text()}")
            # TODO: Парсить координаты из текста и переместить станок
            self.show_error("Функция перемещения к компоненту ещё не реализована")
        else:
            self.show_error("Выберите компонент для перемещения.")

    def capture_image_at_current_position(self):
        """Сделать снимок в текущей позиции."""
        # TODO: Реализовать съёмку изображения
        if self.cam is None:
            self.show_error("Камера не подключена.")
            return
        try:
            frame = self.cam.get_image()
            if frame is not None:
                # TODO: Сохранить изображение с метаданными (координаты, время и т.д.)
                x = self.ui.cur_x_label.text()
                y = self.ui.cur_y_label.text()
                print(f"Съёмка изображения в позиции ({x}, {y})")
                self.show_error("Функция сохранения изображения ещё не реализована")
        except Exception as e:
            self.show_error(f"Ошибка при съёмке изображения: {str(e)}")

    def start_automation_sequence(self):
        """Запустить автоматическую последовательность."""
        # TODO: Реализовать автоматическую последовательность
        print("Запуск автоматической последовательности")
        # TODO: Реализовать логику автоматического перемещения и съёмки
        self.show_error("Функция автоматической последовательности ещё не реализована")

    def stop_automation_sequence(self):
        """Остановить автоматическую последовательность."""
        # TODO: Реализовать остановку автоматической последовательности
        print("Остановка автоматической последовательности")
        # TODO: Реализовать логику остановки
        self.show_error("Функция остановки последовательности ещё не реализована")

    # === Etalon images functionality ===

    def load_etalon_images(self):
        """Загрузить эталонные изображения из файлов."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите эталонные изображения",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.tiff *.tif);;All Files (*)"
        )
        
        if not file_paths:
            return
        
        try:
            loaded_images = []
            loaded_names = []
            for file_path in file_paths:
                # Загружаем изображение с помощью OpenCV
                image = cv2.imread(file_path)
                if image is None:
                    print(f"Предупреждение: не удалось загрузить изображение {file_path}")
                    continue
                loaded_images.append(image)
                # Извлекаем имя файла без расширения
                file_name = Path(file_path).stem
                loaded_names.append(file_name)
            
            if loaded_images:
                self.etalon_images = loaded_images
                self.etalon_image_names = loaded_names
                self.current_etalon_index = 0
                # Reset zoom when loading new images
                self.etalon_initial_zoom_calculated = False
                self.etalon_zoom_scale = 1.0
                self.display_current_etalon_image()
                print(f"Загружено {len(self.etalon_images)} эталонных изображений")
            else:
                self.show_error("Не удалось загрузить ни одного изображения")
        except Exception as e:
            self.show_error(f"Ошибка при загрузке изображений: {str(e)}")

    def display_current_etalon_image(self):
        """Отобразить текущее эталонное изображение."""
        if not self.etalon_images or self.current_etalon_index < 0:
            self.clear_etalon_display()
            self.update_etalon_image_label()
            return
        
        if self.current_etalon_index >= len(self.etalon_images):
            self.current_etalon_index = len(self.etalon_images) - 1
        
        try:
            # Reset zoom calculation for new image (will recalculate initial fit)
            self.etalon_initial_zoom_calculated = False
            
            # Clear bboxes before loading new image (they should already be cleared in next/prev methods)
            # But clear here too as a safety measure
            if hasattr(self, 'etalon_image_widget'):
                self.etalon_image_widget.bounding_boxes = []
            
            image = self.etalon_images[self.current_etalon_index]
            # Конвертируем BGR в RGB для Qt
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            
            # Store original pixmap for zooming
            self.etalon_original_pixmap = pixmap
            
            # Calculate initial zoom scale to fit widget (only on first display)
            if not self.etalon_initial_zoom_calculated:
                widget_width = self.ui.display_etalon_image_widget.width()
                widget_height = self.ui.display_etalon_image_widget.height()
                
                if widget_width > 0 and widget_height > 0 and w > 0 and h > 0:
                    scale_x = widget_width / w
                    scale_y = widget_height / h
                    # Use smaller scale to fit image completely
                    self.etalon_zoom_scale = min(scale_x, scale_y) * 0.95  # 0.95 for small margin
                    # Limit initial zoom scale to reasonable bounds
                    self.etalon_zoom_scale = max(self.etalon_min_zoom, min(self.etalon_zoom_scale, self.etalon_max_zoom))
                    self.etalon_initial_zoom_calculated = True
            
            # Apply zoom scaling
            scaled_width = int(w * self.etalon_zoom_scale)
            scaled_height = int(h * self.etalon_zoom_scale)
            
            # Scale pixmap
            scaled_pixmap = pixmap.scaled(
                scaled_width,
                scaled_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Set the pixmap in the ImageDisplayWidget
            self.etalon_image_widget.set_image(scaled_pixmap)
            self.etalon_image_widget.resize(self.ui.display_etalon_image_widget.size())
            self.ui.display_etalon_image_widget.setStyleSheet("")
            
            # Clear bboxes before loading (ensure clean state)
            if hasattr(self, 'etalon_image_widget'):
                self.etalon_image_widget.bounding_boxes = []
            
            # Load bboxes for the current image (will be scaled appropriately)
            self.load_current_etalon_bboxes()
            
            # Обновляем список компонентов при загрузке изображения
            self.update_component_list()
            
            self.update_etalon_image_label()
        except Exception as e:
            self.show_error(f"Ошибка при отображении изображения: {str(e)}")

    def update_etalon_image_label(self):
        """Обновить метку с номером текущего изображения."""
        if not self.etalon_images or self.current_etalon_index < 0:
            self.ui.etalon_image_number_label.setText("Нет изображений")
        else:
            current_num = self.current_etalon_index + 1
            total = len(self.etalon_images)
            self.ui.etalon_image_number_label.setText(f"{current_num} / {total}")

    def check_unnamed_bboxes(self):
        """Проверить наличие неназванных bboxes на текущем изображении."""
        if not hasattr(self, 'etalon_image_widget') or not self.etalon_image_widget.bounding_boxes:
            return []
        
        unnamed_bboxes = []
        for i, box in enumerate(self.etalon_image_widget.bounding_boxes):
            x1, y1, x2, y2, angle, selected, name = box
            if not name or not name.strip():
                unnamed_bboxes.append(i)
        
        return unnamed_bboxes
    
    def next_etalon_image(self):
        """Перейти к следующему эталонному изображению."""
        if not self.etalon_images:
            return
        
        # Проверяем наличие неназванных bboxes
        unnamed_bboxes = self.check_unnamed_bboxes()
        if unnamed_bboxes:
            # Показываем предупреждение
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Неназванные компоненты")
            msg_box.setText(
                f"На текущем изображении найдено {len(unnamed_bboxes)} неназванных компонентов.\n\n"
                "Что вы хотите сделать?"
            )
            btn_go_back = msg_box.addButton("Вернуться и задать имена", QMessageBox.ButtonRole.AcceptRole)
            btn_continue = msg_box.addButton("Продолжить без изменений", QMessageBox.ButtonRole.RejectRole)
            msg_box.setDefaultButton(btn_go_back)
            msg_box.exec()
            
            if msg_box.clickedButton() == btn_go_back:
                # Пользователь хочет вернуться и задать имена
                return
        
        # Save bboxes for current image before switching
        if hasattr(self, 'etalon_image_widget') and self.etalon_image_widget.bounding_boxes:
            self.save_current_etalon_bboxes()
        
        # Clear bboxes before switching
        if hasattr(self, 'etalon_image_widget'):
            self.etalon_image_widget.bounding_boxes = []
            self.etalon_image_widget.update()
        
        self.current_etalon_index = (self.current_etalon_index + 1) % len(self.etalon_images)
        self.display_current_etalon_image()

    def prev_etalon_image(self):
        """Перейти к предыдущему эталонному изображению."""
        if not self.etalon_images:
            return
        
        # Проверяем наличие неназванных bboxes
        unnamed_bboxes = self.check_unnamed_bboxes()
        if unnamed_bboxes:
            # Показываем предупреждение
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Неназванные компоненты")
            msg_box.setText(
                f"На текущем изображении найдено {len(unnamed_bboxes)} неназванных компонентов.\n\n"
                "Что вы хотите сделать?"
            )
            btn_go_back = msg_box.addButton("Вернуться и задать имена", QMessageBox.ButtonRole.AcceptRole)
            btn_continue = msg_box.addButton("Продолжить без изменений", QMessageBox.ButtonRole.RejectRole)
            msg_box.setDefaultButton(btn_go_back)
            msg_box.exec()
            
            if msg_box.clickedButton() == btn_go_back:
                # Пользователь хочет вернуться и задать имена
                return
        
        # Save bboxes for current image before switching
        if hasattr(self, 'etalon_image_widget') and self.etalon_image_widget.bounding_boxes:
            self.save_current_etalon_bboxes()
        
        # Clear bboxes before switching
        if hasattr(self, 'etalon_image_widget'):
            self.etalon_image_widget.bounding_boxes = []
            self.etalon_image_widget.update()
        
        self.current_etalon_index = (self.current_etalon_index - 1) % len(self.etalon_images)
        self.display_current_etalon_image()

    def clear_etalon_display(self):
        """Очистить отображение эталонного изображения."""
        if hasattr(self, 'etalon_image_widget'):
            self.etalon_image_widget.set_image(None)
            self.etalon_image_widget.bounding_boxes = []
            self.etalon_image_widget.update()
        self.ui.display_etalon_image_widget.setStyleSheet("background-color: black;")
        if hasattr(self, 'etalon_image_widget'):
            self.etalon_image_widget.move(0, 0)
            self.etalon_image_widget.resize(self.ui.display_etalon_image_widget.size())

    def open_mark_image_window(self):
        """Открыть новое окно для разметки изображения. DEPRECATED - markup is now done directly on preview."""
        # This method is kept for backward compatibility but is no longer used
        # Markup is now done directly on the preview
        pass
    
    def get_current_etalon_image_name(self):
        """Получить имя текущего эталонного изображения для сохранения bboxes."""
        if self.current_etalon_index < 0 or not self.etalon_images:
            return None
        if self.current_etalon_index < len(self.etalon_image_names):
            # Use the image name directly (e.g., "photo_0")
            return self.etalon_image_names[self.current_etalon_index]
        else:
            # Fallback на номер, если имя недоступно
            return f"image_{self.current_etalon_index}"
    
    def get_etalon_bboxes_file_path(self):
        """Получить путь к единому файлу для сохранения всех bboxes."""
        project_root = Path(__file__).parent.parent.parent
        markup_dir = project_root / "markup_info"
        markup_dir.mkdir(exist_ok=True)
        return markup_dir / "bboxes.json"
    
    def save_current_etalon_bboxes(self):
        """Сохранить bboxes текущего эталонного изображения в JSON файл."""
        if not hasattr(self, 'etalon_image_widget') or not self.etalon_images or self.current_etalon_index < 0:
            return
        
        try:
            bboxes_file = self.get_etalon_bboxes_file_path()
            bboxes = self.etalon_image_widget.bounding_boxes
            
            # Загружаем существующие данные, если файл есть
            all_bboxes_data = {}
            if bboxes_file.exists():
                try:
                    with open(bboxes_file, 'r', encoding='utf-8') as f:
                        all_bboxes_data = json.load(f)
                except:
                    all_bboxes_data = {}
            
            # Получаем имя текущего изображения
            image_name = self.get_current_etalon_image_name()
            if not image_name:
                return
            
            # Use current zoom scale for coordinate conversion
            scale = self.etalon_zoom_scale
            
            # Конвертируем текущие bboxes в список словарей для JSON
            # Конвертируем координаты из масштабированного пространства в оригинальное
            bboxes_data = []
            for box in bboxes:
                x1, y1, x2, y2, angle, selected, name = box
                # Конвертируем координаты обратно в оригинальный размер изображения
                orig_x1 = x1 / scale
                orig_y1 = y1 / scale
                orig_x2 = x2 / scale
                orig_y2 = y2 / scale
                bboxes_data.append({
                    'x1': float(orig_x1),
                    'y1': float(orig_y1),
                    'x2': float(orig_x2),
                    'y2': float(orig_y2),
                    'angle': float(angle),
                    'name': name if name else ""
                })
            
            # Обновляем данные для текущего изображения
            all_bboxes_data[image_name] = bboxes_data
            
            # Сохраняем все данные обратно в JSON
            with open(bboxes_file, 'w', encoding='utf-8') as f:
                json.dump(all_bboxes_data, f, indent=2, ensure_ascii=False)
            
            # Обновляем список компонентов после сохранения
            self.update_component_list()
        except Exception as e:
            print(f"Ошибка при сохранении bboxes: {str(e)}")
    
    def load_current_etalon_bboxes(self):
        """Загрузить bboxes из JSON файла для текущего эталонного изображения."""
        if not hasattr(self, 'etalon_image_widget') or not self.etalon_images or self.current_etalon_index < 0:
            return
        
        try:
            bboxes_file = self.get_etalon_bboxes_file_path()
            
            if not bboxes_file.exists():
                return  # Нет сохраненных bboxes
            
            # Загружаем из JSON
            with open(bboxes_file, 'r', encoding='utf-8') as f:
                all_bboxes_data = json.load(f)
            
            # Получаем имя текущего изображения
            image_name = self.get_current_etalon_image_name()
            if not image_name:
                return
            
            # Try current format first (image name only)
            bboxes_data = None
            if image_name in all_bboxes_data:
                bboxes_data = all_bboxes_data[image_name]
            else:
                # Fallback to old format (with index prefix) for backward compatibility
                if self.current_etalon_index < len(self.etalon_image_names):
                    old_name = f"{self.current_etalon_index}_{self.etalon_image_names[self.current_etalon_index]}"
                    if old_name in all_bboxes_data:
                        bboxes_data = all_bboxes_data[old_name]
            
            if not bboxes_data:
                return  # Нет bboxes для этого изображения
            
            # Use current zoom scale for coordinate conversion
            scale = self.etalon_zoom_scale
            
            # Конвертируем обратно в формат (x1, y1, x2, y2, angle, selected, name)
            # Конвертируем координаты из оригинального пространства в текущее масштабированное
            loaded_bboxes = []
            for bbox_data in bboxes_data:
                # Конвертируем координаты из оригинального размера в текущий масштаб
                scaled_x1 = bbox_data['x1'] * scale
                scaled_y1 = bbox_data['y1'] * scale
                scaled_x2 = bbox_data['x2'] * scale
                scaled_y2 = bbox_data['y2'] * scale
                loaded_bboxes.append((
                    scaled_x1,
                    scaled_y1,
                    scaled_x2,
                    scaled_y2,
                    bbox_data.get('angle', 0.0),
                    False,  # selected = False по умолчанию
                    bbox_data.get('name', '')
                ))
            
            # Устанавливаем загруженные bboxes
            self.etalon_image_widget.bounding_boxes = loaded_bboxes
            self.etalon_image_widget.update()  # Обновляем отображение
            
        except Exception as e:
            print(f"Ошибка при загрузке bboxes: {str(e)}")
    
    def update_component_list(self):
        """Обновить список компонентов в дереве, сгруппированный по именам изображений."""
        try:
            # Use tree view if available, otherwise fall back to table view
            tree_view = getattr(self, 'component_tree_view', None)
            table_view = getattr(self.ui, 'component_tableView', None)
            view = tree_view if tree_view else table_view
            
            if not view:
                return
            
            bboxes_file = self.get_etalon_bboxes_file_path()
            
            if not bboxes_file.exists():
                # Если файла нет, очищаем вид
                model = QStandardItemModel()
                model.setHorizontalHeaderLabels(["Component Name"])
                view.setModel(model)
                return
            
            # Загружаем все bboxes из JSON
            with open(bboxes_file, 'r', encoding='utf-8') as f:
                all_bboxes_data = json.load(f)
            
            # Получаем список загруженных изображений
            loaded_image_names = None
            if hasattr(self, 'etalon_image_names') and self.etalon_image_names:
                loaded_image_names = set(self.etalon_image_names)
            
            # Если нет загруженных изображений, показываем пустой список
            if loaded_image_names is None or len(loaded_image_names) == 0:
                model = QStandardItemModel()
                model.setHorizontalHeaderLabels(["Component Name"])
                view.setModel(model)
                return
            
            # Создаем модель для дерева
            model = QStandardItemModel()
            model.setHorizontalHeaderLabels(["Component Name"])
            
            # Группируем компоненты по именам изображений
            # Светло-красный цвет для неназванных компонентов
            light_red = QColor(255, 200, 200)  # Light red color
            light_red_brush = QBrush(light_red)
            
            # Зеленый цвет для выбранного компонента
            green = QColor(200, 255, 200)  # Light green color
            green_brush = QBrush(green)
            
            # Получаем информацию о выбранном bbox (если есть)
            selected_image_name = None
            selected_bbox_index = None
            if hasattr(self, 'etalon_image_widget') and hasattr(self.etalon_image_widget, 'selected_box_index'):
                if (self.etalon_image_widget.selected_box_index is not None and 
                    self.etalon_image_widget.selected_box_index < len(self.etalon_image_widget.bounding_boxes)):
                    selected_image_name = self.get_current_etalon_image_name()
                    selected_bbox_index = self.etalon_image_widget.selected_box_index
            
            # Фильтруем только изображения из загруженных
            for image_name in sorted(all_bboxes_data.keys()):
                # Пропускаем изображения, которые не загружены
                if image_name not in loaded_image_names:
                    continue
                bboxes_data = all_bboxes_data[image_name]
                
                # Создаем родительский элемент для изображения
                image_item = QStandardItem(image_name)
                image_item.setEditable(False)
                
                # Добавляем компоненты этого изображения как дочерние элементы
                has_components = False
                unnamed_counter = 1  # Счетчик для неназванных компонентов
                
                for bbox_index, bbox_data in enumerate(bboxes_data):
                    component_name = bbox_data.get('name', '').strip()
                    
                    # Проверяем, является ли этот компонент выбранным
                    is_selected = (image_name == selected_image_name and 
                                  bbox_index == selected_bbox_index)
                    
                    if component_name:
                        # Компонент с именем
                        has_components = True
                        component_item = QStandardItem(component_name)
                        component_item.setEditable(False)
                        # Применяем зеленый фон, если выбран
                        if is_selected:
                            component_item.setBackground(green_brush)
                        # Добавляем как дочерний элемент
                        image_item.appendRow(component_item)
                    else:
                        # Неназванный компонент - показываем как "UnnamedN"
                        has_components = True
                        unnamed_name = f"Unnamed{unnamed_counter}"
                        component_item = QStandardItem(unnamed_name)
                        component_item.setEditable(False)
                        # Применяем фон: зеленый если выбран, иначе светло-красный
                        if is_selected:
                            component_item.setBackground(green_brush)
                        else:
                            component_item.setBackground(light_red_brush)
                        # Добавляем как дочерний элемент
                        image_item.appendRow(component_item)
                        unnamed_counter += 1
                
                # Если есть компоненты, добавляем изображение в модель
                if has_components:
                    model.appendRow(image_item)
            
            # Устанавливаем модель в вид
            view.setModel(model)
            
            # Настраиваем дерево
            if tree_view:
                # Раскрываем все элементы по умолчанию
                view.expandAll()
                # Настраиваем ширину колонки
                view.setColumnWidth(0, 300)
            else:
                # Для таблицы настраиваем ширину колонок
                view.setColumnWidth(0, 200)
                view.setColumnWidth(1, 200)
            
        except Exception as e:
            print(f"Ошибка при обновлении списка компонентов: {str(e)}")
    
    def _rename_component_from_tree(self, item):
        """Переименовать компонент из дерева компонентов."""
        if not item or not item.parent():
            return
        
        # Получаем имя компонента и изображения
        component_name = item.text()
        image_item = item.parent()
        image_name = image_item.text()
        
        # Определяем, является ли это неназванным компонентом
        is_unnamed = component_name.startswith("Unnamed")
        
        # Получаем текущее имя (пустое для неназванных)
        current_name = "" if is_unnamed else component_name
        
        # Открываем диалог для ввода имени
        text, ok = QInputDialog.getText(
            self,
            "Имя компонента",
            f"Введите имя для компонента (изображение: {image_name}):",
            text=current_name
        )
        
        if ok and text and text.strip():
            new_name = text.strip()
            
            # Находим соответствующий bbox и обновляем его имя
            if hasattr(self, 'etalon_image_widget') and self.etalon_image_widget.bounding_boxes:
                # Получаем индекс компонента в списке
                bboxes = self.etalon_image_widget.bounding_boxes
                
                # Загружаем bboxes для этого изображения из файла
                bboxes_file = self.get_etalon_bboxes_file_path()
                if bboxes_file.exists():
                    with open(bboxes_file, 'r', encoding='utf-8') as f:
                        all_bboxes_data = json.load(f)
                    
                    if image_name in all_bboxes_data:
                        bboxes_data = all_bboxes_data[image_name]
                        
                        # Находим индекс компонента в списке
                        # Нужно найти правильный индекс, учитывая порядок в дереве
                        component_index = self._find_component_index_in_tree(item, image_item)
                        
                        if component_index is not None and component_index < len(bboxes_data):
                            # Обновляем имя в данных
                            bboxes_data[component_index]['name'] = new_name
                            
                            # Сохраняем обновленные данные
                            with open(bboxes_file, 'w', encoding='utf-8') as f:
                                json.dump(all_bboxes_data, f, indent=2, ensure_ascii=False)
                            
                            # Если это текущее изображение, обновляем bboxes в виджете
                            current_image_name = self.get_current_etalon_image_name()
                            if current_image_name == image_name:
                                # Перезагружаем bboxes для текущего изображения
                                self.load_current_etalon_bboxes()
                            
                            # Обновляем список компонентов
                            self.update_component_list()
                            
                            # Выделяем переименованный компонент в дереве
                            self._select_component_in_tree(image_name, new_name)
    
    def _delete_component_from_tree(self, item):
        """Удалить компонент из дерева компонентов."""
        if not item or not item.parent():
            return
        
        # Получаем имя компонента и изображения
        component_name = item.text()
        image_item = item.parent()
        image_name = image_item.text()
        
        # Проверяем, нужно ли показывать подтверждение
        if self.skip_delete_confirmation:
            # Пропускаем диалог, сразу удаляем
            pass
        else:
            # Подтверждение удаления
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Question)
            msg_box.setWindowTitle("Удаление компонента")
            msg_box.setText(f"Вы уверены, что хотите удалить компонент '{component_name}' из изображения '{image_name}'?")
            
            # Добавляем чекбокс "Больше не спрашивать"
            checkbox = QCheckBox("Больше не спрашивать")
            msg_box.setCheckBox(checkbox)
            
            btn_yes = msg_box.addButton("Да", QMessageBox.ButtonRole.AcceptRole)
            btn_no = msg_box.addButton("Нет", QMessageBox.ButtonRole.RejectRole)
            msg_box.setDefaultButton(btn_no)
            msg_box.exec()
            
            # Сохраняем настройку, если чекбокс отмечен
            if checkbox.isChecked():
                self.skip_delete_confirmation = True
            
            if msg_box.clickedButton() != btn_yes:
                return
        
        # Загружаем bboxes для этого изображения из файла
        bboxes_file = self.get_etalon_bboxes_file_path()
        if bboxes_file.exists():
            with open(bboxes_file, 'r', encoding='utf-8') as f:
                all_bboxes_data = json.load(f)
            
            if image_name in all_bboxes_data:
                bboxes_data = all_bboxes_data[image_name]
                
                # Находим индекс компонента в списке bboxes
                component_index = item.row()
                
                if component_index is not None and component_index < len(bboxes_data):
                    # Удаляем bbox из данных
                    del bboxes_data[component_index]
                    
                    # Если список пуст, удаляем изображение из данных
                    if not bboxes_data:
                        del all_bboxes_data[image_name]
                    
                    # Сохраняем обновленные данные
                    with open(bboxes_file, 'w', encoding='utf-8') as f:
                        json.dump(all_bboxes_data, f, indent=2, ensure_ascii=False)
                    
                    # Если это текущее изображение, обновляем bboxes в виджете
                    current_image_name = self.get_current_etalon_image_name()
                    if current_image_name == image_name:
                        # Перезагружаем bboxes для текущего изображения
                        self.load_current_etalon_bboxes()
                    
                    # Обновляем список компонентов
                    self.update_component_list()
    
    def _find_component_index_in_tree(self, component_item, image_item):
        """Найти индекс компонента в списке bboxes по его позиции в дереве."""
        # Получаем позицию компонента среди всех дочерних элементов изображения
        # Это соответствует порядку в bboxes_data, так как мы добавляем их в том же порядке
        row = component_item.row()
        return row
    
    def _select_component_in_tree(self, image_name, component_name):
        """Выделить компонент в дереве по имени изображения и компонента."""
        if not hasattr(self, 'component_tree_view'):
            return
        
        model = self.component_tree_view.model()
        if not model:
            return
        
        # Ищем изображение
        for i in range(model.rowCount()):
            image_item = model.item(i)
            if image_item and image_item.text() == image_name:
                # Ищем компонент в этом изображении
                for j in range(image_item.rowCount()):
                    component_item = image_item.child(j)
                    if component_item and component_item.text() == component_name:
                        # Выделяем компонент
                        index = model.indexFromItem(component_item)
                        self.component_tree_view.setCurrentIndex(index)
                        return
    
    def etalon_zoom_in(self):
        """Увеличить масштаб эталонного изображения."""
        if not hasattr(self, 'etalon_original_pixmap') or self.etalon_original_pixmap is None:
            return
        
        old_scale = self.etalon_zoom_scale
        self.etalon_zoom_scale = min(self.etalon_zoom_scale + self.etalon_zoom_step, self.etalon_max_zoom)
        if old_scale != self.etalon_zoom_scale:
            self._update_etalon_bboxes_scale(old_scale, self.etalon_zoom_scale)
            self._redisplay_etalon_with_zoom()
    
    def etalon_zoom_out(self):
        """Уменьшить масштаб эталонного изображения."""
        if not hasattr(self, 'etalon_original_pixmap') or self.etalon_original_pixmap is None:
            return
        
        old_scale = self.etalon_zoom_scale
        self.etalon_zoom_scale = max(self.etalon_zoom_scale - self.etalon_zoom_step, self.etalon_min_zoom)
        if old_scale != self.etalon_zoom_scale:
            self._update_etalon_bboxes_scale(old_scale, self.etalon_zoom_scale)
            self._redisplay_etalon_with_zoom()
    
    def _update_etalon_bboxes_scale(self, old_scale, new_scale):
        """Обновить координаты bboxes при изменении масштаба."""
        if old_scale == 0 or new_scale == 0:
            return
        scale_factor = new_scale / old_scale
        bboxes = self.etalon_image_widget.bounding_boxes
        updated_bboxes = []
        for box in bboxes:
            x1, y1, x2, y2, angle, selected, name = box
            updated_bboxes.append((
                x1 * scale_factor,
                y1 * scale_factor,
                x2 * scale_factor,
                y2 * scale_factor,
                angle,
                selected,
                name
            ))
        self.etalon_image_widget.bounding_boxes = updated_bboxes
        self.etalon_image_widget.update()
    
    def _redisplay_etalon_with_zoom(self):
        """Перерисовать эталонное изображение с текущим масштабом."""
        if not hasattr(self, 'etalon_original_pixmap') or self.etalon_original_pixmap is None:
            return
        
        pixmap = self.etalon_original_pixmap
        w = pixmap.width()
        h = pixmap.height()
        
        # Apply zoom scaling
        scaled_width = int(w * self.etalon_zoom_scale)
        scaled_height = int(h * self.etalon_zoom_scale)
        
        # Scale pixmap
        scaled_pixmap = pixmap.scaled(
            scaled_width,
            scaled_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Set the pixmap in the ImageDisplayWidget
        self.etalon_image_widget.set_image(scaled_pixmap)
        self.etalon_image_widget.update()

    # === Inspection handlers ===
    
    def load_control_photo(self):
        """Обработчик нажатия на кнопку 'Загрузить контрольное изображение'."""
        # Открываем диалог выбора папки
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку с изображениями",
            ""
        )
        
        if not folder_path:
            return
        
        try:
            # Загружаем изображения из папки
            if not self._load_control_images_from_folder(folder_path):
                return
            
            # Отображаем загруженные изображения
            self._display_control_images()
            
        except Exception as e:
            self.show_error(f"Ошибка при загрузке изображений: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _load_control_images_from_folder(self, folder_path: str) -> bool:
        """
        Загружает контрольные изображения из указанной папки и сохраняет их в self.images_data.
        
        Args:
            folder_path: Путь к папке с изображениями
        
        Returns:
            bool: True если загрузка прошла успешно, False в противном случае
        """
        try:
            # Получаем все изображения из папки
            image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif'}
            image_files = []
            
            for file_name in Path(folder_path).iterdir():
                if file_name.suffix.lower() in image_extensions:
                    image_files.append(file_name)
            
            if not image_files:
                self.show_error("В выбранной папке не найдено изображений")
                return False
            
            # Парсим имена файлов для извлечения координат
            # Формат: photo_X_Y.png, где X - столбец (горизонталь), Y - строка (вертикаль)
            self.images_data = []  # [(row, col, file_path, image), ...]
            
            for file_path in image_files:
                # Извлекаем имя файла без расширения
                stem = file_path.stem
                
                # Ищем паттерн _число_число в конце имени
                # Формат: photo_X_Y, где X - столбец, Y - строка
                match = re.search(r'_(\d+)_(\d+)$', stem)
                if match:
                    col = int(match.group(1))  # X - столбец (горизонталь)
                    row = int(match.group(2))   # Y - строка (вертикаль)
                    
                    # Загружаем изображение
                    image = cv2.imread(str(file_path))
                    if image is not None:
                        self.images_data.append((row, col, file_path, image))
                else:
                    # Если паттерн не найден, пропускаем файл
                    print(f"Предупреждение: не удалось определить координаты для файла {file_path.name}")
            
            if not self.images_data:
                self.show_error("Не удалось загрузить изображения или определить их координаты")
                return False
            
            # Сортируем по координатам (сначала по row, потом по col)
            self.images_data.sort(key=lambda x: (x[0], x[1]))
            
            # Применяем выравнивание SIFT к контрольным изображениям
            print("Применение выравнивания SIFT к контрольным изображениям...")
            self._align_control_images()
            
            return True
            
        except Exception as e:
            self.show_error(f"Ошибка при загрузке изображений: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def _display_control_images(self):
        """
        Отображает загруженные в self.images_data изображения в photo_display_widget.
        Если layout уже существует, обновляет существующие изображения.
        """
        if not self.images_data:
            return
        
        # Определяем размеры сетки
        max_row = max(img[0] for img in self.images_data)  # Максимальная строка (Y)
        max_col = max(img[1] for img in self.images_data)  # Максимальный столбец (X)
        
        photo_widget = self.ui.photo_display_widget
        old_layout = photo_widget.layout()
        
        # Если layout уже существует, пытаемся обновить существующие изображения
        if old_layout:
            # Пытаемся найти scroll_area в существующем layout
            scroll_area = None
            for i in range(old_layout.count()):
                item = old_layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    if isinstance(widget, QScrollArea):
                        scroll_area = widget
                        break
            
            if scroll_area:
                # Находим grid_layout внутри scroll_area
                scroll_widget = scroll_area.widget()
                if scroll_widget:
                    grid_layout = scroll_widget.layout()
                    if grid_layout:
                        # Обновляем существующие изображения
                        self._update_existing_images(grid_layout, max_row, max_col)
                        print(f"Обновлено {len(self.images_data)} изображений в сетке {max_row + 1}x{max_col + 1}")
                        return
        
        # Если layout не существует или не удалось обновить, создаем новый
        # Очищаем виджет и создаем новый layout
        # Удаляем старый layout, если он есть
        if old_layout:
            # Удаляем все виджеты из старого layout
            while old_layout.count():
                child = old_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            # Удаляем layout из виджета
            old_layout.setParent(None)
        
        # Создаем scroll area для прокрутки, если изображений много
        scroll_area = QScrollArea(photo_widget)
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        grid_layout_widget = QGridLayout(scroll_widget)
        grid_layout_widget.setSpacing(5)
        
        # Добавляем изображения в сетку
        # Нумерация: снизу вверх, слева направо
        # В QGridLayout строка 0 - это верх, поэтому инвертируем row
        for row, col, file_path, image in self.images_data:
            # Конвертируем BGR в RGB для Qt
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            
            # Масштабируем изображение для отображения в мозаике
            # Размер каждой ячейки примерно 200x200 пикселей
            cell_size = 200
            scaled_pixmap = pixmap.scaled(
                cell_size, cell_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Создаем QLabel для отображения изображения
            label = QLabel()
            label.setPixmap(scaled_pixmap)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("border: 1px solid gray;")
            
            # Добавляем в сетку: инвертируем row для отображения снизу вверх
            # row=0 (низ) должен быть в позиции max_row, row=max_row (верх) должен быть в позиции 0
            grid_row = max_row - row
            grid_layout_widget.addWidget(label, grid_row, col)
        
        scroll_area.setWidget(scroll_widget)
        
        # Создаем новый layout для photo_widget
        main_layout = QVBoxLayout(photo_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)
        photo_widget.setLayout(main_layout)
        
        print(f"Загружено {len(self.images_data)} изображений в сетку {max_row + 1}x{max_col + 1}")
    
    def _update_existing_images(self, grid_layout, max_row, max_col):
        """
        Обновляет существующие изображения в grid_layout без пересоздания виджетов.
        
        Args:
            grid_layout: QGridLayout с существующими QLabel
            max_row: Максимальная строка
            max_col: Максимальный столбец
        """
        # Создаем словарь для быстрого доступа к изображениям по координатам
        images_dict = {}
        for row, col, file_path, image in self.images_data:
            images_dict[(row, col)] = image
        
        # Проходим по всем позициям в grid_layout и обновляем изображения
        for row, col, file_path, image in self.images_data:
            grid_row = max_row - row
            
            # Находим существующий QLabel в этой позиции
            item = grid_layout.itemAtPosition(grid_row, col)
            if item and item.widget():
                label = item.widget()
                if isinstance(label, QLabel):
                    # Конвертируем BGR в RGB для Qt
                    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_image.shape
                    bytes_per_line = ch * w
                    qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qt_image)
                    
                    # Масштабируем изображение для отображения в мозаике
                    cell_size = 200
                    scaled_pixmap = pixmap.scaled(
                        cell_size, cell_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    
                    # Обновляем pixmap в существующем QLabel
                    label.setPixmap(scaled_pixmap)
    
    def _align_control_images(self):
        """
        Выравнивает контрольные изображения относительно эталонных с использованием SIFT.
        Обновляет self.images_data, заменяя исходные изображения на выровненные.
        """
        try:
            project_root = Path(__file__).parent.parent.parent
            
            # Загружаем файл маппинга
            mapping_file = project_root / "markup_info" / "etalon_mapping.json"
            if not mapping_file.exists():
                print(f"Предупреждение: файл маппинга не найден: {mapping_file}, выравнивание пропущено")
                return
            
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
            
            if 'mappings' not in mapping_data or not mapping_data['mappings']:
                print("Предупреждение: файл маппинга не содержит данных, выравнивание пропущено")
                return
            
            # Создаем выравниватель изображений
            image_aligner = SiftImageAligner(
                scale=0.25,
                nfeatures=0,
                contrast_threshold=0.06,
                edge_threshold=15,
                sigma=1.6,
                match_ratio=0.75,
                ransac_threshold=5.0
            )
            
            # Создаем словарь контрольных изображений для быстрого доступа
            control_images_dict = {}
            for row, col, file_path, image in self.images_data:
                control_images_dict[(col, row)] = (file_path, image)
            
            # Обрабатываем каждое правило маппинга
            for mapping in mapping_data['mappings']:
                etalon_indices = mapping.get('etalon_indices', [])
                control_indices_groups = mapping.get('control_indices', [])
                
                if not etalon_indices or not control_indices_groups:
                    continue
                
                # Ищем эталонные изображения в стандартных местах
                possible_etalon_paths = [
                    project_root / "data" / "plate_3" / "etalon_2" / "images",
                    project_root / "data" / "plate_3" / "etalon_2",
                    project_root / "data" / "plate_3" / "etalon" / "images",
                    project_root / "data" / "plate_3" / "etalon",
                ]
                
                etalon_images_folder = None
                for path in possible_etalon_paths:
                    if path.exists():
                        etalon_images_folder = path
                        break
                
                if etalon_images_folder is None:
                    print(f"Предупреждение: не найдена папка с эталонными изображениями")
                    continue
                
                # Загружаем эталонные изображения (только те, что указаны в etalon_indices)
                etalon_images_dict = {}
                for img_file in etalon_images_folder.iterdir():
                    if img_file.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                        match = re.search(r'_(\d+)_(\d+)', img_file.stem)
                        if match:
                            col = int(match.group(1))
                            row = int(match.group(2))
                            if [col, row] in etalon_indices:
                                etalon_img = cv2.imread(str(img_file))
                                if etalon_img is not None:
                                    etalon_images_dict[(col, row)] = etalon_img
                
                if not etalon_images_dict:
                    print(f"Предупреждение: не найдено эталонных изображений для указанных индексов")
                    continue
                
                # Обрабатываем каждую группу контрольных индексов
                for control_indices_group in control_indices_groups:
                    # Создаем сопоставление: эталонный индекс -> контрольный индекс
                    if len(etalon_indices) != len(control_indices_group):
                        continue
                    
                    # Создаем словарь сопоставления
                    index_mapping = {}
                    for i, etalon_idx in enumerate(etalon_indices):
                        if i < len(control_indices_group):
                            etalon_key = tuple(etalon_idx)
                            control_key = tuple(control_indices_group[i])
                            index_mapping[control_key] = etalon_key
                    
                    # Выравниваем контрольные изображения
                    for control_idx in control_indices_group:
                        col, row = control_idx
                        
                        # Проверяем наличие контрольного изображения
                        if (col, row) not in control_images_dict:
                            continue
                        
                        file_path, control_image = control_images_dict[(col, row)]
                        
                        # Находим соответствующий эталонный индекс
                        if (col, row) not in index_mapping:
                            continue
                        
                        etalon_col, etalon_row = index_mapping[(col, row)]
                        
                        # Проверяем наличие эталонного изображения
                        if (etalon_col, etalon_row) not in etalon_images_dict:
                            continue
                        
                        etalon_image = etalon_images_dict[(etalon_col, etalon_row)]
                        
                        # Выравниваем контрольное изображение относительно эталонного
                        print(f"Выравнивание контрольного изображения ({col}, {row}) относительно эталона ({etalon_col}, {etalon_row})...")
                        aligned_control_image = image_aligner.align(etalon_image, control_image)
                        
                        # Обновляем изображение в images_data
                        for i, (r, c, fp, img) in enumerate(self.images_data):
                            if r == row and c == col:
                                self.images_data[i] = (r, c, fp, aligned_control_image)
                                break
            
            print("Выравнивание контрольных изображений завершено")
            
        except Exception as e:
            print(f"Ошибка при выравнивании контрольных изображений: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def run_inspection(self):
        """Обработчик нажатия на кнопку 'Запустить инспекцию'."""
        if not self.images_data:
            self.show_error("Нет загруженных изображений. Сначала загрузите контрольные изображения.")
            return
        
        try:
            # Определяем путь к папке data (в корне проекта)
            project_root = Path(__file__).parent.parent.parent
            data_folder = project_root / "data"
            
            # Создаем папку data, если её нет
            data_folder.mkdir(exist_ok=True)
            
            # Загружаем файл маппинга
            mapping_file = project_root / "markup_info" / "etalon_mapping.json"
            if not mapping_file.exists():
                self.show_error(f"Файл маппинга не найден: {mapping_file}")
                return
            
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
            
            if 'mappings' not in mapping_data or not mapping_data['mappings']:
                self.show_error("Файл маппинга не содержит данных")
                return
            
            # Загружаем bboxes из файла разметки
            bboxes_file = project_root / "markup_info" / "bboxes.json"
            if not bboxes_file.exists():
                self.show_error(f"Файл bboxes не найден: {bboxes_file}")
                return
            
            with open(bboxes_file, 'r', encoding='utf-8') as f:
                bboxes_data = json.load(f)
            
            # Инициализируем компоненты сегментации
            # Определяем путь к модели
            model_path = project_root / "data" / "extended_many_augs.pth"
            segmenter = None
            postprocessor = None
            preprocessor = None
            
            if model_path.exists():
                try:
                    segmenter = ComponentSegmenter(
                        model_path=str(model_path),
                        device='cuda',  # Можно изменить на 'cuda' если доступна GPU
                        input_size=(224, 224)
                    )
                    postprocessor = MaskPostprocessor(
                        threshold=0.5,
                        min_contour_area=100
                    )
                    preprocessor = ImagePreprocessor()
                    print("Компоненты сегментации инициализированы")
                except Exception as e:
                    print(f"Предупреждение: не удалось инициализировать сегментатор: {str(e)}")
            else:
                print(f"Предупреждение: модель сегментации не найдена: {model_path}")
            
            # Создаем словарь контрольных изображений для быстрого доступа
            # Изображения уже выровнены при загрузке
            control_images_dict = {}
            for row, col, file_path, image in self.images_data:
                control_images_dict[(col, row)] = image
            
            # Обрабатываем каждое правило маппинга
            saved_count = 0
            for mapping in mapping_data['mappings']:
                etalon_indices = mapping.get('etalon_indices', [])
                control_indices_groups = mapping.get('control_indices', [])
                
                if not etalon_indices or not control_indices_groups:
                    print(f"Предупреждение: пропущено правило маппинга - нет индексов")
                    continue
                
                # Ищем эталонные изображения в стандартных местах
                # Пробуем несколько возможных путей
                possible_etalon_paths = [
                    project_root / "data" / "plate_3" / "etalon_2" / "images",
                    project_root / "data" / "plate_3" / "etalon_2",
                    project_root / "data" / "plate_3" / "etalon" / "images",
                    project_root / "data" / "plate_3" / "etalon",
                ]
                
                etalon_images_folder = None
                for path in possible_etalon_paths:
                    if path.exists():
                        etalon_images_folder = path
                        break
                
                if etalon_images_folder is None:
                    print(f"Предупреждение: не найдена папка с эталонными изображениями, пропускаем правило")
                    continue
                
                # Загружаем эталонные изображения (только те, что указаны в etalon_indices)
                etalon_images_dict = {}
                for img_file in etalon_images_folder.iterdir():
                    if img_file.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                        # Парсим имя файла для получения индексов (photo_X_Y.png)
                        match = re.search(r'_(\d+)_(\d+)', img_file.stem)
                        if match:
                            col = int(match.group(1))
                            row = int(match.group(2))
                            # Загружаем только изображения из etalon_indices
                            if [col, row] in etalon_indices:
                                etalon_img = cv2.imread(str(img_file))
                                if etalon_img is not None:
                                    etalon_images_dict[(col, row)] = etalon_img
                
                if not etalon_images_dict:
                    print(f"Предупреждение: не найдено эталонных изображений для указанных индексов")
                    continue
                
                # Обрабатываем каждую группу контрольных индексов
                for control_indices_group in control_indices_groups:
                    # Создаем сопоставление: эталонный индекс -> контрольный индекс
                    if len(etalon_indices) != len(control_indices_group):
                        print(f"Предупреждение: количество эталонных индексов ({len(etalon_indices)}) не совпадает с количеством контрольных ({len(control_indices_group)})")
                        continue
                    
                    # Создаем словарь сопоставления
                    index_mapping = {}
                    for i, etalon_idx in enumerate(etalon_indices):
                        if i < len(control_indices_group):
                            etalon_key = tuple(etalon_idx)
                            control_key = tuple(control_indices_group[i])
                            index_mapping[control_key] = etalon_key
                    
                    # Итерируемся по контрольным изображениям из этой группы и создаем коллажи
                    for control_idx in control_indices_group:
                        col, row = control_idx
                        
                        # Проверяем наличие контрольного изображения
                        if (col, row) not in control_images_dict:
                            print(f"Предупреждение: контрольное изображение для ({col}, {row}) не найдено")
                            continue
                        
                        control_image = control_images_dict[(col, row)]
                        
                        # Находим соответствующий эталонный индекс
                        if (col, row) not in index_mapping:
                            print(f"Предупреждение: нет сопоставления для контрольного изображения ({col}, {row})")
                            continue
                        
                        etalon_col, etalon_row = index_mapping[(col, row)]
                        
                        # Проверяем наличие эталонного изображения
                        if (etalon_col, etalon_row) not in etalon_images_dict:
                            print(f"Предупреждение: эталонное изображение для ({etalon_col}, {etalon_row}) не найдено")
                            continue
                        
                        etalon_image = etalon_images_dict[(etalon_col, etalon_row)]
                        
                        # Контрольное изображение уже выровнено при загрузке, используем его напрямую
                        # Формируем ключ для поиска bboxes (используем эталонный индекс)
                        photo_key = f"photo_{etalon_col}_{etalon_row}"
                        
                        # Получаем bboxes для эталонного изображения
                        if photo_key not in bboxes_data:
                            print(f"Предупреждение: bboxes для {photo_key} не найдены")
                            continue
                        
                        bboxes = bboxes_data[photo_key]
                        
                        if not bboxes:
                            print(f"Предупреждение: нет bboxes для {photo_key}")
                            continue
                        
                        # Извлекаем кропы компонентов и добавляем их в поле класса
                        for idx, bbox in enumerate(bboxes):
                            component_name = bbox.get('name', f'Component_{idx+1}')
                            
                            # Извлекаем кропы компонента (контрольное изображение уже выровнено)
                            etalon_crop, control_crop = get_component_crop(etalon_image, control_image, bbox)
                            
                            if etalon_crop is None or control_crop is None:
                                print(f"Предупреждение: пустой кроп для компонента {component_name} в {photo_key}")
                                continue
                            
                            # Добавляем информацию о кропе в поле класса
                            self.component_crops.append({
                                'etalon_crop': etalon_crop.copy(),
                                'control_crop': control_crop.copy(),
                                'photo_key': photo_key,
                                'component_name': component_name,
                                'component_id': idx,
                                'col': col,
                                'row': row,
                                'etalon_col': etalon_col,
                                'etalon_row': etalon_row,
                                'bbox': dict(bbox)  # Сохраняем исходный bbox (копируем словарь)
                            })
                        
                        # Создаем коллаж с кропами компонентов (контрольное изображение уже выровнено)
                        saved_count += save_component_crops(
                            etalon_image, control_image, bboxes, col, row, 
                            data_folder, photo_key
                        )
            
            # Выполняем сегментацию компонентов из списка component_crops
            if self.component_crops and segmenter is not None and postprocessor is not None and preprocessor is not None:
                print(f"\nНачинаем сегментацию {len(self.component_crops)} компонентов...")
                for crop_data in self.component_crops:
                    try:
                        etalon_crop = crop_data['etalon_crop']
                        control_crop = crop_data['control_crop']
                        component_name = crop_data['component_name']
                        
                        # Препроцессинг: подготовка изображений для сегментации
                        etalon_gray, etalon_w, etalon_h = preprocessor.prepare_image_for_segmentation(etalon_crop)
                        control_gray, control_w, control_h = preprocessor.prepare_image_for_segmentation(control_crop)
                        
                        # Сегментация: предсказание масок
                        etalon_mask_pred = segmenter.predict_mask(etalon_gray, (etalon_w, etalon_h))
                        control_mask_pred = segmenter.predict_mask(control_gray, (control_w, control_h))
                        
                        # Постпроцессинг: обработка масок
                        etalon_mask_cleaned, etalon_contours = postprocessor.process_mask(etalon_mask_pred)
                        control_mask_cleaned, control_contours = postprocessor.process_mask(control_mask_pred)
                        
                        # Вычисление метрик
                        iou = calculate_iou(etalon_mask_cleaned, control_mask_cleaned)
                        
                        # Вычисление углов
                        etalon_angle = 0.0
                        control_angle = 0.0
                        
                        if etalon_contours:
                            etalon_angle = get_bottom_edge_angle(etalon_contours[0])
                        
                        if control_contours:
                            control_angle = get_bottom_edge_angle(control_contours[0])
                        
                        # Вычисляем разницу углов
                        angle_diff = abs(etalon_angle - control_angle)
                        
                        # Добавляем метрики в словарь
                        crop_data['iou'] = iou
                        crop_data['angle'] = angle_diff
                        crop_data['etalon_angle'] = etalon_angle
                        crop_data['control_angle'] = control_angle
                        
                        print(f"  {component_name} ({crop_data['photo_key']}): IoU={iou:.3f}, угол={angle_diff:.2f}°")
                        
                    except Exception as e:
                        print(f"Ошибка при сегментации компонента {crop_data.get('component_name', 'unknown')}: {str(e)}")
                        # Добавляем значения по умолчанию при ошибке
                        crop_data['iou'] = 0.0
                        crop_data['angle'] = 0.0
                        crop_data['etalon_angle'] = 0.0
                        crop_data['control_angle'] = 0.0
                print("Сегментация завершена")
            elif self.component_crops:
                print("Предупреждение: сегментация не выполнена - компоненты сегментации не инициализированы")
                # Добавляем значения по умолчанию
                for crop_data in self.component_crops:
                    crop_data['iou'] = 0.0
                    crop_data['angle'] = 0.0
                    crop_data['etalon_angle'] = 0.0
                    crop_data['control_angle'] = 0.0
            
            if saved_count > 0:
                print(f"Успешно сохранено {saved_count} коллажей в папку {data_folder}")
                QMessageBox.information(
                    self,
                    "Инспекция завершена",
                    f"Сохранено {saved_count} коллажей в папку data"
                )
            else:
                self.show_error("Не удалось сохранить ни одного коллажа")
            
            # Отображаем результаты инспекции с обведенными bbox-ами
            self.display_inspection_results()
                
        except Exception as e:
            self.show_error(f"Ошибка при создании коллажей: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def display_inspection_results(self):
        """
        Отображает результаты инспекции, обводя bbox-ы компонентов цветами:
        - Красный: iou < 0.5
        - Синий: angle > 5 или 0.5 < iou < 0.65
        """
        if not self.component_crops or not self.images_data:
            print("Предупреждение: нет данных для отображения результатов")
            return
        
        try:
            # Создаем словарь для быстрого доступа к изображениям по координатам
            images_dict = {}
            for row, col, file_path, image in self.images_data:
                images_dict[(col, row)] = image
            
            # Проходим по всем компонентам и рисуем bbox-ы
            for crop_data in self.component_crops:
                col = crop_data.get('col')
                row = crop_data.get('row')
                bbox = crop_data.get('bbox')
                iou = crop_data.get('iou', 0.0)
                angle = crop_data.get('angle', 0.0)  # angle_diff
                
                # Проверяем наличие необходимых данных
                if col is None or row is None or bbox is None:
                    continue
                
                # Проверяем наличие изображения
                if (col, row) not in images_dict:
                    continue
                
                image = images_dict[(col, row)]
                
                # Определяем цвет bbox
                color = None
                if iou < 0.5:
                    # Красный цвет для iou < 0.5
                    color = (0, 0, 255)  # BGR формат для OpenCV
                elif angle > 5 or (0.5 < iou < 0.65):
                    # Синий цвет для angle > 5 или 0.5 < iou < 0.65
                    color = (255, 0, 0)  # BGR формат для OpenCV
                
                # Если цвет определен, рисуем bbox
                if color is not None:
                    x1 = int(bbox.get('x1', 0))
                    y1 = int(bbox.get('y1', 0))
                    x2 = int(bbox.get('x2', 0))
                    y2 = int(bbox.get('y2', 0))
                    
                    # Проверяем границы изображения
                    h, w = image.shape[:2]
                    x1 = max(0, min(x1, w - 1))
                    y1 = max(0, min(y1, h - 1))
                    x2 = max(x1 + 1, min(x2, w))
                    y2 = max(y1 + 1, min(y2, h))
                    
                    # Рисуем прямоугольник
                    thickness = 36
                    cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)
                    
                    # Опционально: добавляем текст с метриками
                    component_name = crop_data.get('component_name', '')
                    label = f"{component_name}: IoU={iou:.2f}, Ang={angle:.1f}°"
                    
                    # Позиция текста (над прямоугольником)
                    text_y = max(y1 - 10, 20)
                    text_x = x1
                    
                    # Рисуем текст с фоном для лучшей читаемости
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.6
                    text_thickness = 1
                    
                    # Получаем размер текста
                    (text_width, text_height), baseline = cv2.getTextSize(
                        label, font, font_scale, text_thickness
                    )
                    
                    # Рисуем фон для текста
                    cv2.rectangle(
                        image,
                        (text_x, text_y - text_height - baseline - 5),
                        (text_x + text_width, text_y + baseline),
                        (0, 0, 0),  # Черный фон
                        -1
                    )
                    
                    # Рисуем текст
                    cv2.putText(
                        image,
                        label,
                        (text_x, text_y),
                        font,
                        font_scale,
                        color,
                        text_thickness,
                        cv2.LINE_AA
                    )
            
            # Обновляем отображение изображений
            self._display_control_images()
            
            print(f"Отображены результаты инспекции для {len(self.component_crops)} компонентов")
            
        except Exception as e:
            print(f"Ошибка при отображении результатов инспекции: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # === Camera and CNC logic (unchanged) ===

    def clear_image_display(self):
        self.image_label.clear()
        self.ui.image_displayer.setStyleSheet("background-color: black;")
        self.image_label.move(0, 0)
        self.image_label.resize(self.ui.image_displayer.size())

    def toggle_camera(self):
        if self.cam is None:
            port_text = self.ui.camera_port_lineEdit.text()
            try:
                port = int(port_text) if port_text.isdigit() else port_text
                self.cam = ThreadSafeCameraReader(camera_id=port)
                self.timer.start(200)
                self.ui.connect_camera_button.setText("Отключить камеру")
            except Exception as e:
                self.show_error(f"Ошибка при открытии камеры: {str(e)}")
                self.cam = None
                self.clear_image_display()
        else:
            self.timer.stop()
            try:
                self.cam.stop()
            except Exception:
                pass
            self.cam = None
            self.ui.connect_camera_button.setText("Подключить")
            self.clear_image_display()

    def update_frame(self):
        if not self.cam:
            return
        try:
            frame = self.cam.get_image()
        except Exception as e:
            self.timer.stop()
            self.show_error(f"Ошибка чтения кадра с камеры: {str(e)}")
            self.clear_image_display()
            return
        if frame is None or getattr(frame, "size", 0) == 0:
            self.clear_image_display()
            return
        try:
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                self.ui.image_displayer.width(),
                self.ui.image_displayer.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.resize(self.ui.image_displayer.size())
            self.ui.image_displayer.setStyleSheet("")
        except Exception as e:
            self.timer.stop()
            self.show_error(f"Ошибка при отображении кадра: {str(e)}")
            self.clear_image_display()

    def resizeEvent(self, event):
        """Обработка изменения размера главного окна."""
        if self.image_label is not None:
            self.image_label.resize(self.ui.image_displayer.size())
        if hasattr(self, 'etalon_image_widget') and self.etalon_image_widget is not None:
            self.etalon_image_widget.resize(self.ui.display_etalon_image_widget.size())
            # Перерисовываем изображение при изменении размера
            if self.etalon_images and self.current_etalon_index >= 0:
                self.display_current_etalon_image()
        super().resizeEvent(event)

    def move_axis(self, axis, steps):
        if self.driver:
            print(f"Moving {axis} by {steps} mm")
            if axis == 'X':
                current = float(self.ui.cur_x_label.text() or "0")
                if current + steps <= 0:
                    self.driver.move_x_rel(int(steps))
                    self.ui.cur_x_label.setText(str(round(current + steps, 2)))
                else:
                    self.ui.cur_x_label.setText("0.0")
                    self.driver.move_x(0)
                    print('Out of range axis X')
            elif axis == 'Y':
                self.driver.move_y_rel(int(steps))
                current = float(self.ui.cur_y_label.text() or "0")
                self.ui.cur_y_label.setText(str(round(current + steps, 2)))
        else:
            print('ERROR! Connect to CNC')

    def zero_axis(self, axis):
        if self.driver:
            if axis == 'X':
                self.ui.cur_x_label.setText("0.0")
                self.driver.move_x(0)
            elif axis == 'Y':
                self.ui.cur_y_label.setText("0.0")
                self.driver.move_y(0)
            print(f"Zeroing {axis} axis")
        else:
            print('ERROR! Connect to CNC')

    def zero_all(self):
        if self.driver:
            self.driver.move_x(0)
            self.driver.move_y(0)
            self.ui.cur_x_label.setText("0.0")
            self.ui.cur_y_label.setText("0.0")
            print("Zeroing all axes")
        else:
            print('ERROR! Connect to CNC')

    def toggle_cnc_connection(self):
        if not self.cnc_connected:
            port = self.ui.port_lineEdit.text()
            try:
                self.driver = CncMachineDriver(port, baud_rate=115200, timeout=2)
                self.driver.open_serial_port()
                self.driver.unlock()
                self.driver.set_units_and_mode()
                self.cnc_connected = True
                self.ui.connect_cnc_button.setText("Отключить CNC")
                print(f"Подключено к CNC на {port}")
            except Exception as e:
                self.show_error(f"Не удалось подключиться к CNC: {str(e)}")
        else:
            self.ui.cur_x_label.setText("0.0")
            self.ui.cur_y_label.setText("0.0")
            if self.driver:
                self.driver.move_x(0)
                self.driver.move_y(0)
            self.cnc_connected = False
            self.ui.connect_cnc_button.setText("Подключить")
            if self.driver:
                self.driver.close_serial_port()
            self.driver = None
            print("CNC отключён")

    def show_error(self, message):
        print("ERROR:", message)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Ошибка", message)

    def closeEvent(self, event):
        if self.cam:
            self.cam.stop()
        if self.driver:
            self.driver.move_x(0)
            self.driver.move_y(0)
            self.driver.close_serial_port()
        event.accept()


class ImageDisplayWidget(QWidget):
    """Виджет для отображения изображения с возможностью разметки."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Enable keyboard focus
        self.original_image = None
        self.display_pixmap = None
        self.bounding_boxes = []  # Список bounding boxes: [x1, y1, x2, y2, angle, selected, name]
        self.current_box_start = None  # Начальная точка текущего бокса
        self.drawing_box = False
        self.selected_box_index = None
        self.rotation_mode = False
        self.rotation_start_angle = 0
        self.image_offset = QPoint(0, 0)
        self.pan_offset = QPoint(0, 0)  # Смещение для панорамирования
        self.last_mouse_pos = QPoint(0, 0)
        self.dragging_box = False
        self.panning = False  # Флаг панорамирования мышью
        self.pan_start_pos = QPoint(0, 0)  # Начальная позиция мыши при панорамировании
        self.drag_type = None  # 'corner', 'edge', 'move', or None
        self.drag_corner_index = None  # 0-3 for corners
        self.drag_start_pos = None
        self.drag_start_box = None  # Original box coordinates when drag started
        self.rotation_base_angle = 0.0
        self.rotation_start_pointer_angle = 0.0
        self.double_click_panning = False  # Флаг панорамирования после двойного клика
        
    def set_image(self, pixmap):
        """Установить изображение для отображения."""
        self.original_image = pixmap
        self.display_pixmap = pixmap
        self.update()
    
    def is_image_upscaled(self):
        """Проверить, увеличено ли изображение (больше размера виджета)."""
        if not self.display_pixmap:
            return False
        pixmap_size = self.display_pixmap.size()
        widget_size = self.size()
        return pixmap_size.width() > widget_size.width() or pixmap_size.height() > widget_size.height()
    
    def get_box_corners(self, box):
        """Получить координаты углов бокса с учетом поворота."""
        x1, y1, x2, y2, angle, _, _ = box
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        
        # Углы без поворота
        corners = [
            (x1, y1),  # top-left
            (x2, y1),  # top-right
            (x2, y2),  # bottom-right
            (x1, y2)   # bottom-left
        ]
        
        # Применяем поворот
        angle_rad = math.radians(angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        rotated_corners = []
        for cx, cy in corners:
            # Переводим в систему координат с центром в центре бокса
            dx = cx - center_x
            dy = cy - center_y
            # Поворачиваем
            rx = dx * cos_a - dy * sin_a
            ry = dx * sin_a + dy * cos_a
            # Возвращаем в исходную систему координат
            rotated_corners.append((rx + center_x, ry + center_y))
        
        return rotated_corners
    
    def get_rotation_handle(self, box, offset=20):
        """Возвращает точку для ручки вращения (над верхним ребром)."""
        corners = self.get_box_corners(box)
        top_mid_x = (corners[0][0] + corners[1][0]) / 2
        top_mid_y = (corners[0][1] + corners[1][1]) / 2
        # Направление внешней нормали к верхнему ребру
        edge_vec_x = corners[1][0] - corners[0][0]
        edge_vec_y = corners[1][1] - corners[0][1]
        edge_len = math.sqrt(edge_vec_x ** 2 + edge_vec_y ** 2) or 1.0
        normal_x = -edge_vec_y / edge_len
        normal_y = edge_vec_x / edge_len
        handle_x = top_mid_x + normal_x * offset
        handle_y = top_mid_y + normal_y * offset
        return QPoint(int(handle_x), int(handle_y))
    
    def detect_box_interaction(self, pos, box):
        """Определить тип взаимодействия с боксом: угол, край, центр или ручка вращения."""
        x1, y1, x2, y2, angle, _, _ = box
        corners = self.get_box_corners(box)
        
        # Проверяем попадание в углы (радиус 10 пикселей)
        corner_radius = 10
        for i, (cx, cy) in enumerate(corners):
            dist = math.sqrt((pos.x() - cx)**2 + (pos.y() - cy)**2)
            if dist < corner_radius:
                return 'corner', i
        
        # Проверяем попадание на края
        edge_threshold = 5
        for i in range(4):
            p1 = corners[i]
            p2 = corners[(i + 1) % 4]
            
            # Расстояние от точки до отрезка
            A = pos.x() - p1[0]
            B = pos.y() - p1[1]
            C = p2[0] - p1[0]
            D = p2[1] - p1[1]
            
            dot = A * C + B * D
            len_sq = C * C + D * D
            if len_sq > 0:
                param = dot / len_sq
                
                if 0 <= param <= 1:
                    xx = p1[0] + param * C
                    yy = p1[1] + param * D
                    dist = math.sqrt((pos.x() - xx)**2 + (pos.y() - yy)**2)
                    if dist < edge_threshold:
                        return 'edge', i
        
        # Проверяем попадание в центр (простая проверка прямоугольника)
        if min(x1, x2) <= pos.x() <= max(x1, x2) and min(y1, y2) <= pos.y() <= max(y1, y2):
            return 'move', None
        
        return None, None
    
    def constrain_pan_offset(self):
        """Ограничить pan_offset так, чтобы изображение не выходило за границы виджета."""
        if not self.display_pixmap:
            self.pan_offset = QPoint(0, 0)
            return
        
        pixmap_rect = self.display_pixmap.rect()
        widget_rect = self.rect()
        
        # Если изображение меньше виджета, сбрасываем pan_offset
        if pixmap_rect.width() <= widget_rect.width() and pixmap_rect.height() <= widget_rect.height():
            self.pan_offset = QPoint(0, 0)
            return
        
        # Базовое смещение (центрирование)
        base_x = (widget_rect.width() - pixmap_rect.width()) // 2
        base_y = (widget_rect.height() - pixmap_rect.height()) // 2
        
        # Ограничиваем по горизонтали
        if pixmap_rect.width() > widget_rect.width():
            # Финальная позиция: x = base_x + pan_offset.x()
            # Ограничения: 0 <= x <= widget_width - pixmap_width
            # Отсюда: -base_x <= pan_offset.x() <= widget_width - pixmap_width - base_x
            # Когда base_x отрицательный (изображение больше виджета):
            # -base_x положительный (показывает левый край)
            # widget_width - pixmap_width - base_x отрицательный (показывает правый край)
            min_x = widget_rect.width() - pixmap_rect.width() - base_x  # Минимальное значение (показывает правый край)
            max_x = -base_x  # Максимальное значение (показывает левый край)
            self.pan_offset.setX(max(min_x, min(self.pan_offset.x(), max_x)))
        else:
            # Изображение меньше виджета по ширине - не позволяем панорамирование
            self.pan_offset.setX(0)
        
        # Ограничиваем по вертикали
        if pixmap_rect.height() > widget_rect.height():
            # Финальная позиция: y = base_y + pan_offset.y()
            # Ограничения: 0 <= y <= widget_height - pixmap_height
            # Отсюда: -base_y <= pan_offset.y() <= widget_height - pixmap_height - base_y
            # Когда base_y отрицательный (изображение больше виджета):
            # -base_y положительный (показывает верхний край)
            # widget_height - pixmap_height - base_y отрицательный (показывает нижний край)
            min_y = widget_rect.height() - pixmap_rect.height() - base_y  # Минимальное значение (показывает нижний край)
            max_y = -base_y  # Максимальное значение (показывает верхний край)
            self.pan_offset.setY(max(min_y, min(self.pan_offset.y(), max_y)))
        else:
            # Изображение меньше виджета по высоте - не позволяем панорамирование
            self.pan_offset.setY(0)
    
    def paintEvent(self, event):
        """Отрисовка изображения и bounding boxes."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Рисуем изображение
        if self.display_pixmap:
            # Ограничиваем pan_offset перед отрисовкой
            self.constrain_pan_offset()
            
            # Центрируем изображение и применяем смещение панорамирования
            pixmap_rect = self.display_pixmap.rect()
            widget_rect = self.rect()
            # Если изображение меньше виджета, не применяем pan_offset (чтобы избежать пустых полей)
            if pixmap_rect.width() <= widget_rect.width() and pixmap_rect.height() <= widget_rect.height():
                # Изображение меньше виджета - центрируем без pan_offset
                x = (widget_rect.width() - pixmap_rect.width()) // 2
                y = (widget_rect.height() - pixmap_rect.height()) // 2
            else:
                # Изображение больше виджета - применяем pan_offset для панорамирования
                x = (widget_rect.width() - pixmap_rect.width()) // 2 + self.pan_offset.x()
                y = (widget_rect.height() - pixmap_rect.height()) // 2 + self.pan_offset.y()
            painter.drawPixmap(x, y, self.display_pixmap)
            self.image_offset = QPoint(x, y)
        else:
            self.image_offset = QPoint(0, 0)
        
        # Рисуем bounding boxes
        for i, box in enumerate(self.bounding_boxes):
            x1, y1, x2, y2, angle, selected, name = box
            is_selected = (i == self.selected_box_index)
            
            # Преобразуем координаты с учетом смещения изображения
            p1 = QPoint(int(x1) + self.image_offset.x(), int(y1) + self.image_offset.y())
            p2 = QPoint(int(x2) + self.image_offset.x(), int(y2) + self.image_offset.y())
            
            # Вычисляем центр и углы прямоугольника
            center_x = (p1.x() + p2.x()) / 2
            center_y = (p1.y() + p2.y()) / 2
            center = QPoint(int(center_x), int(center_y))
            
            width = abs(p2.x() - p1.x())
            height = abs(p2.y() - p1.y())
            
            # Создаем прямоугольник
            rect = QRectF(p1.x(), p1.y(), width, height)
            rect = rect.normalized()
            
            # Применяем поворот
            painter.save()
            painter.translate(center)
            painter.rotate(angle)
            painter.translate(-center)
            
            # Рисуем прямоугольник
            pen = QPen(QColor(0, 255, 0) if is_selected else QColor(255, 0, 0), 2)
            painter.setPen(pen)
            painter.drawRect(rect)
            
            # Рисуем углы
            corner_size = 8
            corners = [
                QRectF(rect.left() - corner_size/2, rect.top() - corner_size/2, corner_size, corner_size),
                QRectF(rect.right() - corner_size/2, rect.top() - corner_size/2, corner_size, corner_size),
                QRectF(rect.right() - corner_size/2, rect.bottom() - corner_size/2, corner_size, corner_size),
                QRectF(rect.left() - corner_size/2, rect.bottom() - corner_size/2, corner_size, corner_size)
            ]
            for corner in corners:
                painter.fillRect(corner, pen.color())
            
            painter.restore()
            
            # Рисуем имя бокса над верхним левым углом
            if name:
                painter.save()
                # Получаем координаты верхнего левого угла с учетом поворота
                corners = self.get_box_corners(box)
                top_left = corners[0]
                text_x = int(top_left[0]) + self.image_offset.x()
                text_y = int(top_left[1]) + self.image_offset.y() - 5
                
                # Рисуем фон для текста для лучшей читаемости
                font = QFont("Arial", 10)
                painter.setFont(font)
                font_metrics = painter.fontMetrics()
                text_rect = font_metrics.boundingRect(name)
                bg_rect = QRectF(text_x - 2, text_y - text_rect.height() - 2, 
                                 text_rect.width() + 4, text_rect.height() + 4)
                painter.fillRect(bg_rect, QColor(0, 0, 0, 180))  # Полупрозрачный черный фон
                
                # Рисуем текст
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(text_x, text_y, name)
                painter.restore()
        
        # Рисуем текущий бокс при создании (вне цикла, чтобы работало даже когда нет существующих боксов)
        if self.drawing_box and self.current_box_start:
            temp_rect = QRectF(
                min(self.current_box_start.x(), self.last_mouse_pos.x()) + self.image_offset.x(),
                min(self.current_box_start.y(), self.last_mouse_pos.y()) + self.image_offset.y(),
                abs(self.last_mouse_pos.x() - self.current_box_start.x()),
                abs(self.last_mouse_pos.y() - self.current_box_start.y())
            )
            pen = QPen(QColor(0, 255, 255), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(temp_rect)
    
    def mousePressEvent(self, event):
        """Обработка нажатия мыши."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Преобразуем координаты относительно изображения
            widget_pos = event.position().toPoint()
            pos = widget_pos - self.image_offset
            
            # Проверяем, что клик внутри изображения
            if not self.display_pixmap:
                return
            
            pixmap_rect = self.display_pixmap.rect()
            if not (0 <= pos.x() < pixmap_rect.width() and 0 <= pos.y() < pixmap_rect.height()):
                # Если клик вне изображения, но изображение увеличено, разрешаем панорамирование
                if self.is_image_upscaled():
                    self.panning = True
                    self.pan_start_pos = widget_pos
                    self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                return
            
            if self.rotation_mode and self.selected_box_index is not None:
                # Режим поворота
                box = self.bounding_boxes[self.selected_box_index]
                x1, y1, x2, y2, angle, _, _ = box
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                dx = pos.x() - center_x
                dy = pos.y() - center_y
                pointer_angle = math.degrees(math.atan2(dy, dx))
                self.rotation_base_angle = angle
                self.rotation_start_pointer_angle = pointer_angle
            else:
                # Проверяем, кликнули ли по существующему боксу
                clicked_box = None
                interaction_type = None
                interaction_index = None
                
                # Проверяем боксы в обратном порядке (сначала верхние)
                for i in range(len(self.bounding_boxes) - 1, -1, -1):
                    box = self.bounding_boxes[i]
                    interaction_type, interaction_index = self.detect_box_interaction(pos, box)
                    if interaction_type is not None:
                        clicked_box = i
                        break
                
                if clicked_box is not None:
                    self.selected_box_index = clicked_box
                    # Обновляем флаг выбранности
                    for i, box in enumerate(self.bounding_boxes):
                        x1, y1, x2, y2, angle, _, name = box
                        self.bounding_boxes[i] = (x1, y1, x2, y2, angle, i == clicked_box, name)
                    
                    # Обновляем список bboxes в окне разметки
                    if hasattr(self, 'marking_window') and self.marking_window:
                        self.marking_window.update_bbox_list()
                    
                    # Обновляем выделение в списке компонентов
                    if hasattr(self, 'main_window_ref') and self.main_window_ref:
                        self.main_window_ref.update_component_list()
                    
                    # Начинаем перетаскивание
                    self.dragging_box = True
                    self.drag_type = interaction_type
                    self.drag_corner_index = interaction_index
                    self.drag_start_pos = pos
                    self.drag_start_box = self.bounding_boxes[clicked_box]
                    self.update()
                else:
                    # Начинаем создание нового бокса (обычное поведение)
                    self.current_box_start = pos
                    self.last_mouse_pos = pos  # Initialize last_mouse_pos to current position
                    self.drawing_box = True
                    self.selected_box_index = None
                    self.dragging_box = False
                    # Обновляем выделение в списке компонентов (снимаем выделение)
                    if hasattr(self, 'main_window_ref') and self.main_window_ref:
                        self.main_window_ref.update_component_list()
                    self.update()  # Update to show the initial box (even if zero size)
        
        elif event.button() == Qt.MouseButton.RightButton:
            # Правый клик - режим поворота (если есть выбранный бокс) или панорамирование
            if self.selected_box_index is not None:
                self.rotation_mode = True
            else:
                # Если нет выбранного бокса, используем правый клик для панорамирования
                if not self.dragging_box and not self.drawing_box:
                    self.panning = True
                    self.pan_start_pos = event.position().toPoint()
                    self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        elif event.button() == Qt.MouseButton.MiddleButton:
            # Средняя кнопка мыши - начало панорамирования
            if not self.dragging_box and not self.drawing_box:
                self.panning = True
                self.pan_start_pos = event.position().toPoint()
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
    
    def mouseMoveEvent(self, event):
        """Обработка движения мыши."""
        widget_pos = event.position().toPoint()
        self.last_mouse_pos = widget_pos - self.image_offset
        
        # Обновляем курсор в зависимости от позиции
        if not self.dragging_box and not self.drawing_box and not self.rotation_mode:
            pos = widget_pos - self.image_offset
            cursor_set = False
            
            # Проверяем все боксы для определения типа курсора
            for i, box in enumerate(self.bounding_boxes):
                interaction_type, interaction_index = self.detect_box_interaction(pos, box)
                if interaction_type == 'corner':
                    self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
                    cursor_set = True
                    break
                elif interaction_type == 'edge':
                    # Определяем направление края для правильного курсора
                    # Вычисляем фактическое направление края (с учетом поворота)
                    corners = self.get_box_corners(box)
                    edge_idx = interaction_index
                    p1 = corners[edge_idx]
                    p2 = corners[(edge_idx + 1) % 4]
                    
                    # Вычисляем угол края
                    edge_dx = p2[0] - p1[0]
                    edge_dy = p2[1] - p1[1]
                    edge_angle = math.degrees(math.atan2(abs(edge_dy), abs(edge_dx)))
                    
                    # Если угол больше 45 градусов, край более вертикальный
                    # Если угол меньше 45 градусов, край более горизонтальный
                    if edge_angle > 45:
                        self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
                    else:
                        self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
                    cursor_set = True
                    break
                elif interaction_type == 'move':
                    self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
                    cursor_set = True
                    break
            
            if not cursor_set:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        
        if self.rotation_mode and self.selected_box_index is not None:
            # Поворот выбранного бокса
            box = self.bounding_boxes[self.selected_box_index]
            x1, y1, x2, y2, angle, _, name = box
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            dx = self.last_mouse_pos.x() - center_x
            dy = self.last_mouse_pos.y() - center_y
            pointer_angle = math.degrees(math.atan2(dy, dx))
            new_angle = self.rotation_base_angle + (pointer_angle - self.rotation_start_pointer_angle)
            self.bounding_boxes[self.selected_box_index] = (x1, y1, x2, y2, new_angle, True, name)
            self.update()
        elif self.dragging_box and self.selected_box_index is not None:
            # Перетаскивание бокса
            box = self.bounding_boxes[self.selected_box_index]
            x1, y1, x2, y2, angle, _, name = box
            dx = self.last_mouse_pos.x() - self.drag_start_pos.x()
            dy = self.last_mouse_pos.y() - self.drag_start_pos.y()
            
            if self.drag_type == 'move':
                # Перемещение всего бокса (сохраняя размер и угол)
                start_x1, start_y1, start_x2, start_y2, start_angle, _, start_name = self.drag_start_box
                width = start_x2 - start_x1
                height = start_y2 - start_y1
                new_x1 = start_x1 + dx
                new_y1 = start_y1 + dy
                new_x2 = new_x1 + width
                new_y2 = new_y1 + height
                self.bounding_boxes[self.selected_box_index] = (new_x1, new_y1, new_x2, new_y2, angle, True, name)
            elif self.drag_type == 'corner':
                # Изменение размера через угол
                corners = self.get_box_corners(self.drag_start_box)
                corner = corners[self.drag_corner_index]
                
                # Новые координаты угла
                new_corner_x = corner[0] + dx
                new_corner_y = corner[1] + dy
                
                # Находим противоположный угол
                opposite_index = (self.drag_corner_index + 2) % 4
                opposite_corner = corners[opposite_index]
                
                # Обновляем координаты бокса
                new_x1 = min(new_corner_x, opposite_corner[0])
                new_y1 = min(new_corner_y, opposite_corner[1])
                new_x2 = max(new_corner_x, opposite_corner[0])
                new_y2 = max(new_corner_y, opposite_corner[1])
                
                self.bounding_boxes[self.selected_box_index] = (new_x1, new_y1, new_x2, new_y2, angle, True, name)
            elif self.drag_type == 'edge':
                # Изменение размера через край
                edge = self.drag_corner_index
                
                # Работаем в системе координат бокса (до поворота)
                orig_x1, orig_y1, orig_x2, orig_y2, orig_angle, _, orig_name = self.drag_start_box
                center_x = (orig_x1 + orig_x2) / 2
                center_y = (orig_y1 + orig_y2) / 2
                width = abs(orig_x2 - orig_x1)
                height = abs(orig_y2 - orig_y1)
                
                # Преобразуем текущую позицию мыши в систему координат бокса
                # (поворачиваем обратно на -angle)
                angle_rad = -math.radians(angle)
                cos_a = math.cos(angle_rad)
                sin_a = math.sin(angle_rad)
                
                # Смещение мыши относительно центра
                rel_x = self.last_mouse_pos.x() - center_x
                rel_y = self.last_mouse_pos.y() - center_y
                
                # Поворачиваем в систему координат бокса
                rotated_dx = rel_x * cos_a - rel_y * sin_a
                rotated_dy = rel_x * sin_a + rel_y * cos_a
                
                # Начальное смещение в системе координат бокса
                start_rel_x = self.drag_start_pos.x() - center_x
                start_rel_y = self.drag_start_pos.y() - center_y
                start_rotated_dx = start_rel_x * cos_a - start_rel_y * sin_a
                start_rotated_dy = start_rel_x * sin_a + start_rel_y * cos_a
                
                # Изменение в системе координат бокса
                delta_rotated_x = rotated_dx - start_rotated_dx
                delta_rotated_y = rotated_dy - start_rotated_dy
                
                # Определяем, какой размер изменяется в зависимости от края
                # edge 0: верхний край (y1 изменяется)
                # edge 1: правый край (x2 изменяется)
                # edge 2: нижний край (y2 изменяется)
                # edge 3: левый край (x1 изменяется)
                
                new_x1, new_y1, new_x2, new_y2 = orig_x1, orig_y1, orig_x2, orig_y2
                
                if edge == 0:  # Верхний край - изменяем y1
                    new_y1 = orig_y1 + delta_rotated_y
                elif edge == 1:  # Правый край - изменяем x2
                    new_x2 = orig_x2 + delta_rotated_x
                elif edge == 2:  # Нижний край - изменяем y2
                    new_y2 = orig_y2 + delta_rotated_y
                elif edge == 3:  # Левый край - изменяем x1
                    new_x1 = orig_x1 + delta_rotated_x
                
                # Убеждаемся, что размеры не стали отрицательными
                if abs(new_x2 - new_x1) < 5:
                    if edge == 1:
                        new_x2 = new_x1 + 5
                    elif edge == 3:
                        new_x1 = new_x2 - 5
                
                if abs(new_y2 - new_y1) < 5:
                    if edge == 2:
                        new_y2 = new_y1 + 5
                    elif edge == 0:
                        new_y1 = new_y2 - 5
                
                self.bounding_boxes[self.selected_box_index] = (new_x1, new_y1, new_x2, new_y2, angle, True, name)
            
            self.update()
        elif self.drawing_box:
            self.update()
        elif self.double_click_panning:
            # Панорамирование после двойного клика
            current_pos = event.position().toPoint()
            dx = current_pos.x() - self.pan_start_pos.x()
            dy = current_pos.y() - self.pan_start_pos.y()
            self.pan_offset.setX(self.pan_offset.x() + dx)
            self.pan_offset.setY(self.pan_offset.y() + dy)
            # Ограничиваем pan_offset, чтобы изображение не выходило за границы
            self.constrain_pan_offset()
            self.pan_start_pos = current_pos
            self.update()
            # Обновляем scrollbars
            if hasattr(self, 'marking_window') and self.marking_window:
                self.marking_window.update_scrollbars()
        elif self.panning:
            # Панорамирование изображения
            current_pos = event.position().toPoint()
            dx = current_pos.x() - self.pan_start_pos.x()
            dy = current_pos.y() - self.pan_start_pos.y()
            self.pan_offset.setX(self.pan_offset.x() + dx)
            self.pan_offset.setY(self.pan_offset.y() + dy)
            # Ограничиваем pan_offset, чтобы изображение не выходило за границы
            self.constrain_pan_offset()
            self.pan_start_pos = current_pos
            self.update()
            # Обновляем scrollbars
            if hasattr(self, 'marking_window') and self.marking_window:
                self.marking_window.update_scrollbars()
    
    def mouseDoubleClickEvent(self, event):
        """Обработка двойного клика мыши для начала панорамирования."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Если изображение увеличено, начинаем панорамирование после двойного клика
            if self.is_image_upscaled():
                self.double_click_panning = True
                self.pan_start_pos = event.position().toPoint()
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
    
    def mouseReleaseEvent(self, event):
        """Обработка отпускания мыши."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Завершаем панорамирование после двойного клика
            if self.double_click_panning:
                self.double_click_panning = False
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                # Обновляем scrollbars
                if hasattr(self, 'marking_window') and self.marking_window:
                    self.marking_window.update_scrollbars()
            
            # Завершаем обычное панорамирование, если оно было начато
            if self.panning and not self.drawing_box and not self.dragging_box:
                self.panning = False
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                # Обновляем scrollbars
                if hasattr(self, 'marking_window') and self.marking_window:
                    self.marking_window.update_scrollbars()
            
            if self.drawing_box and self.current_box_start:
                # Завершаем создание бокса
                widget_pos = event.position().toPoint()
                end_pos = widget_pos - self.image_offset
                x1, y1 = self.current_box_start.x(), self.current_box_start.y()
                x2, y2 = end_pos.x(), end_pos.y()
                
                # Проверяем, что бокс имеет ненулевой размер
                if abs(x2 - x1) > 5 and abs(y2 - y1) > 5:
                    # Добавляем новый бокс (начало, конец, угол=0, выбран, имя="")
                    self.bounding_boxes.append((x1, y1, x2, y2, 0.0, True, ""))
                    # Снимаем выделение с других боксов
                    for i in range(len(self.bounding_boxes) - 1):
                        box = self.bounding_boxes[i]
                        self.bounding_boxes[i] = (box[0], box[1], box[2], box[3], box[4], False, box[6])
                    self.selected_box_index = len(self.bounding_boxes) - 1
                    
                    # Обновляем список bboxes в окне разметки
                    if hasattr(self, 'marking_window') and self.marking_window:
                        self.marking_window.update_bbox_list()
                    
                    # Auto-save if used in preview (has main_window_ref)
                    if hasattr(self, 'main_window_ref') and self.main_window_ref:
                        self.main_window_ref.save_current_etalon_bboxes()
                    
                    # Автоматически показываем диалог для ввода имени нового бокса
                    self._show_name_dialog_for_selected_box()
                
                self.drawing_box = False
                self.current_box_start = None
                self.update()
            
            # Завершаем перетаскивание
            if self.dragging_box:
                self.dragging_box = False
                self.drag_type = None
                self.drag_corner_index = None
                self.drag_start_pos = None
                self.drag_start_box = None
            
            self.rotation_mode = False
        
        elif event.button() == Qt.MouseButton.RightButton:
            self.rotation_mode = False
            # Завершение панорамирования (если панорамирование было начато правым кликом)
            if self.panning:
                self.panning = False
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            if self.dragging_box:
                self.dragging_box = False
                self.drag_type = None
                self.drag_corner_index = None
                self.drag_start_pos = None
                self.drag_start_box = None
        
        elif event.button() == Qt.MouseButton.MiddleButton:
            # Завершение панорамирования
            if self.panning:
                self.panning = False
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        
        elif event.button() == Qt.MouseButton.MiddleButton:
            # Завершение панорамирования
            if self.panning:
                self.panning = False
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
    
    def _show_name_dialog_for_selected_box(self):
        """Показать диалог для ввода имени выбранного бокса."""
        if self.selected_box_index is not None and self.selected_box_index < len(self.bounding_boxes):
            box = self.bounding_boxes[self.selected_box_index]
            x1, y1, x2, y2, angle, selected, current_name = box
            
            # Открываем диалог для ввода имени
            text, ok = QInputDialog.getText(
                self,
                "Имя bounding box",
                "Введите имя для bounding box:",
                text=current_name if current_name else ""
            )
            
            if ok and text:
                # Обновляем имя бокса
                self.bounding_boxes[self.selected_box_index] = (x1, y1, x2, y2, angle, selected, text)
                self.update()
                # Обновляем список bboxes в окне разметки
                if hasattr(self, 'marking_window') and self.marking_window:
                    self.marking_window.update_bbox_list()
                # Auto-save if used in preview (has main_window_ref)
                if hasattr(self, 'main_window_ref') and self.main_window_ref:
                    self.main_window_ref.save_current_etalon_bboxes()
    
    def _confirm_delete_bbox(self):
        """Показать диалог подтверждения удаления бокса."""
        if self.selected_box_index is None or self.selected_box_index >= len(self.bounding_boxes):
            return False
        
        box = self.bounding_boxes[self.selected_box_index]
        x1, y1, x2, y2, angle, selected, name = box
        
        # Получаем главное окно для доступа к настройке
        main_window = None
        if hasattr(self, 'main_window_ref') and self.main_window_ref:
            main_window = self.main_window_ref
        else:
            parent = self.parent()
            while parent and not isinstance(parent, QMainWindow):
                parent = parent.parent()
            if isinstance(parent, QMainWindow):
                main_window = parent
        
        # Проверяем, нужно ли показывать подтверждение
        if main_window and hasattr(main_window, 'skip_delete_confirmation') and main_window.skip_delete_confirmation:
            # Пропускаем диалог, сразу подтверждаем удаление
            return True
        
        # Получаем родительское окно для показа диалога
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        
        if not parent:
            # Если не нашли главное окно, используем self
            parent = self
        
        # Показываем диалог подтверждения
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle("Удаление компонента")
        
        # Формируем текст сообщения
        component_name = name if name and name.strip() else "неназванный компонент"
        msg_box.setText(f"Вы уверены, что хотите удалить компонент '{component_name}'?")
        
        # Добавляем чекбокс "Больше не спрашивать"
        checkbox = QCheckBox("Больше не спрашивать")
        msg_box.setCheckBox(checkbox)
        
        btn_yes = msg_box.addButton("Да", QMessageBox.ButtonRole.AcceptRole)
        btn_no = msg_box.addButton("Нет", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(btn_no)
        msg_box.exec()
        
        # Сохраняем настройку, если чекбокс отмечен
        if checkbox.isChecked() and main_window:
            main_window.skip_delete_confirmation = True
        
        return msg_box.clickedButton() == btn_yes
    
    def keyPressEvent(self, event):
        """Обработка нажатия клавиш."""
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # Если нажат Enter и есть выбранный бокс, открываем диалог для ввода имени
            if self.selected_box_index is not None:
                self._show_name_dialog_for_selected_box()
        elif event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            # Если нажат Delete/Backspace и есть выбранный бокс, показываем подтверждение и удаляем его
            if self.selected_box_index is not None and self.selected_box_index < len(self.bounding_boxes):
                # Показываем диалог подтверждения
                if not self._confirm_delete_bbox():
                    return
                
                # Удаляем выбранный бокс
                del self.bounding_boxes[self.selected_box_index]
                # Сбрасываем выделение
                self.selected_box_index = None
                # Обновляем отображение
                self.update()
                # Обновляем список bboxes в окне разметки
                if hasattr(self, 'marking_window') and self.marking_window:
                    self.marking_window.update_bbox_list()
                # Auto-save if used in preview (has main_window_ref)
                if hasattr(self, 'main_window_ref') and self.main_window_ref:
                    self.main_window_ref.save_current_etalon_bboxes()
                    # Обновляем выделение в списке компонентов
                    self.main_window_ref.update_component_list()
        elif event.key() == Qt.Key.Key_Left:
            # Стрелка влево - панорамирование влево
            self.pan_offset.setX(self.pan_offset.x() + 20)
            self.update()
            # Обновляем scrollbars
            if hasattr(self, 'marking_window') and self.marking_window:
                self.marking_window.update_scrollbars()
        elif event.key() == Qt.Key.Key_Right:
            # Стрелка вправо - панорамирование вправо
            self.pan_offset.setX(self.pan_offset.x() - 20)
            self.update()
            # Обновляем scrollbars
            if hasattr(self, 'marking_window') and self.marking_window:
                self.marking_window.update_scrollbars()
        elif event.key() == Qt.Key.Key_Up:
            # Стрелка вверх - панорамирование вверх
            self.pan_offset.setY(self.pan_offset.y() + 20)
            self.update()
            # Обновляем scrollbars
            if hasattr(self, 'marking_window') and self.marking_window:
                self.marking_window.update_scrollbars()
        elif event.key() == Qt.Key.Key_Down:
            # Стрелка вниз - панорамирование вниз
            self.pan_offset.setY(self.pan_offset.y() - 20)
            self.update()
            # Обновляем scrollbars
            if hasattr(self, 'marking_window') and self.marking_window:
                self.marking_window.update_scrollbars()
        elif event.key() == Qt.Key.Key_Space:
            # Пробел - начало панорамирования мышью
            if not self.dragging_box and not self.drawing_box:
                self.panning = True
                self.pan_start_pos = self.mapFromGlobal(QCursor.pos())
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        else:
            super().keyPressEvent(event)
    
    def wheelEvent(self, event):
        """Обработка прокрутки колесика мыши для масштабирования с Ctrl или панорамирования без Ctrl."""
        # Проверяем, нажат ли Ctrl
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Получаем направление прокрутки
            delta = event.angleDelta().y()
            
            # Если есть ссылка на окно разметки, вызываем методы масштабирования
            if hasattr(self, 'marking_window') and self.marking_window:
                if delta > 0:
                    # Прокрутка вверх - увеличение
                    self.marking_window.zoom_in()
                elif delta < 0:
                    # Прокрутка вниз - уменьшение
                    self.marking_window.zoom_out()
                event.accept()
                return
            # Если используется в preview (has main_window_ref), вызываем методы масштабирования
            elif hasattr(self, 'main_window_ref') and self.main_window_ref:
                if delta > 0:
                    # Прокрутка вверх - увеличение
                    self.main_window_ref.etalon_zoom_in()
                elif delta < 0:
                    # Прокрутка вниз - уменьшение
                    self.main_window_ref.etalon_zoom_out()
                event.accept()
                return
        else:
            # Если Ctrl не нажат, используем прокрутку для панорамирования
            # Получаем направление прокрутки
            delta_x = event.angleDelta().x()
            delta_y = event.angleDelta().y()
            
            # Если есть горизонтальная прокрутка (trackpad), используем её
            if delta_x != 0:
                self.pan_offset.setX(self.pan_offset.x() - delta_x // 10)
                self.update()
                event.accept()
                return
            
            # Вертикальная прокрутка - панорамирование вверх/вниз
            if delta_y != 0:
                self.pan_offset.setY(self.pan_offset.y() - delta_y // 10)
                self.update()
                event.accept()
                return
        
        # Если ничего не обработано, передаем событие дальше
        super().wheelEvent(event)
    
    def keyReleaseEvent(self, event):
        """Обработка отпускания клавиш."""
        if event.key() == Qt.Key.Key_Space:
            # Отпускание пробела - завершение панорамирования
            if self.panning:
                self.panning = False
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().keyReleaseEvent(event)


class ImageMarkingWindow(QWidget):
    """Окно для разметки изображения."""
    
    def __init__(self, image, image_name=None, parent=None):
        super().__init__(parent)
        # Устанавливаем флаги окна для создания отдельного окна
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowTitle("Разметка изображения")
        self.setMinimumSize(800, 600)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # Сохраняем имя изображения
        self.image_name = image_name if image_name is not None else "unknown"
        
        # Сохраняем оригинальное изображение (numpy array) для масштабирования
        self.original_cv_image = image
        
        # Фактор масштабирования (будет рассчитан для подгонки под окно)
        self.zoom_scale = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.zoom_step = 0.1
        self.initial_zoom_calculated = False
        
        # Создаем горизонтальный layout для размещения изображения и списка bboxes
        main_layout = QHBoxLayout(self)
        
        # Создаем кастомный виджет для отображения изображения с разметкой
        self.image_widget = ImageDisplayWidget()
        # Сохраняем ссылку на окно в виджете для обновления списка
        self.image_widget.marking_window = self
        
        # Обертываем виджет изображения в QScrollArea для навигации с помощью scrollbars
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.image_widget)
        self.scroll_area.setWidgetResizable(False)  # Виджет не будет автоматически изменять размер
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Подключаем сигналы прокрутки для синхронизации с pan_offset
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self.on_horizontal_scroll)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_vertical_scroll)
        
        main_layout.addWidget(self.scroll_area, stretch=1)
        
        # Создаем список для отображения имен bboxes
        bbox_list_layout = QVBoxLayout()
        bbox_list_label = QLabel("Bounding Boxes:")
        bbox_list_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        bbox_list_layout.addWidget(bbox_list_label)
        
        self.bbox_list_widget = QListWidget()
        self.bbox_list_widget.setMaximumWidth(250)
        self.bbox_list_widget.setMinimumWidth(200)
        self.bbox_list_widget.itemClicked.connect(self.on_bbox_list_item_clicked)
        bbox_list_layout.addWidget(self.bbox_list_widget)
        
        # Создаем контейнер для списка
        bbox_list_container = QWidget()
        bbox_list_container.setLayout(bbox_list_layout)
        main_layout.addWidget(bbox_list_container)
        
        # Добавляем горячую клавишу Ctrl+S для сохранения в JSON
        self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.save_shortcut.activated.connect(self.save_bboxes)
        
        # Добавляем горячие клавиши для масштабирования
        self.zoom_in_shortcut = QShortcut(QKeySequence("Ctrl+="), self)  # Ctrl+= для увеличения
        self.zoom_in_shortcut.activated.connect(self.zoom_in)
        self.zoom_in_plus_shortcut = QShortcut(QKeySequence("Ctrl++"), self)  # Ctrl++ для увеличения
        self.zoom_in_plus_shortcut.activated.connect(self.zoom_in)
        self.zoom_out_shortcut = QShortcut(QKeySequence("Ctrl+-"), self)  # Ctrl+- для уменьшения
        self.zoom_out_shortcut.activated.connect(self.zoom_out)
        
        # Устанавливаем фокус на виджет изображения для получения событий клавиатуры
        self.image_widget.setFocus()
        
        # Отображаем изображение (с начальным масштабом для подгонки под окно)
        self.display_image(image)
        
        # Загружаем сохраненные bboxes для этого изображения
        self.load_bboxes()
        
        # Обновляем список bboxes
        self.update_bbox_list()
    
    def on_horizontal_scroll(self, value):
        """Обработка горизонтальной прокрутки."""
        # Синхронизируем pan_offset с позицией scrollbar
        if hasattr(self, 'image_widget') and hasattr(self, 'scroll_area'):
            h_scrollbar = self.scroll_area.horizontalScrollBar()
            max_value = h_scrollbar.maximum()
            if max_value > 0:
                # Преобразуем значение scrollbar в pan_offset
                # Scrollbar: 0 (слева) до max (справа)
                # Когда scrollbar = 0, изображение сдвинуто вправо (pan_offset отрицательный)
                # Когда scrollbar = max, изображение сдвинуто влево (pan_offset положительный)
                center_x = max_value // 2
                self.image_widget.pan_offset.setX(center_x - value)
                self.image_widget.update()
    
    def on_vertical_scroll(self, value):
        """Обработка вертикальной прокрутки."""
        # Синхронизируем pan_offset с позицией scrollbar
        if hasattr(self, 'image_widget') and hasattr(self, 'scroll_area'):
            v_scrollbar = self.scroll_area.verticalScrollBar()
            max_value = v_scrollbar.maximum()
            if max_value > 0:
                # Преобразуем значение scrollbar в pan_offset
                # Scrollbar: 0 (вверху) до max (внизу)
                # Когда scrollbar = 0, изображение сдвинуто вниз (pan_offset отрицательный)
                # Когда scrollbar = max, изображение сдвинуто вверх (pan_offset положительный)
                center_y = max_value // 2
                self.image_widget.pan_offset.setY(center_y - value)
                self.image_widget.update()
    
    def update_scrollbars(self):
        """Обновить позиции scrollbars на основе pan_offset и размера изображения."""
        if not hasattr(self, 'scroll_area') or not hasattr(self, 'image_widget'):
            return
        
        # Вычисляем размеры для scrollbars на основе отображаемого pixmap
        if not self.image_widget.display_pixmap:
            return
            
        pixmap_size = self.image_widget.display_pixmap.size()
        viewport_size = self.scroll_area.viewport().size()
        
        # Устанавливаем минимальный размер виджета равным размеру pixmap
        self.image_widget.setMinimumSize(pixmap_size)
        self.image_widget.resize(pixmap_size)
        
        # Обновляем диапазоны scrollbars
        h_scrollbar = self.scroll_area.horizontalScrollBar()
        v_scrollbar = self.scroll_area.verticalScrollBar()
        
        # Временно блокируем сигналы, чтобы избежать рекурсии
        h_scrollbar.blockSignals(True)
        v_scrollbar.blockSignals(True)
        
        if pixmap_size.width() > viewport_size.width():
            h_max = pixmap_size.width() - viewport_size.width()
            h_scrollbar.setMaximum(h_max)
            h_scrollbar.setPageStep(viewport_size.width())
            # Устанавливаем позицию на основе pan_offset
            # pan_offset положительный = изображение сдвинуто влево = scrollbar должен быть меньше центра
            # pan_offset отрицательный = изображение сдвинуто вправо = scrollbar должен быть больше центра
            center_x = h_max // 2
            scroll_value = center_x - self.image_widget.pan_offset.x()
            scroll_value = max(0, min(h_max, scroll_value))  # Ограничиваем диапазон
            h_scrollbar.setValue(int(scroll_value))
            h_scrollbar.setVisible(True)
        else:
            # Если изображение меньше viewport, сбрасываем горизонтальный pan_offset
            self.image_widget.pan_offset.setX(0)
            h_scrollbar.setMaximum(0)
            h_scrollbar.setVisible(False)
        
        if pixmap_size.height() > viewport_size.height():
            v_max = pixmap_size.height() - viewport_size.height()
            v_scrollbar.setMaximum(v_max)
            v_scrollbar.setPageStep(viewport_size.height())
            # Устанавливаем позицию на основе pan_offset
            # pan_offset положительный = изображение сдвинуто вверх = scrollbar должен быть меньше центра
            # pan_offset отрицательный = изображение сдвинуто вниз = scrollbar должен быть больше центра
            center_y = v_max // 2
            scroll_value = center_y - self.image_widget.pan_offset.y()
            scroll_value = max(0, min(v_max, scroll_value))  # Ограничиваем диапазон
            v_scrollbar.setValue(int(scroll_value))
            v_scrollbar.setVisible(True)
        else:
            # Если изображение меньше viewport, сбрасываем вертикальный pan_offset
            self.image_widget.pan_offset.setY(0)
            v_scrollbar.setMaximum(0)
            v_scrollbar.setVisible(False)
        
        # Разблокируем сигналы
        h_scrollbar.blockSignals(False)
        v_scrollbar.blockSignals(False)
    
    def display_image(self, image=None):
        """Отобразить изображение в окне с учетом текущего масштаба."""
        try:
            # Используем сохраненное изображение, если не передано новое
            if image is None:
                image = self.original_cv_image
            else:
                self.original_cv_image = image
            
            # Конвертируем BGR в RGB для Qt
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            
            # Сохраняем оригинальное изображение для возможного использования
            self.original_pixmap = pixmap
            
            # Рассчитываем начальный масштаб для подгонки изображения под окно (только при первом отображении)
            if not self.initial_zoom_calculated:
                # Получаем размер виджета изображения
                widget_width = self.image_widget.width()
                widget_height = self.image_widget.height()
                
                # Если виджет еще не отображен, используем размер окна
                if widget_width <= 0 or widget_height <= 0:
                    widget_width = self.width() - 20
                    widget_height = self.height() - 20
                
                # Рассчитываем масштаб для подгонки изображения под размер виджета
                if widget_width > 0 and widget_height > 0 and w > 0 and h > 0:
                    scale_x = widget_width / w
                    scale_y = widget_height / h
                    # Используем меньший масштаб, чтобы изображение полностью поместилось
                    self.zoom_scale = min(scale_x, scale_y) * 0.95  # 0.95 для небольшого отступа
                    # Ограничиваем начальный масштаб разумными пределами
                    self.zoom_scale = max(self.min_zoom, min(self.zoom_scale, self.max_zoom))
                    self.initial_zoom_calculated = True
            
            # Применяем масштабирование
            scaled_width = int(w * self.zoom_scale)
            scaled_height = int(h * self.zoom_scale)
            
            # Масштабируем pixmap
            scaled_pixmap = pixmap.scaled(
                scaled_width, scaled_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Проверяем, если изображение стало меньше виджета, сбрасываем pan_offset сразу
            # (чтобы избежать пустых полей при уменьшении)
            if hasattr(self, 'scroll_area') and hasattr(self.scroll_area, 'viewport'):
                viewport_size = self.scroll_area.viewport().size()
                if scaled_width <= viewport_size.width() and scaled_height <= viewport_size.height():
                    self.image_widget.pan_offset = QPoint(0, 0)
            
            # Устанавливаем изображение в виджет
            self.image_widget.set_image(scaled_pixmap)
            
            # Обновляем scrollbars после установки изображения (сбросит pan_offset если нужно)
            # Используем QTimer для отложенного обновления после того, как виджет обновится
            def update_scrollbars_and_image():
                self.update_scrollbars()
                self.image_widget.update()
            QTimer.singleShot(10, update_scrollbars_and_image)
            
        except Exception as e:
            error_label = QLabel(f"Ошибка при отображении изображения: {str(e)}")
            layout = self.layout()
            if layout:
                layout.addWidget(error_label)
    
    def zoom_in(self):
        """Увеличить масштаб изображения."""
        old_scale = self.zoom_scale
        self.zoom_scale = min(self.zoom_scale + self.zoom_step, self.max_zoom)
        if old_scale != self.zoom_scale:
            self._update_bboxes_scale(old_scale, self.zoom_scale)
            self.display_image()
    
    def zoom_out(self):
        """Уменьшить масштаб изображения."""
        old_scale = self.zoom_scale
        self.zoom_scale = max(self.zoom_scale - self.zoom_step, self.min_zoom)
        if old_scale != self.zoom_scale:
            self._update_bboxes_scale(old_scale, self.zoom_scale)
            self.display_image()
            # Обновляем scrollbars после изменения масштаба
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(10, self.update_scrollbars)
    
    def _update_bboxes_scale(self, old_scale, new_scale):
        """Обновить координаты bboxes при изменении масштаба."""
        if old_scale == 0 or new_scale == 0:
            return
        scale_factor = new_scale / old_scale
        bboxes = self.image_widget.bounding_boxes
        updated_bboxes = []
        for box in bboxes:
            x1, y1, x2, y2, angle, selected, name = box
            updated_bboxes.append((
                x1 * scale_factor,
                y1 * scale_factor,
                x2 * scale_factor,
                y2 * scale_factor,
                angle,
                selected,
                name
            ))
        self.image_widget.bounding_boxes = updated_bboxes
        self.image_widget.update()

    def showEvent(self, event):
        """Обработка показа окна - пересчитываем начальный масштаб если еще не был рассчитан."""
        super().showEvent(event)
        if hasattr(self, 'original_cv_image') and not self.initial_zoom_calculated:
            # Пересчитываем начальный масштаб после того, как окно показано
            self.initial_zoom_calculated = False
            self.display_image()
    
    def resizeEvent(self, event):
        """Обработка изменения размера окна разметки."""
        # При изменении размера окна перерисовываем изображение с текущим масштабом
        # (не пересчитываем начальный масштаб, чтобы сохранить пользовательский zoom)
        if hasattr(self, 'original_cv_image'):
            # Временно отключаем пересчет начального масштаба
            was_calculated = self.initial_zoom_calculated
            self.initial_zoom_calculated = True
            self.display_image()
            self.initial_zoom_calculated = was_calculated
        super().resizeEvent(event)
    
    def get_bboxes_file_path(self):
        """Получить путь к единому файлу для сохранения всех bboxes."""
        project_root = Path(__file__).parent.parent.parent
        markup_dir = project_root / "markup_info"
        markup_dir.mkdir(exist_ok=True)
        return markup_dir / "bboxes.json"
    
    def save_bboxes(self):
        """Сохранить bboxes в единый JSON файл (для всех изображений)."""
        try:
            bboxes_file = self.get_bboxes_file_path()
            bboxes = self.image_widget.bounding_boxes
            
            # Загружаем существующие данные, если файл есть
            all_bboxes_data = {}
            if bboxes_file.exists():
                try:
                    with open(bboxes_file, 'r', encoding='utf-8') as f:
                        all_bboxes_data = json.load(f)
                except:
                    all_bboxes_data = {}
            
            # Конвертируем текущие bboxes в список словарей для JSON
            # Важно: конвертируем координаты из масштабированного пространства в оригинальное
            bboxes_data = []
            for box in bboxes:
                x1, y1, x2, y2, angle, selected, name = box
                # Конвертируем координаты обратно в оригинальный размер изображения
                orig_x1 = x1 / self.zoom_scale
                orig_y1 = y1 / self.zoom_scale
                orig_x2 = x2 / self.zoom_scale
                orig_y2 = y2 / self.zoom_scale
                bboxes_data.append({
                    'x1': float(orig_x1),
                    'y1': float(orig_y1),
                    'x2': float(orig_x2),
                    'y2': float(orig_y2),
                    'angle': float(angle),
                    'name': name if name else ""
                })
            
            # Обновляем данные для текущего изображения (используем имя изображения как ключ)
            image_key = self.image_name
            all_bboxes_data[image_key] = bboxes_data
            
            # Сохраняем все данные обратно в JSON
            with open(bboxes_file, 'w', encoding='utf-8') as f:
                json.dump(all_bboxes_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка при сохранении bboxes: {str(e)}")
    
    def load_bboxes(self):
        """Загрузить bboxes из единого JSON файла для текущего изображения."""
        try:
            bboxes_file = self.get_bboxes_file_path()
            
            if not bboxes_file.exists():
                return  # Нет сохраненных bboxes
            
            # Загружаем из JSON
            with open(bboxes_file, 'r', encoding='utf-8') as f:
                all_bboxes_data = json.load(f)
            
            # Извлекаем bboxes для текущего изображения (используем имя изображения как ключ)
            image_key = self.image_name
            if image_key not in all_bboxes_data:
                return  # Нет bboxes для этого изображения
            
            bboxes_data = all_bboxes_data[image_key]
            
            # Конвертируем обратно в формат (x1, y1, x2, y2, angle, selected, name)
            # Важно: конвертируем координаты из оригинального пространства в текущее масштабированное
            loaded_bboxes = []
            for bbox_data in bboxes_data:
                # Конвертируем координаты из оригинального размера в текущий масштаб
                scaled_x1 = bbox_data['x1'] * self.zoom_scale
                scaled_y1 = bbox_data['y1'] * self.zoom_scale
                scaled_x2 = bbox_data['x2'] * self.zoom_scale
                scaled_y2 = bbox_data['y2'] * self.zoom_scale
                loaded_bboxes.append((
                    scaled_x1,
                    scaled_y1,
                    scaled_x2,
                    scaled_y2,
                    bbox_data.get('angle', 0.0),
                    False,  # selected = False по умолчанию
                    bbox_data.get('name', '')
                ))
            
            # Устанавливаем загруженные bboxes
            self.image_widget.bounding_boxes = loaded_bboxes
            self.image_widget.update()  # Обновляем отображение
            
            # Обновляем список bboxes
            self.update_bbox_list()
            
        except Exception as e:
            print(f"Ошибка при загрузке bboxes: {str(e)}")
    
    def update_bbox_list(self):
        """Обновить список имен bboxes в боковой панели."""
        if not hasattr(self, 'bbox_list_widget'):
            return
        
        self.bbox_list_widget.clear()
        bboxes = self.image_widget.bounding_boxes
        
        for i, box in enumerate(bboxes):
            x1, y1, x2, y2, angle, selected, name = box
            # Показываем имя или "Unnamed" если имя пустое
            display_name = name if name else f"Unnamed #{i+1}"
            self.bbox_list_widget.addItem(display_name)
            
            # Получаем элемент для настройки
            item = self.bbox_list_widget.item(i)
            if item:
                # Выделяем неназванные элементы светло-красным цветом
                if not name or name.strip() == "":
                    light_red = QColor(255, 200, 200)  # Светло-красный цвет
                    item.setBackground(light_red)
                
                # Выделяем текущий выбранный bbox
                if selected and i == self.image_widget.selected_box_index:
                    item.setSelected(True)
                    self.bbox_list_widget.setCurrentItem(item)
    
    def on_bbox_list_item_clicked(self, item):
        """Обработка клика по элементу списка bboxes - выделить соответствующий bbox."""
        row = self.bbox_list_widget.row(item)
        if 0 <= row < len(self.image_widget.bounding_boxes):
            # Выделяем соответствующий bbox
            self.image_widget.selected_box_index = row
            # Обновляем флаги выбранности для всех bboxes
            for i, box in enumerate(self.image_widget.bounding_boxes):
                x1, y1, x2, y2, angle, selected, name = box
                self.image_widget.bounding_boxes[i] = (x1, y1, x2, y2, angle, i == row, name)
            self.image_widget.update()
            # Обновляем список для синхронизации выделения
            self.update_bbox_list()
    
    def closeEvent(self, event):
        """Обработка закрытия окна разметки."""
        # Проверяем наличие неназванных bboxes
        bboxes = self.image_widget.bounding_boxes
        unnamed_bboxes = []
        for i, box in enumerate(bboxes):
            x1, y1, x2, y2, angle, selected, name = box
            if not name or name.strip() == "":
                unnamed_bboxes.append(i + 1)  # +1 для отображения (начинаем с 1, а не 0)
        
        # Если есть неназванные bboxes, показываем предупреждение
        if unnamed_bboxes:
            unnamed_count = len(unnamed_bboxes)
            if unnamed_count == 1:
                message = f"Есть 1 неназванный bounding box (№{unnamed_bboxes[0]}).\n\nВы хотите вернуться и задать имя или продолжить закрытие окна?"
            else:
                bbox_numbers = ", ".join([f"№{num}" for num in unnamed_bboxes[:5]])  # Показываем первые 5
                if unnamed_count > 5:
                    bbox_numbers += f" и еще {unnamed_count - 5}"
                message = f"Есть {unnamed_count} неназванных bounding boxes ({bbox_numbers}).\n\nВы хотите вернуться и задать имена или продолжить закрытие окна?"
            
            # Создаем диалог с кнопками "Вернуться" и "Продолжить"
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Неназванные bounding boxes")
            msg_box.setText(message)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            
            # Добавляем кнопки
            go_back_button = msg_box.addButton("Вернуться", QMessageBox.ButtonRole.RejectRole)
            continue_button = msg_box.addButton("Продолжить", QMessageBox.ButtonRole.AcceptRole)
            
            # Устанавливаем кнопку по умолчанию
            msg_box.setDefaultButton(go_back_button)
            
            # Показываем диалог
            msg_box.exec()
            
            # Если пользователь выбрал "Вернуться", отменяем закрытие
            if msg_box.clickedButton() == go_back_button:
                event.ignore()
                return
        
        # Сохраняем bboxes перед закрытием
        self.save_bboxes()
        
        # Очищаем ссылку в главном окне, если она существует
        if hasattr(self, 'main_window_ref'):
            self.main_window_ref.marking_window = None
        event.accept()

    def rename_selected_bbox(self):
        """Переименовать выбранный bbox через диалог."""
        # Получаем индекс выбранного bbox
        selected_index = None
        
        # Сначала проверяем, есть ли выбранный элемент в списке
        current_item = self.bbox_list_widget.currentItem()
        if current_item:
            selected_index = self.bbox_list_widget.row(current_item)
        # Если нет выбранного в списке, проверяем selected_box_index в image_widget
        elif hasattr(self.image_widget, 'selected_box_index') and self.image_widget.selected_box_index is not None:
            selected_index = self.image_widget.selected_box_index
        
        # Если нет выбранного bbox, ничего не делаем
        if selected_index is None or selected_index < 0 or selected_index >= len(self.image_widget.bounding_boxes):
            return
        
        # Получаем текущее имя bbox
        box = self.image_widget.bounding_boxes[selected_index]
        x1, y1, x2, y2, angle, selected, current_name = box
        
        # Показываем диалог для ввода нового имени
        new_name, ok = QInputDialog.getText(
            self,
            "Переименовать Bounding Box",
            f"Введите новое имя для bbox #{selected_index + 1}:",
            text=current_name if current_name else ""
        )
        
        # Если пользователь нажал OK и ввел имя
        if ok and new_name is not None:
            # Обновляем имя в bbox
            self.image_widget.bounding_boxes[selected_index] = (x1, y1, x2, y2, angle, selected, new_name)
            # Обновляем отображение
            self.image_widget.update()
            # Обновляем список
            self.update_bbox_list()
            # Выделяем переименованный элемент в списке
            if selected_index < self.bbox_list_widget.count():
                self.bbox_list_widget.setCurrentRow(selected_index)

    def keyPressEvent(self, event):
        """Enter/Return — переименование выбранного бокса."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.rename_selected_bbox()
            return
        super().keyPressEvent(event)


# Optional: Run standalone for testing
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindowControllerV2()
    window.show()
    sys.exit(app.exec())
