from PyQt6 import QtCore, QtGui, QtWidgets

class CameraSettingsGroup:
    def __init__(self, parent):
        self.camera_settings_groupbox = QtWidgets.QGroupBox(parent=parent)
        self.camera_settings_groupbox.setObjectName("camera_settings_groupbox")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.camera_settings_groupbox)
        self.verticalLayout.setObjectName("verticalLayout")
        
        self.label = QtWidgets.QLabel(parent=self.camera_settings_groupbox)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        
        self.camera_port_lineEdit = QtWidgets.QLineEdit(parent=self.camera_settings_groupbox)
        self.camera_port_lineEdit.setObjectName("camera_port_lineEdit")
        self.verticalLayout.addWidget(self.camera_port_lineEdit)
        
        self.label_2 = QtWidgets.QLabel(parent=self.camera_settings_groupbox)
        self.label_2.setObjectName("label_2")
        self.verticalLayout.addWidget(self.label_2)
        
        self.camera_mode_groupbox = QtWidgets.QFontComboBox(parent=self.camera_settings_groupbox)
        self.camera_mode_groupbox.setObjectName("camera_mode_groupbox")
        self.verticalLayout.addWidget(self.camera_mode_groupbox)
        
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        
        self.connect_camera_button = QtWidgets.QPushButton(parent=self.camera_settings_groupbox)
        self.connect_camera_button.setObjectName("connect_camera_button")
        self.verticalLayout.addWidget(self.connect_camera_button)


class CncSettingsGroup:
    def __init__(self, parent):
        self.cnc_settings_groupbox = QtWidgets.QGroupBox(parent=parent)
        self.cnc_settings_groupbox.setMaximumSize(QtCore.QSize(380, 16777215))
        self.cnc_settings_groupbox.setObjectName("cnc_settings_groupbox")
        
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.cnc_settings_groupbox)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        
        self.port_label = QtWidgets.QLabel(parent=self.cnc_settings_groupbox)
        self.port_label.setObjectName("port_label")
        self.verticalLayout_2.addWidget(self.port_label)
        
        self.port_lineEdit = QtWidgets.QLineEdit(parent=self.cnc_settings_groupbox)
        self.port_lineEdit.setObjectName("port_lineEdit")
        self.verticalLayout_2.addWidget(self.port_lineEdit)
        
        spacerItem1 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
        self.verticalLayout_2.addItem(spacerItem1)
        
        self.connect_cnc_button = QtWidgets.QPushButton(parent=self.cnc_settings_groupbox)
        self.connect_cnc_button.setObjectName("connect_cnc_button")
        self.verticalLayout_2.addWidget(self.connect_cnc_button)

class ComponentCoordinatesGroup:
    def __init__(self, parent):
        self.componet_coordinates_groupbox = QtWidgets.QGroupBox(parent=parent)
        self.componet_coordinates_groupbox.setMinimumSize(QtCore.QSize(190, 0))
        self.componet_coordinates_groupbox.setObjectName("componet_coordinates_groupbox")
        
        self.verticalLayout_4 = QtWidgets.QVBoxLayout(self.componet_coordinates_groupbox)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        
        self.component_coordinates_display_area = QtWidgets.QScrollArea(parent=self.componet_coordinates_groupbox)
        self.component_coordinates_display_area.setWidgetResizable(True)
        self.component_coordinates_display_area.setObjectName("component_coordinates_display_area")
        
        self.scrollAreaWidgetContents_2 = QtWidgets.QWidget()
        self.scrollAreaWidgetContents_2.setGeometry(QtCore.QRect(0, 0, 164, 374))
        self.scrollAreaWidgetContents_2.setObjectName("scrollAreaWidgetContents_2")
        self.component_coordinates_display_area.setWidget(self.scrollAreaWidgetContents_2)
        self.verticalLayout_4.addWidget(self.component_coordinates_display_area)
        
        self.add_button = QtWidgets.QPushButton(parent=self.componet_coordinates_groupbox)
        self.add_button.setObjectName("add_button")
        self.verticalLayout_4.addWidget(self.add_button)
        
        self.delete_component_button = QtWidgets.QPushButton(parent=self.componet_coordinates_groupbox)
        self.delete_component_button.setObjectName("delete_component_button")
        self.verticalLayout_4.addWidget(self.delete_component_button)
        
        self.load_from_file_button = QtWidgets.QPushButton(parent=self.componet_coordinates_groupbox)
        self.load_from_file_button.setObjectName("load_from_file_button")
        self.verticalLayout_4.addWidget(self.load_from_file_button)

