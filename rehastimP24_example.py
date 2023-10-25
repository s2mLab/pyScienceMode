from time import sleep,time
from pyScienceMode2 import Channel as Ch
from pyScienceMode2.rehastimp24_interface import StimulatorP24 as St

# list which contains the channels you want to use
list_channels = []

# Create an object channel

channel_1 = Ch.Channel(mode="Single", no_channel=1, name="Biceps", frequency=50,device_type="RehastimP24")
channel_2 = Ch.Channel(mode="Single", no_channel=2, name="Triceps", frequency=30, device_type="RehastimP24")

list_channels.append(channel_1)
list_channels.append(channel_2)

stimulator = St(port="COM4", show_log=True)

# stimulator.ll_init()

# Init the stimulation. Use it before starting the stimulation or after stopping it.

stimulator.get_extended_version()  # TODO : add all the get_extended_version data
stimulator.init_stimulation(list_channels=list_channels)

# Add points with the configuration you want to create your shape pulse

point1 = channel_1.add_point(100, -15)
point2 = channel_1.add_point(100, 15)

channel_2.add_point(100, 15)
channel_2.add_point(100, -15)

stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=10)

"""
You can change the configuration of the channel during the stimulation.
"""
# channel_1.set_frequency(100)
# channel_1.set_amplitude(15)
# channel_1.set_pulse_width(200)
# point1.set_amplitude(20)
# point2.set_amplitude(-20)

stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2)

stimulator.stop_stimulation()

stimulator.close_port()
