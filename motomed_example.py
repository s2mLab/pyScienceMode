import time
from pyScienceMode2.rehastim_interface import Stimulator

port = "/dev/ttyUSB0"

motomed = Stimulator(port, show_log=True, with_motomed=True).motomed
while True:
    print(motomed.motomed_values)
    time.sleep(0.1)

# time.sleep(5)
# print(motomed.get_motomed_mode())
# time.sleep(2)
# motomed.init_phase_training(arm_training=True)
# time.sleep(10)
# motomed.start_phase(speed=20, gear=5, passive=True)
# time.sleep(25)
# motomed.stop_training()
# motomed.start_phase(gear=1, speed=20)
# motomed.start_basic_training(arm_training=True)
# while True:
#     print(motomed.motomed_values)
#     time.sleep(0.5)
time.sleep(5)
# motomed.set_direction(go_forward=False)
time.sleep(5)
motomed.set_speed(15)

# motomed.set_gear(8)
# # time.sleep(10)
# # print(motomed.motomed_values)
# time.sleep(2)
# motomed.pause_training()
# time.sleep(8)
# motomed.continue_training()
# time.sleep(8)
# motomed.stop_training()
# motomed.disconnect()

# motomed.debug_reha_show_com = False
