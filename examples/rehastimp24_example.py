import time

from pyScienceMode2 import Channel, Point
from pyScienceMode2 import RehastimP24 as St

"""
This example shows how to use the RehastimP24 device. 
There are several commands divided into three levels (general, low and mid).
You can't call commands from different levels, you must first close the current level
to be able to use commands from another one.
"""

# list which contains the channels you want to use
list_channels = []

# list which contains the points you want to use
list_stimulation_points = []

# Create an object channel
channel_1 = Channel(
    no_channel=1, name="Biceps", amplitude=40.1, pulse_width=500, frequency=30, device_type="RehastimP24"
)
channel_2 = Channel(
    mode="Doublet",
    no_channel=2,
    amplitude=40,
    pulse_width=500,
    name="Triceps",
    frequency=35,
    ramp=5,
    device_type="RehastimP24",
)
channel_3 = Channel(
    mode="Triplet",
    no_channel=3,
    amplitude=40,
    pulse_width=500,
    name="Triceps",
    frequency=15,
    ramp=15,
    device_type="RehastimP24",
)

# Create an object stimulator
stimulator = St(port="COM4", show_log="Partial")  # Enter the port on which the rehastim is connected

# Add the channels you want to stimulate to the list.
list_channels.append(channel_1)
list_channels.append(channel_2)
# list_channels.append(channel_3)

"""
General level commands. 
In this level you can get several information about the device.
"""

# stimulator.get_battery_status()
print(stimulator.get_stim_status())
# stimulator.get_main_status()
# stimulator.get_all()
# stimulator.reset()

"""
Low level commands.
In this level you can configure a custom shape pulse. You can stimulate only one channel.
This is useful for the execution of stimulation pulses with a high frequency.
"""

# Create a point with the configuration you want to create your own shape pulse.
point1 = Point(500, 20)
point2 = Point(500, -20)
point3 = Point(500, 10)
point4 = Point(500, -10)


# Add the points you want to use to the list
list_stimulation_points.append(point1)
list_stimulation_points.append(point2)
list_stimulation_points.append(point3)
list_stimulation_points.append(point4)


"""
Start the ll stimulation with the list of points provided. 
It is possible to update the parameters of the point by giving a new list of points.
If you set the safety flag to False, it will not check if the stimulation points  provided are symmetrical
for a muscle loading and unloading phase. 
"""

stimulator.stim_start_one_channel_stimulation(no_channel=1, points=list_stimulation_points, stim_sequence=500, pulse_interval=10)

# You can update the configuration of the point during the stimulation.
point1.set_amplitude(30)
point1.set_pulse_width(350)
point2.set_amplitude(-30)
point2.set_pulse_width(350)
point3.set_amplitude(20)
point3.set_pulse_width(350)
point4.set_amplitude(-20)
point4.set_pulse_width(350)

# Restart the stimulation with the new point configuration.
stimulator.update_stim_one_channel(upd_list_point=list_stimulation_points)

"""
Stop the ll stimulation and leave the low level but it does not disconnect the Pc and the RehastimP24.
"""
stimulator.ll_stop()

"""
Mid level commands. 
In this level you can define a stimulation pattern. You can stimulate several channels at the same time
"""

"""
Initialize the channels list given. Use it before starting the stimulation or after stopping it.
Open the mid level stimulation.
"""
stimulator.init_stimulation(list_channels=list_channels)

"""
If you want to create your own shape pulse, you can create and pilot stimulation points.
16 max per channels.
Otherwise, you can use the default biphasic shape pulse mode="Single" or "Doublet" or "Triplet".
"""

point1 = channel_1.add_point(3000, 20)
point2 = channel_1.add_point(3000, -20)
point3 = channel_1.add_point(3000, 20)
point4 = channel_1.add_point(3000, -20)

# point5 = channel_2.add_point(100, 15)
# point6 = channel_2.add_point(100, -15)

"""
Start the stimulation with the list of channels provided for 5s.
If you set the safety flag to False, it will not  check if the stimulation points provided are symmetrical
for a muscle loading and unloading phase. 
"""

stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=3.5, safety=False)

# You can modify some parameters during the stimulation.
# if you have chosen the default shape pulse (single,doublet,triplet), you can modify the amplitude and the pulse width.
channel_2.set_amplitude(15)
channel_2.set_pulse_width(500)
channel_2.set_frequency(10)

# If you have created your own shape pulse, you can modify the amplitude and the pulse width of the points.
# You can also create new points during the stimulation.
point1.set_amplitude(10)
point2.set_amplitude(-10)
point5 = channel_1.add_point(500, 15)
point6 = channel_1.add_point(500, -15)
point7 = channel_1.add_point(500, -15)

"""
Restart the stimulation with the new point configuration for 5s.
"""
stimulator.update_stimulation(upd_list_channels=list_channels, stimulation_duration=5)

"""
Stop the stimulation and leave the mid level but it does not disconnect the Pc and the RehastimP24.
To restart a stimulation you have to initialize the level again
"""
stimulator.end_stimulation()

"""
Close the port and disconnect the Pc and the RehastimP24.
"""
stimulator.close_port()
