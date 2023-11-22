"""
Test for file IO.
"""

from typing import Callable
import numpy as np
import pytest
from pyScienceMode2 import RehastimP24 as Stp24
from pyScienceMode2 import Rehastim2 as St2
from pyScienceMode2 import Channel, Point, Device, Modes
from time import sleep




# brancher le channel 1 à un boitier de stim ou sur la peau, puis lancer le test. Pendant le test, retirer l'électrode
#modifier le port au besoin
@pytest.mark.parametrize("instant", ["while","begining"])
@pytest.mark.parametrize("port", ["COM4"])
def test_electrode_error_p24(instant,port):
    """
    Prepare and solve and animate a reaching task ocp #TODO change the docstring
    """

    stimulator = Stp24(port=port, show_log="Status")
    list_channels = []
    channel_number = 1
    channel_1 = Channel( mode=Modes.SINGLE,
        no_channel=channel_number, amplitude=20, pulse_width=300, frequency=10, device_type=Device.Rehastimp24
    )
    list_channels.append(channel_1)
    stimulator.init_stimulation(list_channels = list_channels)
    if instant == "while":
        with pytest.raises(
                RuntimeError,
                match=f"Electrode error on channel {channel_number}"
        ):
            while 1:
                stimulator.start_stimulation(upd_list_channels=list_channels,stimulation_duration=20, safety=True)

    elif instant == "begining" :
        with pytest.raises(
                RuntimeError,
                match=f"Electrode error on channel {channel_number}"
        ):
            stimulator.start_stimulation(upd_list_channels=list_channels,stimulation_duration=1, safety=True)
    # sleep(1)
    stimulator.close_port()