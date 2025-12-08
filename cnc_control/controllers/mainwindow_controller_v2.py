"""
MainWindow Controller V2

Контроллер для работы с mainwindow_ui_v2.py.
Содержит все обработчики из старого контроллера и заготовки для новых кнопок.

Если имя класса UI отличается от Ui_MainWindowV2, измените импорт в начале файла.
"""
import sys
import cv2
import time
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QLabel, QListWidget,
    QAbstractItemView, QVBoxLayout, QFileDialog, QMessageBox, QWidget
)
from PyQt6.QtCore import QTimer, Qt, QPoint, QRectF
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QPolygonF
import math
# Try to import UI v2 - adjust class name if needed
import sys
from pathlib import Path
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
            
            # Создаем и показываем новое окно как отдельное окно (не дочернее)
            self.marking_window = ImageMarkingWindow(current_image, parent=None)
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
        self.original_image = None
        self.display_pixmap = None
        self.bounding_boxes = []  # Список bounding boxes: [x1, y1, x2, y2, angle, selected]
        self.current_box_start = None  # Начальная точка текущего бокса
        self.drawing_box = False
        self.selected_box_index = None
        self.rotation_mode = False
        self.rotation_start_angle = 0
        self.image_offset = QPoint(0, 0)
        self.last_mouse_pos = QPoint(0, 0)
        
    def set_image(self, pixmap):
        """Установить изображение для отображения."""
        self.original_image = pixmap
        self.display_pixmap = pixmap
        self.update()
    
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
            x1, y1, x2, y2, angle, selected = box
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
                x1, y1, x2, y2, angle, _ = box
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                dx = pos.x() - center_x
                dy = pos.y() - center_y
                self.rotation_start_angle = math.degrees(math.atan2(dy, dx)) - angle
            else:
                # Проверяем, кликнули ли по существующему боксу
                clicked_box = None
                for i, box in enumerate(self.bounding_boxes):
                    x1, y1, x2, y2, angle, _ = box
                    
                    # Простая проверка попадания в прямоугольник (в координатах изображения)
                    if min(x1, x2) <= pos.x() <= max(x1, x2) and min(y1, y2) <= pos.y() <= max(y1, y2):
                        clicked_box = i
                        break
                
                if clicked_box is not None:
                    self.selected_box_index = clicked_box
                    # Обновляем флаг выбранности
                    for i, box in enumerate(self.bounding_boxes):
                        x1, y1, x2, y2, angle, _ = box
                        self.bounding_boxes[i] = (x1, y1, x2, y2, angle, i == clicked_box)
                    self.update()
                else:
                    # Начинаем создание нового бокса
                    self.current_box_start = pos
                    self.drawing_box = True
                    self.selected_box_index = None
        
        elif event.button() == Qt.MouseButton.RightButton:
            # Правый клик - режим поворота
            if self.selected_box_index is not None:
                self.rotation_mode = True
    
    def mouseMoveEvent(self, event):
        """Обработка движения мыши."""
        widget_pos = event.position().toPoint()
        self.last_mouse_pos = widget_pos - self.image_offset
        
        if self.rotation_mode and self.selected_box_index is not None:
            # Поворот выбранного бокса
            box = self.bounding_boxes[self.selected_box_index]
            x1, y1, x2, y2, angle, _ = box
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            dx = self.last_mouse_pos.x() - center_x
            dy = self.last_mouse_pos.y() - center_y
            new_angle = math.degrees(math.atan2(dy, dx)) - self.rotation_start_angle
            self.bounding_boxes[self.selected_box_index] = (x1, y1, x2, y2, new_angle, True)
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
                    # Добавляем новый бокс (начало, конец, угол=0, выбран)
                    self.bounding_boxes.append((x1, y1, x2, y2, 0.0, True))
                    # Снимаем выделение с других боксов
                    for i in range(len(self.bounding_boxes) - 1):
                        box = self.bounding_boxes[i]
                        self.bounding_boxes[i] = (box[0], box[1], box[2], box[3], box[4], False)
                    self.selected_box_index = len(self.bounding_boxes) - 1
                
                self.drawing_box = False
                self.current_box_start = None
                self.update()
            
            self.rotation_mode = False
        
        elif event.button() == Qt.MouseButton.RightButton:
            self.rotation_mode = False


class ImageMarkingWindow(QWidget):
    """Окно для разметки изображения."""
    
    def __init__(self, image, parent=None):
        super().__init__(parent)
        # Устанавливаем флаги окна для создания отдельного окна
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowTitle("Разметка изображения")
        self.setMinimumSize(800, 600)
        
        # Создаем layout
        layout = QVBoxLayout(self)
        
        # Создаем кастомный виджет для отображения изображения с разметкой
        self.image_widget = ImageDisplayWidget()
        layout.addWidget(self.image_widget)
        
        # Отображаем изображение
        self.display_image(image)
    
    def display_image(self, image):
        """Отобразить изображение в окне."""
        try:
            # Конвертируем BGR в RGB для Qt
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            
            # Сохраняем оригинальное изображение для возможного использования
            self.original_pixmap = pixmap
            
            # Устанавливаем размер окна под изображение (с ограничениями)
            max_width = 1920
            max_height = 1080
            img_width = w
            img_height = h
            
            # Масштабируем если изображение слишком большое
            if img_width > max_width or img_height > max_height:
                scale = min(max_width / img_width, max_height / img_height)
                img_width = int(img_width * scale)
                img_height = int(img_height * scale)
                # Масштабируем pixmap для отображения
                pixmap = pixmap.scaled(
                    img_width, img_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            
            # Устанавливаем изображение в виджет
            self.image_widget.set_image(pixmap)
            
        except Exception as e:
            error_label = QLabel(f"Ошибка при отображении изображения: {str(e)}")
            layout = self.layout()
            if layout:
                layout.addWidget(error_label)

    def resizeEvent(self, event):
        """Обработка изменения размера окна разметки."""
        if hasattr(self, 'image_widget') and hasattr(self, 'original_pixmap'):
            # Масштабируем изображение при изменении размера окна
            scaled_pixmap = self.original_pixmap.scaled(
                self.width() - 50,
                self.height() - 50,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_widget.set_image(scaled_pixmap)
        super().resizeEvent(event)
    
    def closeEvent(self, event):
        """Обработка закрытия окна разметки."""
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
