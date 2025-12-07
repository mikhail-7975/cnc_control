import sys

from PyQt6.QtWidgets import QMainWindow, QApplication, QLabel 
from mainwindow_controller_v2 import MainWindowControllerV2

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindowControllerV2()
    window.show()
    sys.exit(app.exec())