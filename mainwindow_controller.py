import sys
import cv2
import time
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QLabel, QListWidget,
    QAbstractItemView, QVBoxLayout, QFileDialog
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap
from mainwindow_ui import Ui_MainWindow  # Generated UI file
from cnc_control.cnc_lib.new_machine_lib import CncMachineDriver
from cnc_control.camera.camera_reader import ThreadSafeCameraReader
from widgets_collection import TrackFileControlWidget

class MainWindowController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # === Replace scroll area contents with QListWidget ===
        # For take image points
        self.take_image_points_list = QListWidget()
        self.take_image_points_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.ui.take_image_points_display_area.setWidget(self.take_image_points_list)

        self.image_points_file_control = TrackFileControlWidget()
        self.image_points_file_control.setMaximumSize(100, 40)
        self.ui.verticalLayout_3.addWidget(self.image_points_file_control)

        self.image_points_currnet_filename = None
        self.image_points_file_control.new_file_tool_button.clicked.connect(self.__new_file_button_clicked)
        self.image_points_file_control.open_file_tool_button.clicked.connect(self.__open_file_button_clicked)
        self.image_points_file_control.save_file_tool_button.clicked.connect(self.__save_file_button_clicked)

        # For component coordinates
        self.component_coordinates_list = QListWidget()
        self.component_coordinates_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.ui.component_coordinates_display_area.setWidget(self.component_coordinates_list)

        self.component_coordinates_file_control = TrackFileControlWidget()
        self.component_coordinates_file_control.setMaximumSize(100, 40)
        self.ui.verticalLayout_4.addWidget(self.component_coordinates_file_control)

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

        self.take_image_current_filename = "keypoints/"

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
        self.ui.pushButton_4.clicked.connect(lambda: self.move_axis('Z', 1))    # Assuming V = Z
        self.ui.pushButton_5.clicked.connect(lambda: self.move_axis('Z', 10))
        self.ui.pushButton_6.clicked.connect(lambda: self.move_axis('Z', 50))

        # Zeroing buttons
        self.ui.pushButton.clicked.connect(lambda: self.zero_axis('X'))         # zero X
        self.ui.pushButton_2.clicked.connect(lambda: self.zero_axis('Y'))       # zero Y
        self.ui.pushButton_3.clicked.connect(self.zero_all)                     # zero all

        self.ui.cur_x_label.setText("0.0")
        self.ui.cur_y_label.setText("0.0")

        # CNC connection
        self.ui.connect_cnc_button.clicked.connect(self.toggle_cnc_connection)

        # Coordinate list management
        self.ui.add_point_button.clicked.connect(self.add_image_point)
        self.ui.delete_point_button.clicked.connect(self.delete_selected_image_point)

        self.ui.add_button.clicked.connect(self.add_component_coordinate)
        self.ui.delete_component_button.clicked.connect(self.delete_selected_component)

    # === Coordinate list functionality ===

    def add_image_point(self):
        # For demo: add current position as point
        x = self.ui.cur_x_label.text()
        y = self.ui.cur_y_label.text()
        item_text = f"({x}, {y})"
        self.take_image_points_list.addItem(item_text)

    def delete_selected_image_point(self):
        row = self.take_image_points_list.currentRow()
        if row >= 0:
            self.take_image_points_list.takeItem(row)
        else:
            self.show_error("Нет выбранной точки для удаления.")

    def add_component_coordinate(self):
        # For demo: add current position
        x = self.ui.cur_x_label.text()
        y = self.ui.cur_y_label.text()
        item_text = f"Комп: ({x}, {y})"
        self.component_coordinates_list.addItem(item_text)

    def delete_selected_component(self):
        row = self.component_coordinates_list.currentRow()
        if row >= 0:
            self.component_coordinates_list.takeItem(row)
        else:
            self.show_error("Нет выбранной координаты компонента для удаления.")

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
        if hasattr(self, 'image_label') and self.image_label:
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
            self.driver.move_x(0)
            self.driver.move_y(0)
            self.cnc_connected = False
            self.ui.connect_cnc_button.setText("Подключить")
            self.driver.close_serial_port()
            self.driver = None
            print("CNC отключён")

    def show_error(self, message):
        print("ERROR:", message)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Ошибка", message)

    def __new_file_button_clicked(self):
        filename, _ = QFileDialog.getSaveFileName(
            parent=self,                            # Parent widget
            caption="Select a File",                  # Dialog window title
            directory="keypoints",                               # Default directory (empty string defaults to current working directory)
            filter="Text (*.txt)" # File filters
        )
        self.take_image_current_filename = filename if filename else "noname_image_points"
        # TODO: warning for existing file
        self.take_image_points_list.clear()

    def __open_file_button_clicked(self):
        filename, _ = QFileDialog.getOpenFileName(
            parent=self,                            # Parent widget
            caption="Select a File",                  # Dialog window title
            directory="keypoints",                               # Default directory (empty string defaults to current working directory)
            filter="Text (*.txt)" # File filters
        )
        if not filename:
            return
        self.take_image_current_filename = filename
        self.take_image_points_list.clear()
        with open(filename, 'r') as f:
            items_from_file = f.read().splitlines()
        self.take_image_points_list.addItems(items_from_file)

        # TODO: warning for existing file


    def __save_file_button_clicked(self):
        points = [self.take_image_points_list.item(i).text() for i in range(self.take_image_points_list.count())]
        with open (self.take_image_current_filename+"_.txt", 'w') as f:
            f.write('\n'.join(points))


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
    window = MainWindowController()
    window.show()
    sys.exit(app.exec())