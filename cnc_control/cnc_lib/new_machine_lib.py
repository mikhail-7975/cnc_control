import serial
import time
import logging


class CncMachineDriver:
    
    BAUD_RATE = 115200
    TIMEOUT = 2

    # Ограничения по координатам (мм)
    X_MIN, X_MAX = -1000, 1000
    Y_MIN, Y_MAX = -1000, 1000

    def __init__(self, port, baud_rate, timeout):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.serial_port_object = None
        self.logger = logging.getLogger("CncMachineDriver")
        logging.basicConfig(level=logging.INFO)

        self.X = 0
        self.Y = 0

    def __enter__(self):
        self.open_serial_port()
        self.unlock()

        self._send_gcode("$RST=#")           
        self._send_gcode("G10 P0 L20 X0 Y0") 
        self.set_units_and_mode()
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.home()
        time.sleep(1)
        self._send_gcode("$H")
        self.close_serial_port()

    # --- Подключение ---
    def open_serial_port(self):
        if not self.serial_port_object or not self.serial_port_object.is_open:
            self.serial_port_object = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout
            )
            time.sleep(2)
            self.logger.info("Serial port opened.")
        else:
            self.logger.info("Serial port already open.")

    def close_serial_port(self):
        if self.serial_port_object and self.serial_port_object.is_open:
            self.serial_port_object.close()
            self.logger.info("Serial port closed.")

    # --- Настройка GRBL ---
    def unlock(self):
        """Разблокировка GRBL"""
        self._send_gcode("$H")
        self._log_response("GRBL Unlock")

    def set_units_and_mode(self):
        """Устанавливаем миллиметры и абсолютные координаты"""
        self._send_gcode("G21")  # миллиметры
        self._send_gcode("G90")  # абсолютный режим
        self._log_response("Units = mm, Absolute mode")

    # --- Основные команды движения ---
    def move_x(self, x_mm, speed=7000):
        command = f"G1 X{x_mm} F{speed}"
        self._execute_move(command)
        self.X = x_mm

    def move_y(self, y_mm, speed=7000):
        command = f"G1 Y{y_mm} F{speed}"
        self._execute_move(command)
        self.Y = y_mm

    def move_xy(self, x_mm, y_mm, speed=7000):
        command = f"G1 X{x_mm} Y{y_mm} F{speed}"
        self._execute_move(command)
        self.X, self.Y = x_mm, y_mm

    # --- Относительное перемещение ---
    def move_x_rel(self, dx_mm, speed=7000):
        self._send_gcode("G21")
        self._send_gcode("G91")
        command = f"G1 X{dx_mm} F{speed}"
        self._execute_move(command)
        self.X += dx_mm
        self._send_gcode("G90")

    def move_y_rel(self, dy_mm, speed=7000):
        self._send_gcode("G21")
        self._send_gcode("G91")
        command = f"G1 Y{dy_mm} F{speed}"
        self._execute_move(command)
        self.Y += dy_mm
        self._send_gcode("G90")

    def move_xy_rel(self, dx_mm, dy_mm, speed=7000):
        self._send_gcode("G21")
        self._send_gcode("G91")
        command = f"G1 X{dx_mm} Y{dy_mm} F{speed}"
        self._execute_move(command)
        self.X += dx_mm
        self.Y += dy_mm
        self._send_gcode("G90")

    # --- Домашнее положение ---
    def home(self):
        self._send_gcode("$H")
        # self._wait_for_idle()
        self.X, self.Y = 0, 0

    def _execute_move(self, command):
        self._send_gcode(command)
        self._send_gcode("M400")  # Ждём окончания движения
        self._wait_for_idle()
        self._log_response("Movement complete")

    def _wait_for_idle(self, timeout=5):
        start_time = time.time()
        while time.time() - start_time < timeout:
            self._send_gcode("?")
            time.sleep(0.2)
            responses = self._read_response()
            print("DEBUG", responses)
            for line in responses:
                self.logger.info(f"[STATUS] {line}")   # Показываем ответ GRBL
            
                if line.startswith("<Idle"):
                    self.logger.info("GRBL is Idle. Movement complete.")
                    return
                if "ALARM" in line:
                    self.logger.info("Stopper is reached.")
                    return
        raise TimeoutError("GRBL did not return to Idle state")
    
    def _send_gcode(self, command):
        self.serial_port_object.write((command + '\n').encode())
        self.logger.info(f"[SEND] {command}")

    def _read_response(self, wait_time=0.5):
        """Чтение ответа от GRBL"""
        responses = []
        time.sleep(wait_time)   # Даем GRBL время ответить
        while self.serial_port_object.in_waiting:
            line = self.serial_port_object.readline().decode('utf-8').strip()
            if line:
                responses.append(line)
        return responses
    
    def _log_response(self, context=""):
        responses = self._read_response()
        for res in responses:
            self.logger.info(f"[RESP][{context}] {res}")

