# Import Stimulator class
from pyScienceMode2 import Stimulator as St
# Import Channel class
from pyScienceMode2 import Channel as Ch

import time

# Create a list of channel
list_channels = []

# Create all channels possible
channel_1 = Ch.Channel('Single', 1, 2, 20, 100, 10, 10, 'Biceps')

channel_2 = Ch.Channel()
channel_2.set_mode('Single')
channel_2.set_no_channel(2)
channel_2.set_amplitude(2)
channel_2.set_frequency(20)
channel_2.set_pulse_width(100)
channel_2.set_stimulation_interval(10)
channel_2.set_inter_pulse_interval(10)
channel_2.set_name('Triceps')

channel_3 = Ch.Channel('Single', 3, 2, 20, 100, 11, 10)
channel_4 = Ch.Channel('Single', 4, 2, 20, 100, 10, 10)
channel_5 = Ch.Channel('Single', 5, 2, 20, 100, 10, 10)
channel_6 = Ch.Channel('Single', 6, 2, 20, 100, 10, 10)
channel_7 = Ch.Channel('Single', 7, 2, 20, 100, 10, 10)
channel_8 = Ch.Channel('Single', 8, 2, 20, 100, 10, 10)

# Choose which channel will be used, Warning channel 2 and 4 are not working
list_channels.append(channel_1)
list_channels.append(channel_3)
list_channels.append(channel_5)
list_channels.append(channel_6)
list_channels.append(channel_8)

# Create our object Stimulator
stimulator = St.Stimulator(list_channels, 'COM4')

# Show the log, by default True if called, to deactivate : stimulator.show_log(False)
stimulator.show_log()

# Initialise all Channels, True by default
# All channels that will be used during the test needs to be initialised, to simplify always call
# initialise_all_channels()
stimulator.initialise_all_channels()

# Start the stimulation with the given parameters
# Possible to stop the stimulation after a given time with start_stimulation(time), if used, start_stimulation must be
# used again.
stimulator.start_stimulation()

# Modify some parameters,
list_channels[2].amplitude = 10
list_channels.append(channel_7)

# Wait a given time in seconds
time.sleep(5)

# Update the parameters of the stimulation
stimulator.update_stimulation(list_channels)

# Wait a given time in seconds
time.sleep(5)

# Stop the stimulation
stimulator.stop_stimulation()

# Disconnect the Rehastim, stop sending watchdog
stimulator.disconnect()

time.sleep(2)

# It is possible to restart a stimulation, the program automatically connect to the Rehastim
stimulator.start_stimulation()
time.sleep(10)

# Stimulator.disconnect() must be called in order to finish the program and stop send watchdog.
stimulator.disconnect()