class ImagePointsGroup:
    def __init__(self, parent):
        self.take_image_points_groupbox = QtWidgets.QGroupBox(parent=parent)
        self.take_image_points_groupbox.setMinimumSize(QtCore.QSize(190, 320))
        self.take_image_points_groupbox.setObjectName("take_image_points_groupbox")
        
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.take_image_points_groupbox)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        
        self.take_image_points_display_area = QtWidgets.QScrollArea(parent=self.take_image_points_groupbox)
        self.take_image_points_display_area.setWidgetResizable(True)
        self.take_image_points_display_area.setObjectName("take_image_points_display_area")
        
        self.scrollAreaWidgetContents = QtWidgets.QWidget()
        self.scrollAreaWidgetContents.setGeometry(QtCore.QRect(0, 0, 164, 407))
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.take_image_points_display_area.setWidget(self.scrollAreaWidgetContents)
        self.verticalLayout_3.addWidget(self.take_image_points_display_area)
        
        self.add_point_button = QtWidgets.QPushButton(parent=self.take_image_points_groupbox)
        self.add_point_button.setObjectName("add_point_button")
        self.verticalLayout_3.addWidget(self.add_point_button)
        
        self.delete_point_button = QtWidgets.QPushButton(parent=self.take_image_points_groupbox)
        self.delete_point_button.setObjectName("delete_point_button")
        self.verticalLayout_3.addWidget(self.delete_point_button)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1276, 539)
        MainWindow.setMaximumSize(QtCore.QSize(1920, 1080))
        
        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        
        self.gridLayout = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName("gridLayout")
        
        self._create_widget_groups()
        self._arrange_layout()
        
        MainWindow.setCentralWidget(self.centralwidget)
        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def _create_widget_groups(self):
        self.camera_settings = CameraSettingsGroup(self.centralwidget)
        self.joystick = JoystickGroup(self.centralwidget)
        self.cnc_settings = CncSettingsGroup(self.centralwidget)
        self.component_coordinates = ComponentCoordinatesGroup(self.centralwidget)
        self.image_points = ImagePointsGroup(self.centralwidget)
        
        self.image_displayer = QtWidgets.QWidget(parent=self.centralwidget)
        self.image_displayer.setMinimumSize(QtCore.QSize(480, 320))
        self.image_displayer.setObjectName("image_displayer")

    def _arrange_layout(self):
        self.gridLayout.addWidget(self.image_displayer, 0, 0, 1, 1)
        self.gridLayout.addWidget(self.joystick.joystic_groupbox, 0, 1, 1, 1)
        self.gridLayout.addWidget(self.camera_settings.camera_settings_groupbox, 1, 0, 1, 1)
        self.gridLayout.addWidget(self.cnc_settings.cnc_settings_groupbox, 1, 1, 1, 1)
        self.gridLayout.addWidget(self.image_points.take_image_points_groupbox, 0, 2, 2, 1)
        self.gridLayout.addWidget(self.component_coordinates.componet_coordinates_groupbox, 0, 3, 2, 1)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        
        self.camera_settings.camera_settings_groupbox.setTitle(_translate("MainWindow", "Настройки камеры"))
        self.camera_settings.label.setText(_translate("MainWindow", "Порт"))
        self.camera_settings.camera_port_lineEdit.setText(_translate("MainWindow", "/dev/video4"))
        self.camera_settings.label_2.setText(_translate("MainWindow", "Режим работы"))
        self.camera_settings.connect_camera_button.setText(_translate("MainWindow", "подключить"))
        
        self.joystick.up50_button.setText(_translate("MainWindow", "50"))
        self.joystick.up10_button.setText(_translate("MainWindow", "10"))
        self.joystick.up_1_button.setText(_translate("MainWindow", "1 "))
        self.joystick.left_50_button.setText(_translate("MainWindow", "<-50"))
        self.joystick.left_10_button.setText(_translate("MainWindow", "<-10"))
        self.joystick.left_1_button.setText(_translate("MainWindow", "<-1"))
        self.joystick.right_1_button.setText(_translate("MainWindow", "1->"))
        self.joystick.right_10_button.setText(_translate("MainWindow", "10->"))
        self.joystick.right_50_button.setText(_translate("MainWindow", "50->"))
        self.joystick.pushButton_4.setText(_translate("MainWindow", "1 V"))
        self.joystick.pushButton_5.setText(_translate("MainWindow", "10 V"))
        self.joystick.pushButton_6.setText(_translate("MainWindow", "50 V"))
        self.joystick.pushButton.setText(_translate("MainWindow", "zero X"))
        self.joystick.pushButton_2.setText(_translate("MainWindow", "zero Y"))
        self.joystick.pushButton_3.setText(_translate("MainWindow", "zero"))
        self.joystick.label_4.setText(_translate("MainWindow", "X = "))
        self.joystick.label_5.setText(_translate("MainWindow", "Y ="))
        
        self.cnc_settings.cnc_settings_groupbox.setTitle(_translate("MainWindow", "Настройки контроллера станка"))
        self.cnc_settings.port_label.setText(_translate("MainWindow", "Порт"))
        self.cnc_settings.port_lineEdit.setText(_translate("MainWindow", "/dev/ttyUSB0"))
        self.cnc_settings.connect_cnc_button.setText(_translate("MainWindow", "подключить"))
        
        self.component_coordinates.componet_coordinates_groupbox.setTitle(_translate("MainWindow", "Координаты компонентов"))
        self.component_coordinates.add_button.setText(_translate("MainWindow", "Добавить"))
        self.component_coordinates.delete_component_button.setText(_translate("MainWindow", "Удалить"))
        self.component_coordinates.load_from_file_button.setText(_translate("MainWindow", "Загрузить файл"))
        
        self.image_points.take_image_points_groupbox.setTitle(_translate("MainWindow", "Точки съёмки"))
        self.image_points.add_point_button.setText(_translate("MainWindow", "добавить"))
        self.image_points.delete_point_button.setText(_translate("MainWindow", "удалить"))

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec())