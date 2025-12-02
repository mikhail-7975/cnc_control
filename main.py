import sys

from PyQt6.QtWidgets import QMainWindow, QApplication, QLabel 
from mainwindow_controller import MainWindowController

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindowController()
    window.show()
    sys.exit(app.exec())