import time
from pyScienceMode2.rehastim_interface import Stimulator

"""
This example show how to control the Motomomed device using the Rehastim interface.
"""

port = "/dev/ttyUSB0" # Change this to the port of your computer

# Create a Stimulator object to control the rehastim device
# 'show_log=True' enables logging for communication messages
# 'with_motomed=True' indicates that you want to control a Motomed device.
motomed = Stimulator(port, show_log=True, with_motomed=True).motomed

# Initialize the phase training of the Motomed device specifying that you want to train the arm
motomed.init_phase_training(arm_training=True)

# You can print the current mode of the Motomed device
print(motomed.get_motomed_mode())

# Start the training with a speed of 50, a gear of 5, the spasm detection activated and the direction of the movement is backward
# You can modify the settings  with the set_speed(), set_gear(), set_spasm_detection() and set_direction() methods
motomed.start_phase(speed=50, gear=5, active=False, go_forward=False, spasm_detection=True)

# Pause the training for 2 seconds
time.sleep(2)

# Change the gear to 10
motomed.set_gear(10)

# Pause for 200 seconds
time.sleep(200)

# Stop the training
motomed.stop_training()

# Print the result of the training
print(motomed.get_phase_result())
