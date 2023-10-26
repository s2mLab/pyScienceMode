from time import sleep,time
from pyScienceMode2 import Channel as Ch
from pyScienceMode2.rehastimp24_interface import StimulatorP24 as St
from pyScienceMode2.Channel import Point

# list which contains the channels you want to use
list_channels = []

# list which contains the points you want to use
list_stimulation_points = []

# Create an object channel

channel_1 = Ch.Channel(mode="Single", no_channel=1, name="Biceps", frequency=50, device_type="RehastimP24") #TODO : function for single doublet and triplet
channel_2 = Ch.Channel(mode="Single", no_channel=2, name="Triceps", frequency=30, device_type="RehastimP24")

list_channels.append(channel_1)
list_channels.append(channel_2)

stimulator = St(port="COM4", show_log=True) #TODO: Try to put the device_type in the rehastimp24_interface

# stimulator.get_extended_version()
# stimulator.get_devide_id()
# stimulator.get_battery_status()
# stimulator.get_stim_status()
# stimulator.get_main_status()
# stimulator.reset()

stimulator.ll_init()

point1 = Point(100, 10)
point2 = Point(100, 10)
point3 = Point(100, -10)

list_stimulation_points.append(point1)
list_stimulation_points.append(point2)
list_stimulation_points.append(point3)

stimulator.start_ll_channel_config(no_channel=2, points=list_stimulation_points,stim_sequence=10, pulse_interval=500)

point1.set_amplitude(15)
point1.set_pulse_width(200)
point2.set_amplitude(15)
point2.set_pulse_width(200)
point3.set_amplitude(-15)
point3.set_pulse_width(200)

stimulator.update_ll_channel_config(upd_list_point=list_stimulation_points)

stimulator.ll_stop()
# Init the stimulation. Use it before starting the stimulation or after stopping it.

stimulator.init_stimulation(list_channels=list_channels)

# Add points with the configuration you want to create your shape pulse
# 16 max per channels

point1 = channel_1.add_point(100, -15)
point2 = channel_1.add_point(100, 15)

channel_2.add_point(100, 15)
channel_2.add_point(100, -15)

stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=10)
"""
You can change the configuration of the channel during the stimulation.
"""
channel_1.set_frequency(100)
channel_1.set_amplitude(15)
channel_1.set_pulse_width(200)
point1.set_amplitude(10)
point2.set_amplitude(-10)

stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=5)

stimulator.stop_stimulation()
stimulator.close_port()
