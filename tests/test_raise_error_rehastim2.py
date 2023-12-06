import pytest
from pyScienceMode import Rehastim2 as St2
from pyScienceMode import Channel, Point, Device, Modes


@pytest.mark.parametrize("port", ["COM3"])
def test_electrode_error(port):
    """
    Test if the electrode is not connected to the stimulator. You will need to connect the channel 1 to a stim box
    or directly to the skin. Then start the test and remove the electrode.
    You can chang the port if you want to test another stimulator
    """

    stimulator = St2(port=port, show_log=True)
    list_channels = []
    channel_number = 2
    ack = "Electrode error"
    channel_1 = Channel(mode=Modes.SINGLE,
                        no_channel=channel_number, amplitude=10, pulse_width=300,
                        device_type=Device.Rehastim2
                        )
    list_channels.append(channel_1)
    stimulator.init_channel(list_channels=list_channels, stimulation_interval=30)
    with pytest.raises(
            RuntimeError,
            match=f"Stimulation error"
    ):
        while 1:
            stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=10)


@pytest.mark.parametrize("port", ["COM3"])
def test_stimulation_duration_too_short(port):
    """
    Connect the electrode to the stimulator and start the test with a very short stimulation duration.
    """

    stimulator = St2(port="COM3", show_log=True)
    list_channels = []
    channel_number = 2
    channel_1 = Channel(mode=Modes.SINGLE,
                        no_channel=channel_number, amplitude=10, pulse_width=300,
                        device_type=Device.Rehastim2
                        )
    list_channels.append(channel_1)
    stimulator.init_channel(list_channels=list_channels, stimulation_interval=30)
    with pytest.raises(
            RuntimeError,
            match="Asked stimulation duration too short"
    ):
        stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=0.001)


@pytest.mark.parametrize("port", ["COM3"])
def test_channel_list_empty(port):
    """
    Test if no channel is provided in the init_stimulation.
    """

    stimulator = St2(port=port, show_log=True)
    list_channels = []
    with pytest.raises(
            ValueError,
            match="Please provide at least one channel for stimulation."
    ):
        stimulator.init_channel(list_channels=list_channels, stimulation_interval=30)


@pytest.mark.parametrize("port", ["COM3"])
def test_no_channel_instance_error(port):
    """
    Test if the channel list contains a non channel instance.
    """

    stimulator = St2(port=port, show_log=True)
    list_channels = [1]
    index = 0
    with pytest.raises(
            TypeError,
            match=f"Item at index {index} is not a Channel instance, got {type(list_channels[index]).__name__} "
                  f"type instead."
    ):
        stimulator.init_channel(list_channels=list_channels, stimulation_interval=30)
        stimulator.close_port()
