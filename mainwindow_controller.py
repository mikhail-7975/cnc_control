import sys
import cv2
from PyQt6.QtWidgets import QMainWindow, QApplication, QLabel
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap
from mainwindow_ui import Ui_MainWindow  # Generated UI file


class MainWindowController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Camera variables
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        # CNC-related variables (placeholder for serial connection)
        self.cnc_connected = False

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

        # CNC connection
        self.ui.connect_cnc_button.clicked.connect(self.toggle_cnc_connection)

    def toggle_camera(self):
        if self.cap is None or not self.cap.isOpened():
            port_text = self.ui.camera_port_lineEdit.text()
            try:
                port = int(port_text) if port_text.isdigit() else port_text
                self.cap = cv2.VideoCapture(port)
                if self.cap.isOpened():
                    self.ui.connect_camera_button.setText("Отключить камеру")
                    self.timer.start(30)  # ~30 FPS
                else:
                    self.show_error("Не удалось открыть камеру на порту: " + str(port))
                    self.cap = None
            except Exception as e:
                self.show_error(f"Ошибка при открытии камеры: {str(e)}")
                self.cap = None
        else:
            self.timer.stop()
            self.cap.release()
            self.cap = None
            self.ui.connect_camera_button.setText("Подключить")
            # Clear display
            self.ui.image_displayer.setStyleSheet("background-color: black;")

    def update_frame(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                # Convert OpenCV BGR to RGB
                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qt_image)
                # Scale to fit displayer while keeping aspect ratio
                scaled_pixmap = pixmap.scaled(
                    self.ui.image_displayer.width(),
                    self.ui.image_displayer.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                # Display using QLabel if not already set
                if not hasattr(self, 'image_label') or not self.image_label.parent():
                    self.image_label = QLabel(self.ui.image_displayer)
                    self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.image_label.resize(self.ui.image_displayer.size())
                    self.image_label.show()
                self.image_label.setPixmap(scaled_pixmap)
                self.image_label.resize(self.ui.image_displayer.size())
            else:
                self.timer.stop()
                self.show_error("Ошибка чтения кадра с камеры")

    def resizeEvent(self, event):
        if hasattr(self, 'image_label') and self.image_label:
            self.image_label.resize(self.ui.image_displayer.size())
        super().resizeEvent(event)

    def move_axis(self, axis, steps):
        # TODO: Send G-code or command to CNC (e.g., via serial)
        print(f"Moving {axis} by {steps} units")
        # Example placeholder:
        # if self.cnc_connected:
        #     self.serial.write(f"G91\nG0 {axis}{steps}\nG90\n".encode())

        # Update UI position labels (mock values for demo)
        if axis == 'X':
            current = float(self.ui.cur_x_label.text() or "0")
            self.ui.cur_x_label.setText(str(round(current + steps, 2)))
        elif axis == 'Y':
            current = float(self.ui.cur_y_label.text() or "0")
            self.ui.cur_y_label.setText(str(round(current + steps, 2)))

    def zero_axis(self, axis):
        if axis == 'X':
            self.ui.cur_x_label.setText("0.0")
        elif axis == 'Y':
            self.ui.cur_y_label.setText("0.0")
        print(f"Zeroing {axis} axis")

    def zero_all(self):
        self.ui.cur_x_label.setText("0.0")
        self.ui.cur_y_label.setText("0.0")
        print("Zeroing all axes")

    def toggle_cnc_connection(self):
        if not self.cnc_connected:
            port = self.ui.port_lineEdit.text()
            try:
                # TODO: Open serial connection to CNC
                # Example: self.serial = serial.Serial(port, 115200, timeout=1)
                self.cnc_connected = True
                self.ui.connect_cnc_button.setText("Отключить CNC")
                print(f"Подключено к CNC на {port}")
            except Exception as e:
                self.show_error(f"Не удалось подключиться к CNC: {str(e)}")
        else:
            # TODO: Close serial
            self.cnc_connected = False
            self.ui.connect_cnc_button.setText("Подключить")
            print("CNC отключён")

    def show_error(self, message):
        print("ERROR:", message)
        # Optional: Use QMessageBox for GUI error
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Ошибка", message)

    def closeEvent(self, event):
        if self.cap:
            self.cap.release()
        # TODO: Close CNC serial if open
        event.accept()


# Optional: Run standalone for testing
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindowController()
    window.show()
    sys.exit(app.exec())