# Import Stimulator class
from pyScienceMode2 import Stimulator as St
# Import Channel class
from pyScienceMode2 import Channel as Ch

from time import time
from time import sleep
while 1:
    # Create a list of channel
    list_channels = []

    # Create all channels possible
    channel_1 = Ch.Channel(mode='Single', no_channel=1, amplitude=2, pulse_width=100, stimulation_interval=10,
                           inter_pulse_interval=10, name='Biceps')

    channel_2 = Ch.Channel()
    channel_2.set_mode('Single')
    channel_2.set_no_channel(2)
    channel_2.set_amplitude(2)
    channel_2.set_pulse_width(100)
    channel_2.set_stimulation_interval(10)
    channel_2.set_inter_pulse_interval(10)
    channel_2.set_name('Triceps')

    channel_3 = Ch.Channel('Single', 3, 2, 100, 11, 10)
    channel_4 = Ch.Channel('Single', 4, 2, 100, 10, 10)
    channel_5 = Ch.Channel('Single', 5, 2, 100, 10, 10)
    channel_6 = Ch.Channel('Single', 6, 2, 100, 10, 10)
    channel_7 = Ch.Channel('Single', 7, 2, 100, 10, 10)
    channel_8 = Ch.Channel('Single', 8, 2, 100, 10, 10)

    # Choose which channel will be used, Warning channel 2 and 4 are not working in our case
    list_channels.append(channel_1)
    list_channels.append(channel_3)
    list_channels.append(channel_5)
    list_channels.append(channel_6)
    list_channels.append(channel_7)
    list_channels.append(channel_8)

    # Create our object Stimulator
    stimulator = St.Stimulator(list_channels, 'COM4')

    # Show the log, by default True if called, to deactivate : stimulator.show_log(False)
    stimulator.show_log()
    # stimulator.show_com()

    # print("     Initialisation")
    # Start the stimulation with the given parameters
    # Possible to stop the stimulation after a given time with start_stimulation(time), if used, start_stimulation must be
    # used again.

    stimulator.init_channel()
    # n = 0
    # while n < 10:
    #     print(n % 2)
    #     if n % 2 == 0:
    #         stimulator.start_stimulation(stimulation_duration=1, wait_rehastim_response=False)
    #     else:
    #         stimulator.start_stimulation(stimulation_duration=1)
    #     sleep(3)
    #     n += 1

    stimulator.start_stimulation(stimulation_duration=1)
    # Modify some parameters,
    list_channels[2].amplitude = 10
    list_channels[3].amplitude = 15

    # print("     Wait for 5 sec")
    # Wait a given time in seconds
    sleep(1)

    # print("     Update signal")
    # Update the parameters of the stimulation
    stimulator.start_stimulation(upd_list_channels=list_channels)

    # Wait a given time in seconds
    # sleep(5)
    #
    # # Stop the stimulation
    # print("     Stop stimulation")
    stimulator.stop_stimulation()

    # print("     Wait 5 sec")
    sleep(1)

    # print("     Restart stimulation for 10 sec")
    # Disconnect the Rehastim, stop sending watchdog
    stimulator.start_stimulation(2)

    # print("     Disconnect")
    stimulator.disconnect()

    # print("     Sleep 2 sec")
    sleep(1)

    # print("     Init")
    stimulator.init_channel()

    # print("     Start for 5 sec")
    # It is possible to restart a stimulation, the program automatically connect to the Rehastim
    stimulator.start_stimulation(2, list_channels, False)

    # Stimulator.disconnect() must be called in order to finish the program and stop send watchdog.
    stimulator.disconnect()
    stimulator.close_port()
