import time

from pyScienceMode2.Stimulator import Motomed
import numpy as np
import serial

BAUD_RATE = 460800
port = "/dev/ttyUSB0"
# port = serial.Serial(port, BAUD_RATE, bytesize=serial.EIGHTBITS, parity=serial.PARITY_EVEN,
#                           stopbits=serial.STOPBITS_ONE, timeout=0.1)
# while 1:
#     print(port.read(port.inWaiting()))
#     time.sleep(1)
motomed = Motomed(port)
print(motomed.get_motomed_mode())
motomed.debug_reha_show_com = False
