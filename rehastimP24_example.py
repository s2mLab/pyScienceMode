from time import sleep,time
from pyScienceMode2 import Channel as Ch
from sciencemode import sciencemode
from pyScienceMode2.rehastimp24_interface import StimulatorP24 as St

# list which contains the channels you want to use
list_channels = []

# Create an object channel

channel_1 = Ch.Channel(mode="Single", no_channel=1, amplitude=20, pulse_width=100, name="Biceps", device_type="RehastimP24", period=10)

list_channels.append(channel_1)

stimulator = St(port="COM4", show_log=True, device_type="RehastimP24")

sleep(1)

# Init the stimulation. Use it before starting the stimulation or after stopping it.

stimulator.init_stimulation(list_channels=list_channels)

# Add points with the configuration you want to create your shape pulse

channel_1.add_point(100, 10)
channel_1.add_point(100, 20)


stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=10)

stimulator.stop_stimulation()

stimulator.close_port()
