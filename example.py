# Import Stimulator class
from pyScienceMode2 import Stimulator as St
# Import Channel class
from pyScienceMode2 import Channel as Ch

from time import sleep

# Create all channels possible
channel_1 = Ch.Channel(mode='Single', no_channel=1, amplitude=5, pulse_width=100, inter_pulse_interval=10,
                       name='Biceps')

channel_2 = Ch.Channel()
channel_2.set_mode('Single')
channel_2.set_no_channel(2)
channel_2.set_amplitude(2)
channel_2.set_pulse_width(100)
channel_2.set_inter_pulse_interval(10)
channel_2.set_name('Triceps')

channel_3 = Ch.Channel('Single', 3, 2, 100, 10)
channel_4 = Ch.Channel('Single', 4, 2, 100, 10)
channel_5 = Ch.Channel('Single', 5, 2, 100, 10)
channel_6 = Ch.Channel('Single', 6, 2, 100, 10)
channel_7 = Ch.Channel('Single', 7, 2, 100, 10)
channel_8 = Ch.Channel('Single', 8, 2, 100, 10)

# Choose which channel will be used
list_channels.append(channel_1)
list_channels.append(channel_3)
list_channels.append(channel_5)
list_channels.append(channel_6)
list_channels.append(channel_7)
list_channels.append(channel_8)

# Create our object Stimulator
stimulator = St.Stimulator(list_channels=list_channels, stimulation_interval=1000, port_path='COM4')

# Display log, communication or/and watchdog, by default True if called, to deactivate : stimulator.show_log(False)
stimulator.show_log()
# stimulator.show_com()
# stimulator.show_watchdog()

"""
Initialise the channels given.
It is possible to modify the list of channels and the stimulation interval
"""
stimulator.init_channel()
# stimulator.init_channel(stimulation_interval=200, list_channels=nv_list_channel)

"""
Start the stimulation.
It is possible to :
- Give a time after which the stimulation will be stopped but not disconnected.
- Update the parameters of the channel by giving a new list of channels. The channel given must have been 
  initialised first.
"""
stimulator.start_stimulation()
# stimulator.start_stimulation(stimulation_duration=10, upd_list_channels=nw_list_channel)

# Modify some parameters,
list_channels[2].amplitude = 10
list_channels[3].amplitude = 15

# Wait a given time in seconds
sleep(1)

# Update the parameters of the stimulation
stimulator.start_stimulation(upd_list_channels=list_channels)

# Wait a given time in seconds
sleep(5)

"""
Stop the stimulation. But does not disconnect the Pc and the Rehastim.
"""
stimulator.stop_stimulation()

"""
Restart a stimulation with the same parameter for 2 seconds.
"""
stimulator.start_stimulation(stimulation_duration=2)

"""
The method init_channel must be called to update the stimulation interval (period).
"""
stimulator.init_channel(stimulation_interval=10)
stimulator.start_stimulation(stimulation_duration=2)

"""
To disconnect the computer and the Rehastim, use the disconnect method.
"""
stimulator.disconnect()

"""
After a disconnection, init_channel must be called.  
"""
stimulator.init_channel(stimulation_interval=15)
stimulator.start_stimulation(2, list_channels)
stimulator.disconnect()

"""
close_port method closes the serial port.
"""
stimulator.close_port()
