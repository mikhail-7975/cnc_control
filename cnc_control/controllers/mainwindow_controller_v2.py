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
    QAbstractItemView, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QWidget, QInputDialog
)
from PyQt6.QtCore import QTimer, Qt, QPoint, QRectF
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QPolygonF, QCursor, QFont, QShortcut, QKeySequence
import math
# Try to import UI v2 - adjust class name if needed
# Add project root to path for UI imports
# project_root = Path(__file__).parent.parent.parent
# if str(project_root) not in sys.path:
#     sys.path.insert(0, str(project_root))

from ui.generated.mainwindow_ui_v2 import Ui_MainWindow as Ui_MainWindowV2
from cnc_control.core.cnc.drivers.grbl_driver import CncMachineDriver
from cnc_control.core.camera.camera_reader import ThreadSafeCameraReader


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
        self.current_etalon_index = -1  # Индекс текущего изображения (-1 если нет изображений)
        
        # Reference to marking window to prevent garbage collection
        self.marking_window = None
        
        # Etalon image display label
        self.etalon_image_label = QLabel(self.ui.display_etalon_image_widget)
        self.etalon_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.etalon_image_label.setScaledContents(False)
        self.etalon_image_label.resize(self.ui.display_etalon_image_widget.size())
        self.clear_etalon_display()

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
        self.ui.mark_image_button.clicked.connect(self.open_mark_image_window)

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
            for file_path in file_paths:
                # Загружаем изображение с помощью OpenCV
                image = cv2.imread(file_path)
                if image is None:
                    print(f"Предупреждение: не удалось загрузить изображение {file_path}")
                    continue
                loaded_images.append(image)
            
            if loaded_images:
                self.etalon_images = loaded_images
                self.current_etalon_index = 0
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
            image = self.etalon_images[self.current_etalon_index]
            # Конвертируем BGR в RGB для Qt
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            
            # Масштабируем изображение под размер виджета
            scaled_pixmap = pixmap.scaled(
                self.ui.display_etalon_image_widget.width(),
                self.ui.display_etalon_image_widget.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.etalon_image_label.setPixmap(scaled_pixmap)
            self.etalon_image_label.resize(self.ui.display_etalon_image_widget.size())
            self.ui.display_etalon_image_widget.setStyleSheet("")
            
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

    def next_etalon_image(self):
        """Перейти к следующему эталонному изображению."""
        if not self.etalon_images:
            return
        
        self.current_etalon_index = (self.current_etalon_index + 1) % len(self.etalon_images)
        self.display_current_etalon_image()

    def prev_etalon_image(self):
        """Перейти к предыдущему эталонному изображению."""
        if not self.etalon_images:
            return
        
        self.current_etalon_index = (self.current_etalon_index - 1) % len(self.etalon_images)
        self.display_current_etalon_image()

    def clear_etalon_display(self):
        """Очистить отображение эталонного изображения."""
        self.etalon_image_label.clear()
        self.ui.display_etalon_image_widget.setStyleSheet("background-color: black;")
        self.etalon_image_label.move(0, 0)
        self.etalon_image_label.resize(self.ui.display_etalon_image_widget.size())

    def open_mark_image_window(self):
        """Открыть новое окно для разметки изображения."""
        if not self.etalon_images or self.current_etalon_index < 0:
            self.show_error("Нет изображения для разметки. Загрузите эталонные изображения.")
            return
        
        try:
            # Получаем текущее изображение
            current_image = self.etalon_images[self.current_etalon_index]
            
            # Если окно уже открыто, просто активируем его
            if self.marking_window is not None and self.marking_window.isVisible():
                self.marking_window.raise_()
                self.marking_window.activateWindow()
                return
            
            # Получаем номер изображения (индекс + 1)
            image_number = self.current_etalon_index + 1
            
            # Создаем и показываем новое окно как отдельное окно (не дочернее)
            self.marking_window = ImageMarkingWindow(current_image, image_number=image_number, parent=None)
            # Сохраняем ссылку на главное окно в окне разметки для очистки при закрытии
            self.marking_window.main_window_ref = self
            
            # Устанавливаем размер окна такой же, как у главного окна
            main_window_size = self.size()
            self.marking_window.resize(main_window_size)
            
            self.marking_window.show()
            self.marking_window.raise_()  # Поднимаем окно на передний план
            self.marking_window.activateWindow()  # Активируем окно
        except Exception as e:
            self.show_error(f"Ошибка при открытии окна разметки: {str(e)}")

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
        if self.etalon_image_label is not None:
            self.etalon_image_label.resize(self.ui.display_etalon_image_widget.size())
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
        self.last_mouse_pos = QPoint(0, 0)
        self.dragging_box = False
        self.drag_type = None  # 'corner', 'edge', 'move', or None
        self.drag_corner_index = None  # 0-3 for corners
        self.drag_start_pos = None
        self.drag_start_box = None  # Original box coordinates when drag started
        self.rotation_base_angle = 0.0
        self.rotation_start_pointer_angle = 0.0
        
    def set_image(self, pixmap):
        """Установить изображение для отображения."""
        self.original_image = pixmap
        self.display_pixmap = pixmap
        self.update()
    
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
    
    def paintEvent(self, event):
        """Отрисовка изображения и bounding boxes."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Рисуем изображение
        if self.display_pixmap:
            # Центрируем изображение
            pixmap_rect = self.display_pixmap.rect()
            widget_rect = self.rect()
            x = (widget_rect.width() - pixmap_rect.width()) // 2
            y = (widget_rect.height() - pixmap_rect.height()) // 2
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
            
            # Рисуем текущий бокс при создании
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
                    
                    # Начинаем перетаскивание
                    self.dragging_box = True
                    self.drag_type = interaction_type
                    self.drag_corner_index = interaction_index
                    self.drag_start_pos = pos
                    self.drag_start_box = self.bounding_boxes[clicked_box]
                    self.update()
                else:
                    # Начинаем создание нового бокса
                    self.current_box_start = pos
                    self.drawing_box = True
                    self.selected_box_index = None
                    self.dragging_box = False
        
        elif event.button() == Qt.MouseButton.RightButton:
            # Правый клик - режим поворота
            if self.selected_box_index is not None:
                self.rotation_mode = True
    
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
    
    def mouseReleaseEvent(self, event):
        """Обработка отпускания мыши."""
        if event.button() == Qt.MouseButton.LeftButton:
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
            if self.dragging_box:
                self.dragging_box = False
                self.drag_type = None
                self.drag_corner_index = None
                self.drag_start_pos = None
                self.drag_start_box = None
    
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
    
    def keyPressEvent(self, event):
        """Обработка нажатия клавиш."""
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # Если нажат Enter и есть выбранный бокс, открываем диалог для ввода имени
            if self.selected_box_index is not None:
                self._show_name_dialog_for_selected_box()
        elif event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            # Если нажат Delete/Backspace и есть выбранный бокс, удаляем его
            if self.selected_box_index is not None and self.selected_box_index < len(self.bounding_boxes):
                # Удаляем выбранный бокс
                del self.bounding_boxes[self.selected_box_index]
                # Сбрасываем выделение
                self.selected_box_index = None
                # Обновляем отображение
                self.update()
                # Обновляем список bboxes в окне разметки
                if hasattr(self, 'marking_window') and self.marking_window:
                    self.marking_window.update_bbox_list()
        else:
            super().keyPressEvent(event)


class ImageMarkingWindow(QWidget):
    """Окно для разметки изображения."""
    
    def __init__(self, image, image_number=None, parent=None):
        super().__init__(parent)
        # Устанавливаем флаги окна для создания отдельного окна
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowTitle("Разметка изображения")
        self.setMinimumSize(800, 600)
        
        # Сохраняем номер/имя изображения
        self.image_number = image_number if image_number is not None else "unknown"
        
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
        main_layout.addWidget(self.image_widget, stretch=1)
        
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
            
            # Устанавливаем изображение в виджет
            self.image_widget.set_image(scaled_pixmap)
            
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
            
            # Обновляем данные для текущего изображения
            image_key = str(self.image_number)
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
            
            # Извлекаем bboxes для текущего изображения
            image_key = str(self.image_number)
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
            
            # Выделяем текущий выбранный bbox
            if selected and i == self.image_widget.selected_box_index:
                item = self.bbox_list_widget.item(i)
                if item:
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
        # Сохраняем bboxes перед закрытием
        self.save_bboxes()
        
        # Очищаем ссылку в главном окне, если она существует
        if hasattr(self, 'main_window_ref'):
            self.main_window_ref.marking_window = None
        event.accept()


# Optional: Run standalone for testing
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindowControllerV2()
    window.show()
    sys.exit(app.exec())
