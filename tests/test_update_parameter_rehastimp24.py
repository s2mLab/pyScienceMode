import pytest
from pyScienceMode2 import RehastimP24 as Stp24
from pyScienceMode2 import Channel, Device, Modes


# Connect the Rehastimp24 device to the computer. Then connect channel 1 to a stim box or to the skin, and start the
# test.


@pytest.mark.parametrize("port", ["COM4"])
@pytest.mark.parametrize("amplitude", [10, 20, 30])
def test_update_amplitude(port, amplitude):
    stimulator = Stp24(port=port, show_log="Status")
    list_channels = []
    channel_number = 1
    channel_1 = Channel(mode=Modes.SINGLE,
                        no_channel=channel_number, amplitude=amplitude, pulse_width=300, frequency=10,
                        device_type=Device.Rehastimp24
                        )
    list_channels.append(channel_1)
    stimulator.init_stimulation(list_channels=list_channels)
    channel_1.set_amplitude(amplitude)
    assert channel_1.get_amplitude() == amplitude
    stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=1, safety=True)
    stimulator.close_port()


@pytest.mark.parametrize("port", ["COM4"])
@pytest.mark.parametrize("pulse_width", [100, 350, 600])
def test_update_pulse_width(port, pulse_width):
    stimulator = Stp24(port=port, show_log="Status")
    list_channels = []
    channel_number = 1
    channel_1 = Channel(mode=Modes.SINGLE,
                        no_channel=channel_number, amplitude=10, pulse_width=pulse_width, frequency=10,
                        device_type=Device.Rehastimp24
                        )
    list_channels.append(channel_1)
    stimulator.init_stimulation(list_channels=list_channels)
    channel_1.set_pulse_width(pulse_width=pulse_width)
    assert channel_1.get_pulse_width() == pulse_width
    stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=1, safety=True)
    stimulator.close_port()


@pytest.mark.parametrize("port", ["COM4"])
@pytest.mark.parametrize("frequency", [10, 30, 50])
def test_update_frequency(port, frequency):
    stimulator = Stp24(port=port, show_log="Status")
    list_channels = []
    channel_number = 1
    channel_1 = Channel(mode=Modes.SINGLE,
                        no_channel=channel_number, amplitude=10, pulse_width=500, frequency=frequency,
                        device_type=Device.Rehastimp24
                        )
    list_channels.append(channel_1)
    stimulator.init_stimulation(list_channels=list_channels)
    channel_1.set_frequency(frequency=frequency)
    assert channel_1.get_frequency() == frequency
    stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=1, safety=True)
    stimulator.close_port()


@pytest.mark.parametrize("port", ["COM4"])
@pytest.mark.parametrize("mode", [Modes.SINGLE, Modes.DOUBLET, Modes.TRIPLET])
def test_update_mode(port, mode):
    stimulator = Stp24(port=port, show_log="Status")
    list_channels = []
    channel_number = 1
    channel_1 = Channel(mode=mode,
                        no_channel=channel_number, amplitude=20, pulse_width=350, frequency=10,
                        device_type=Device.Rehastimp24
                        )
    list_channels.append(channel_1)
    stimulator.init_stimulation(list_channels=list_channels)
    channel_1.set_mode(mode=mode)
    assert channel_1.get_mode() == mode.value
    stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=1, safety=True)
    stimulator.close_port()
