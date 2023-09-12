import time
from pyScienceMode2.rehastim_interface import Stimulator as St
from pyScienceMode2 import Channel as Ch

"""
This example shows how to use the Rehastim stimulator with the Motomed.
"""

def init_rehastim():
    """
    This function initialize the stimulator and the channels

    Returns
    -------
    stimulator : Stimulator
        The stimulator object
    list_channels : list
        The list of channels
    """
    # Create a list of channels
    list_channels = []

    # Create all channels possible.
    channel_1 = Ch.Channel(mode="Single", no_channel=1, amplitude=10, pulse_width=100, name="Biceps")
    channel_2 = Ch.Channel(mode="Single", no_channel=2, amplitude=8, pulse_width=100, name="delt_ant")
    channel_3 = Ch.Channel(mode="Single", no_channel=3, amplitude=8, pulse_width=100, name="Triceps")
    channel_4 = Ch.Channel(mode="Single", no_channel=4, amplitude=9, pulse_width=100, name="delt_post")

    # Choose which channel will be used. Comment the channel you don't want to use.
    list_channels.append(channel_1)
    list_channels.append(channel_2)
    list_channels.append(channel_3)
    list_channels.append(channel_4)

    # Create our object Stimulator
    stimulator = St(port="COM3", with_motomed=True, show_log=True) # port="COM3" for windows, port="/dev/ttyACM0" for linux
    stimulator.init_channel(stimulation_interval=20, list_channels=list_channels, low_frequency_factor=0)

    return stimulator, list_channels


if __name__ == "__main__":
    # Initialize the stimulator and the motomed object.
    stimulator, list_channels = init_rehastim()
    motomed = stimulator.motomed

    # Set the amplitude of the channels. The amplitude is in mA.
    list_channels[0].set_amplitude(10)
    list_channels[1].set_amplitude(10)
    list_channels[2].set_amplitude(10)
    list_channels[3].set_amplitude(10)

    # Start basic training with arm stimulation.
    motomed.start_basic_training(arm_training=True)

    # Start stimulation with the list of channels used
    stimulator.start_stimulation(upd_list_channels=list_channels)

    # Set the speed of the motomed.
    motomed.set_speed(20)

    bic_delt_stim = False
    tric_delt_stim = False

    while 1:
        # Get the angle of the crank.
        angle_crank = motomed.get_angle()

        # Check angle range for stopping stimulation.
        if (10 <= angle_crank < 20 or 180 <= angle_crank < 220) and (tric_delt_stim or bic_delt_stim):
            stimulator.stop_stimulation()
            tric_delt_stim, bic_delt_stim = False, False
            print("angle crank", angle_crank)
            print("stimulation_state", (tric_delt_stim or bic_delt_stim))

        # Check angle range for triceps and deltoid stimulation.
        if 20 <= angle_crank < 180 and not tric_delt_stim:
            list_channels[2].set_amplitude(7)
            list_channels[3].set_amplitude(15)
            stimulator.start_stimulation(upd_list_channels=list_channels)
            tric_delt_stim = True
            bic_delt_stim = False
            print("angle crank", angle_crank)
            print("stimulation_state", tric_delt_stim)

        # Check angle range for biceps and deltoid stimulation.
        if (220 <= angle_crank < 360 or 0 <= angle_crank < 10) and not bic_delt_stim:
            upd_list = list_channels[:2]
            stimulator.start_stimulation(upd_list_channels=upd_list)
            bic_delt_stim = True
            tric_delt_stim = False
            print("angle crank", angle_crank)
            print("stimulation_state", bic_delt_stim)

        # Wait 10ms.
        time.sleep(0.01)
