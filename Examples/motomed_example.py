import time

from pyScienceMode import logger
from pyScienceMode.devices.rehastim2 import Rehastim2


port = "/dev/ttyUSB0"  # Enter the port on which the stimulator is connected

motomed = Rehastim2(port, show_log=True, with_motomed=True).motomed
motomed.init_phase_training(arm_training=True)
logger.info(motomed.get_motomed_mode())
motomed.start_phase(speed=50, gear=5, active=False, go_forward=False, spasm_detection=True)
time.sleep(2)
motomed.set_gear(10)
time.sleep(200)
motomed.stop_training()
logger.info(motomed.get_phase_result())
