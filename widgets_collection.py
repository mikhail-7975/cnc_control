from PyQt6.QtWidgets import QToolButton, QStyle, QMainWindow, QWidget, QHBoxLayout, QSizePolicy, QGroupBox,\
QGridLayout, QLabel, QPushButton
from PyQt6.QtGui import QIcon
from PyQt6 import QtCore

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


class JoystickGroup(QWidget):
    def __init__(self):
        super().__init__()
        self.joystic_groupbox = QGroupBox()
        self.joystic_groupbox.setMaximumSize(QtCore.QSize(380, 320))
        self.joystic_groupbox.setTitle("")
        self.joystic_groupbox.setObjectName("joystic_groupbox")
        
        self.joystick_buttons_layout = QGridLayout(self.joystic_groupbox)
        self.joystick_buttons_layout.setObjectName("gridLayout_2")
        
        self._create_movement_buttons()
        self._create_vertical_buttons()
        self._create_zero_buttons()
        self._create_coordinate_labels()

        self.setLayout(self.joystick_buttons_layout)

    def _create_movement_buttons(self):
        self.up50_button = self._create_button("up50_button", "50", 0, 3)
        self.up10_button = self._create_button("up10_button", "10", 1, 3)
        self.up_1_button = self._create_button("up_1_button", "1 ", 2, 3)
        
        self.left_50_button = self._create_button("left_50_button", "<-50", 3, 0)
        self.left_10_button = self._create_button("left_10_button", "<-10", 3, 1)
        self.left_1_button = self._create_button("left_1_button", "<-1", 3, 2)
        
        self.right_1_button = self._create_button("right_1_button", "1->", 3, 4)
        self.right_10_button = self._create_button("right_10_button", "10->", 3, 5)
        self.right_50_button = self._create_button("right_50_button", "50->", 3, 6)

    def _create_vertical_buttons(self):
        self.pushButton_4 = self._create_button("pushButton_4", "1 V", 4, 3)
        self.pushButton_5 = self._create_button("pushButton_5", "10 V", 5, 3)
        self.pushButton_6 = self._create_button("pushButton_6", "50 V", 6, 3)

    def _create_zero_buttons(self):
        self.zero_x_pushButton = self._create_button("pushButton", "zero X", 6, 0, 60, 60)
        self.zero_y_pushButton = self._create_button("pushButton_2", "zero Y", 6, 1, 60)
        self.zero_both_pushButton = self._create_button("pushButton_3", "zero", 5, 0, 60)

    def _create_coordinate_labels(self):
        self.x_value_label = QLabel(parent=self.joystic_groupbox)
        self.x_value_label.setObjectName("label_4")
        self.joystick_buttons_layout.addWidget(self.x_value_label, 0, 5, 1, 1)
        
        self.y_value_label = QLabel(parent=self.joystic_groupbox)
        self.y_value_label.setObjectName("label_5")
        self.joystick_buttons_layout.addWidget(self.y_value_label, 1, 5, 1, 1)
        
        self.current_x_value_number_label = QLabel(parent=self.joystic_groupbox)
        self.current_x_value_number_label.setText("")
        self.current_x_value_number_label.setObjectName("cur_x_label")
        self.joystick_buttons_layout.addWidget(self.current_x_value_number_label, 0, 6, 1, 1)
        
        self.current_y_value_number_label = QLabel(parent=self.joystic_groupbox)
        self.current_y_value_number_label.setText("")
        self.current_y_value_number_label.setObjectName("cur_y_label")
        self.joystick_buttons_layout.addWidget(self.current_y_value_number_label, 1, 6, 1, 1)

    def _create_button(self, name, text, row, col, max_width=40, max_height=16777215):
        button = QPushButton(parent=self.joystic_groupbox)
        button.setMaximumSize(QtCore.QSize(max_width, max_height))
        button.setObjectName(name)
        self.joystick_buttons_layout.addWidget(button, row, col, 1, 1)
        return button


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