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
    QAbstractItemView, QVBoxLayout, QFileDialog, QMessageBox
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap
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
        self.ui.component_coordinates_display_area.setWidget(self.component_coordinates_list)

        # Camera variables
        self.cam = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

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

        # Connect signals
        self.setup_connections()

    def setup_connections(self):
        # Camera
        self.ui.connect_camera_button.clicked.connect(self.toggle_camera)

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

        self.ui.add_button.clicked.connect(self.add_component_coordinate)
        self.ui.delete_component_button.clicked.connect(self.delete_selected_component)
        
        # New button handlers (заготовки для новых кнопок)
        # Загрузка координат компонентов из файла
        self.ui.load_from_file_button.clicked.connect(self.load_component_coordinates_from_file)

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
        if self.image_label is not None:
            self.image_label.resize(self.ui.image_displayer.size())
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


# Optional: Run standalone for testing
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindowControllerV2()
    window.show()
    sys.exit(app.exec())
