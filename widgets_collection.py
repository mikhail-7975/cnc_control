from PyQt6.QtWidgets import QToolButton, QStyle, QMainWindow, QWidget, QHBoxLayout, QSizePolicy
from PyQt6.QtGui import QIcon

class TrackFileControlWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.new_file_tool_button = QToolButton()
        new_file_icon: QIcon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        self.new_file_tool_button.setIcon(new_file_icon)
        self.new_file_tool_button.setToolTip("Новый файл ключевых точек")

        self.save_file_tool_button = QToolButton()
        save_file_icon: QIcon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        self.save_file_tool_button.setIcon(save_file_icon)
        self.save_file_tool_button.setToolTip("Сохранить файл ключевых точек")

        self.open_file_tool_button = QToolButton()
        open_file_icon: QIcon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        self.open_file_tool_button.setIcon(open_file_icon)
        self.open_file_tool_button.setToolTip("Открыть файл ключевых точек")

        self.edit_file_tool_button = QToolButton()
        edit_file_icon: QIcon = self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        self.edit_file_tool_button.setIcon(edit_file_icon)
        self.edit_file_tool_button.setToolTip("Редактировать файл ключевых точек")

        self.tool_layout = QHBoxLayout()
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        self.tool_layout.addWidget(self.new_file_tool_button)
        self.tool_layout.addWidget(self.save_file_tool_button)
        self.tool_layout.addWidget(self.open_file_tool_button)
        self.tool_layout.addWidget(self.edit_file_tool_button)
        self.setLayout(self.tool_layout)

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)

    main_window = QMainWindow()
    main_window.setWindowTitle("Пример с QToolBar")
    main_window.setMaximumSize(100, 40)
    
    # Создаем панель инструментов
    toolbar = TrackFileControlWidget()
    
    # Добавляем панель в главное окно
    main_window.setCentralWidget(toolbar)

    main_window.show()
    sys.exit(app.exec())