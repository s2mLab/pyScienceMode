import time
from pyScienceMode2.motomed_interface import Motomed

port = "/dev/ttyUSB0"
motomed = Motomed(port)
# time.sleep(5)
# print(motomed.get_motomed_mode())
# time.sleep(2)
# motomed.init_phase_training(arm_training=True)
# time.sleep(10)
# motomed.start_phase(speed=20, gear=5, passive=True)
# time.sleep(25)
# motomed.stop_training()
# motomed.start_phase(gear=1, speed=20)
motomed.start_basic_training(arm_training=True)
time.sleep(5)
motomed.set_speed(12)
motomed.set_gear(8)
time.sleep(8)
motomed.pause_training()
time.sleep(8)
motomed.continue_training()
time.sleep(8)
motomed.stop_training()
motomed.disconnect()

# motomed.debug_reha_show_com = False
