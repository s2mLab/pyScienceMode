"""
Test for file IO.
"""

import pytest
from pyScienceMode import RehastimP24 as Stp24
from pyScienceMode import Rehastim2 as St2
from pyScienceMode import Channel, Point, Device, Modes


# You will need to connect channel 1 to a stim box or to the skin, then start the test.
# If instant is "while" : Remove the electrode during the test to see the error message.
# If instant is "begining" : Remove the electrode before the test to see the error message.
# You can change the port if you want to test on another stimulator.

@pytest.mark.parametrize("instant", ["while", "begining"])
@pytest.mark.parametrize("port", ["COM4"])
def test_electrode_error_p24(instant, port):
    """
    Prepare and solve and animate a reaching task ocp #TODO change the docstring
    """

    stimulator = Stp24(port=port, show_log="Status")
    list_channels = []
    channel_number = 1
    channel_1 = Channel(mode=Modes.SINGLE,
                        no_channel=channel_number, amplitude=20, pulse_width=300, frequency=10,
                        device_type=Device.Rehastimp24
                        )
    list_channels.append(channel_1)
    stimulator.init_stimulation(list_channels=list_channels)
    if instant == "while":
        with pytest.raises(
                RuntimeError,
                match=f"Electrode error on channel {channel_number}"
        ):
            while 1:
                stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=20, safety=True)

    elif instant == "begining":
        with pytest.raises(
                RuntimeError,
                match=f"Electrode error on channel {channel_number}"
        ):
            stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=1, safety=True)
    # sleep(1)
    stimulator.close_port()


@pytest.mark.parametrize("port", ["COM4"])
def test_port_access_error(port):
    """
    Prepare and solve and animate a reaching task ocp #TODO change the docstring
    """
    stimulator = Stp24(port=port, show_log="Status")
    with pytest.raises(
            RuntimeError,
            match=f"Failed to access port {port}."
    ):
        stimulator.close_port()
    stimulator = Stp24(port=port, show_log="Status")
    with pytest.raises(
            RuntimeError,
            match=f"Unable to open port {port}."
    ):
        stimulator.close_port()


def test_no_stimulation_points_error():
    """
    Prepare and solve and animate a reaching task ocp #TODO change the docstring
    """
    stimulator = Stp24(port="COM4", show_log="Status")
    list_channels = []
    channel_number = 1
    channel_1 = Channel(no_channel=channel_number, amplitude=20, frequency=10,
                        device_type=Device.Rehastimp24)

    list_channels.append(channel_1)
    stimulator.init_stimulation(list_channels=list_channels)
    stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=0.5, safety=True)
    with pytest.raises(
            ValueError,
            match="No stimulation point provided for channel {}. "
                  "Please either provide an amplitude and pulse width for a biphasic stimulation."
                  "Or specify specific stimulation points.".format(channel_1._no_channel)
    ):
        stimulator.close_port()


def test_symmetric_error():
    """
    Prepare and solve and animate a reaching task ocp #TODO change the docstring
    """
    stimulator = Stp24(port="COM4", show_log="Status")
    list_channels = []
    channel_number = 1
    channel_1 = Channel(no_channel=channel_number, amplitude=20, frequency=10,
                        device_type=Device.Rehastimp24)

    list_channels.append(channel_1)
    channel_1.add_point(20, 350)
    stimulator.init_stimulation(list_channels=list_channels)
    stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=0.5, safety=True)
    with pytest.raises(
            ValueError,
            match=f"Pulse for channel {channel_1._no_channel} is not symmetric.\n"
                  f"Polarization and depolarization must have the same area.\n"
                  f"Or set safety=False in start_stimulation."
    ):
        stimulator.close_port()


def test_no_stimulation_duration_error():
    """
    Prepare and solve and animate a reaching task ocp #TODO change the docstring
    """
    stimulator = Stp24(port="COM4", show_log="Status")
    list_channels = []
    channel_number = 1
    channel_1 = Channel(mode=Modes.SINGLE,
                        no_channel=channel_number, amplitude=20, pulse_width=300, frequency=10,
                        device_type=Device.Rehastimp24
                        )

    list_channels.append(channel_1)
    stimulator.init_stimulation(list_channels=list_channels)
    stimulator.start_stimulation(upd_list_channels=list_channels, safety=True)
    with pytest.raises(
            ValueError,
            match="Please indicate the stimulation duration"
    ):
        stimulator.close_port()


def test_channel_list_empty() :

    stimulator = Stp24(port="COM4", show_log="Status")
    list_channels = []
    stimulator.init_stimulation(list_channels=list_channels)
    with pytest.raises(
            ValueError,
            match="Please provide at least one channel for stimulation."
    ):
        stimulator.close_port()


def test_not_channel_instance_error() :

    stimulator = Stp24(port="COM4", show_log="Status")
    list_channels = [1]
    index = 0
    with pytest.raises(
            TypeError,
            match=f"Item at index {index} is not a Channel instance, got {type(list_channels[index]).__name__} "
                  f"type instead."
    ):
        stimulator.init_stimulation(list_channels=list_channels)
        stimulator.close_port()

