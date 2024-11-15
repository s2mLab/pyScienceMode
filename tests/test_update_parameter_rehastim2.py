import pytest
from pysciencemode import Rehastim2 as St2
from pysciencemode import Channel, Device, Modes


# Connect the Rehastim2 device to the computer.
# You will need to connect channel 2 (or the no_channel you want between 1 and 8 to a stim box or to the skin.
# Then you can run the whole file or just one test.


@pytest.mark.parametrize("port", ["COM3"])
@pytest.mark.parametrize("amplitude", [10, 20, 30])
def test_update_amplitude(port, amplitude):
    """
    You will need to connect channel 2 to a stim box or to the skin, then start the test.
    The stimulation will be updated with a new amplitude.
    """
    stimulator = St2(port=port, show_log=False)
    list_channels = []
    channel_number = 2
    channel_1 = Channel(
        mode=Modes.SINGLE,
        no_channel=channel_number,
        amplitude=amplitude,
        pulse_width=300,
        device_type=Device.Rehastim2,
    )
    list_channels.append(channel_1)
    stimulator.init_channel(list_channels=list_channels, stimulation_interval=30)
    channel_1.set_amplitude(amplitude)
    assert channel_1.get_amplitude() == amplitude
    stimulator.start_stimulation(
        upd_list_channels=list_channels, stimulation_duration=0.5
    )
    stimulator.disconnect()
    stimulator.close_port()


@pytest.mark.parametrize("port", ["COM3"])
@pytest.mark.parametrize("pulse_width", [100, 350, 500])
def test_update_pulse_width(port, pulse_width):
    """
    You will need to connect channel 2 to a stim box or to the skin, then start the test.
    The stimulation will be updated with a new pusle width.
    """
    stimulator = St2(port=port, show_log=False)
    list_channels = []
    channel_number = 2
    channel_1 = Channel(
        mode=Modes.SINGLE,
        no_channel=channel_number,
        amplitude=10,
        pulse_width=pulse_width,
        device_type=Device.Rehastim2,
    )
    list_channels.append(channel_1)
    stimulator.init_channel(list_channels=list_channels, stimulation_interval=30)
    channel_1.set_pulse_width(pulse_width=pulse_width)
    assert channel_1.get_pulse_width() == pulse_width
    stimulator.start_stimulation(
        upd_list_channels=list_channels, stimulation_duration=0.5
    )
    stimulator.disconnect()
    stimulator.close_port()


@pytest.mark.parametrize("port", ["COM3"])
@pytest.mark.parametrize("frequency", [10, 30, 50])
def test_update_frequency(port, frequency):
    """
    You will need to connect channel 2 to a stim box or to the skin, then start the test.
    The stimulation will be updated with a new frequency
    """

    stimulator = St2(port=port, show_log=False)
    list_channels = []
    channel_number = 2
    channel_1 = Channel(
        mode=Modes.SINGLE,
        no_channel=channel_number,
        amplitude=10,
        pulse_width=400,
        device_type=Device.Rehastim2,
    )
    list_channels.append(channel_1)
    stimulator.init_channel(
        list_channels=list_channels, stimulation_interval=round(1 / frequency * 1000)
    )
    print(stimulator.stimulation_interval)
    assert stimulator.stimulation_interval == round(1 / frequency * 1000)
    stimulator.disconnect()
    stimulator.close_port()


@pytest.mark.parametrize("port", ["COM3"])
@pytest.mark.parametrize("mode", [Modes.SINGLE, Modes.DOUBLET, Modes.TRIPLET])
def test_update_mode(port, mode):
    """
    You will need to connect channel 2 to a stim box or to the skin, then start the test.
    The stimulation will be updated with a new mode
    """
    stimulator = St2(port=port, show_log=False)
    list_channels = []
    channel_number = 2
    channel_1 = Channel(
        mode=mode,
        no_channel=channel_number,
        amplitude=10,
        pulse_width=350,
        device_type=Device.Rehastim2,
    )
    list_channels.append(channel_1)
    stimulator.init_channel(list_channels=list_channels, stimulation_interval=30)
    channel_1.set_mode(mode=mode)
    assert channel_1.get_mode() == mode.value
    stimulator.start_stimulation(
        upd_list_channels=list_channels, stimulation_duration=0.5
    )
    stimulator.disconnect()
    stimulator.close_port()
