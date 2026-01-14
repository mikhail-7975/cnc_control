from cnc_control.core.cnc.drivers.grbl_driver import CncMachineDriver
from cnc_control.core.camera.camera_reader import ThreadSafeCameraReader
import time
import os
import re
import ast
import cv2
from PIL import Image
import msvcrt


ETALON_PATH = "C:\\Users\\nikgl\Desktop\\neurolumber\\cnc_3\\cnc_control\\plates\\plate_4\\etalon"

plate_x = 6
plate_y = 5

driver = CncMachineDriver('COM10', baud_rate = 115200, timeout = 2)
driver.open_serial_port()
driver.unlock()
driver.set_units_and_mode()

cam = ThreadSafeCameraReader(camera_id=1, res_mode = '1080', photo_mode = 'etalon')
time.sleep(2)
with open("C:\\Users\\nikgl\\Desktop\\neurolumber\\cnc_3\\cnc_control\\plates\\plate_4\\keypoints.txt", encoding="utf-8") as f:
    lines = f.readlines()
places = []

for line in lines:
    # print(line)
    x, y = ast.literal_eval(line)
    places.append((x, y))

curr_x = 0
curr_y = 0

# msvcrt.getch()

start_plate_y = 0
start_plate_x = 0
# time.sleep(5)
print('started')
for i, place in enumerate(places):
    delation = 0.1
    if i == 0 or i % 7 ==0  :
        delation = 5
    print('moving to ', place[0], place[1])
    driver.move_y(place[1]-50)
    driver.move_x(place[0])
    time.sleep(delation)        

    frame = cam.get_image()
    cv2.imwrite(ETALON_PATH + f'\\photo_{int(place[0])}_{int(place[1])}.png', frame)
    start_plate_x += 1
    curr_x = place[0]
    curr_y = place[1]


# driver.move_x_rel(-curr_x)
# driver.move_y_rel(-curr_y)
driver.close_serial_port()
