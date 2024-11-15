import time
from pysciencemode import Rehastim2

port = "/dev/ttyUSB0"  # Enter the port on which the stimulator is connected

motomed = Rehastim2(port, show_log=True, with_motomed=True).motomed
motomed.init_phase_training(arm_training=True)
print(motomed.get_motomed_mode())
motomed.start_phase(
    speed=50, gear=5, active=False, go_forward=False, spasm_detection=True
)
time.sleep(2)
motomed.set_gear(10)
time.sleep(200)
motomed.stop_training()
print(motomed.get_phase_result())
