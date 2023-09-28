# Import Stimulator class
from pyScienceMode2.rehastim_interface import Stimulator as St

# Import Channel class
from pyScienceMode2 import Channel as Ch

from time import time,sleep

list_channels = []

channel_1 = Ch.Channel(
  mode="Single", no_channel=1, amplitude=15, pulse_width=300, enable_low_frequency=False, name="Biceps"
 )
# channel_2 = Ch.Channel( mode="Single", no_channel=1, amplitude=30, pulse_width=300, name="Biceps_recorded")

list_channels.append(channel_1)
# list_channels.append(channel_2)
# list_channels.append(channel_3)
# list_channels.append(channel_5)
# list_channels.append(channel_6)
# list_channels.append(channel_7)
# list_channels.append(channel_8)

# Create our object Stimulator
stimulator = St(
    port="COM3",
    show_log=True,
)

# stimulator.init_channel(stimulation_interval=33, list_channels=list_channels)
end_time = time() + 6

while time() < end_time:
    stimulator.init_channel(stimulation_interval=33, list_channels=list_channels)
    stimulator.start_stimulation(stimulation_duration=1)
    sleep(1)
# #
# stimulator.init_channel(
# 
# *
# stimulation_interval=30, list_channels=list_channels)
# stimulator.start_stimulation(stimulation_duration=5)



stimulator.stop_stimulation()
stimulator.disconnect()
stimulator.close_port()
