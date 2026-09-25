import time

import pytest
from pysciencemode import P24 as Stp24
from pysciencemode import Channel, Device, Modes

pytestmark = [pytest.mark.hardware, pytest.mark.p24]


# Connect the P24 device to the computer. Then connect channel 1 to a stim box or to the skin, and start the
# test.
# Then you can run the whole file or just one test.


@pytest.mark.parametrize("amplitude", [10, 20, 30])
def test_update_amplitude(port, amplitude):
    """
    You will need to connect channel 1 to a stim box or to the skin, then start the test.
    The stimulation will be updated with a new amplitude.
    """
    stimulator = Stp24(port=port, show_log="Status")
    list_channels = []
    channel_number = 1
    channel_1 = Channel(
        mode=Modes.SINGLE,
        no_channel=channel_number,
        amplitude=amplitude,
        pulse_width=300,
        frequency=10,
        device_type=Device.P24,
    )
    list_channels.append(channel_1)
    stimulator.init_stimulation(list_channels=list_channels)
    channel_1.set_amplitude(amplitude)
    assert channel_1.get_amplitude() == amplitude
    stimulator.start_stimulation(
        upd_list_channels=list_channels, stimulation_duration=1, safety=True
    )
    stimulator.close_port()


@pytest.mark.parametrize("pulse_width", [100, 350, 600])
def test_update_pulse_width(port, pulse_width):
    """
    You will need to connect channel 2 to a stim box or to the skin, then start the test.
    The stimulation will be updated with a new pusle width.
    """
    stimulator = Stp24(port=port, show_log="Status")
    list_channels = []
    channel_number = 1
    channel_1 = Channel(
        mode=Modes.SINGLE,
        no_channel=channel_number,
        amplitude=10,
        pulse_width=pulse_width,
        frequency=10,
        device_type=Device.P24,
    )
    list_channels.append(channel_1)
    stimulator.init_stimulation(list_channels=list_channels)
    channel_1.set_pulse_width(pulse_width=pulse_width)
    assert channel_1.get_pulse_width() == pulse_width
    stimulator.start_stimulation(
        upd_list_channels=list_channels, stimulation_duration=1, safety=True
    )
    stimulator.close_port()


@pytest.mark.parametrize("frequency", [10, 30, 50])
def test_update_frequency(port, frequency):
    """
    You will need to connect channel 2 to a stim box or to the skin, then start the test.
    The stimulation will be updated with a new frequency
    """
    stimulator = Stp24(port=port, show_log="Status")
    list_channels = []
    channel_number = 1
    channel_1 = Channel(
        mode=Modes.SINGLE,
        no_channel=channel_number,
        amplitude=10,
        pulse_width=500,
        frequency=frequency,
        device_type=Device.P24,
    )
    list_channels.append(channel_1)
    stimulator.init_stimulation(list_channels=list_channels)
    channel_1.set_frequency(frequency=frequency)
    assert round(channel_1.get_frequency()) == frequency
    stimulator.start_stimulation(
        upd_list_channels=list_channels, stimulation_duration=1, safety=True
    )
    stimulator.close_port()


@pytest.mark.parametrize("nb_pulses", [10, 50])
def test_pulse_by_pulse_stimulation(port, nb_pulses):
    """
    You will need to connect channel 1 to a stim box or to the skin, then start the test.
    The pulse width, the amplitude and the interval before the next pulse will be updated between each pulse.
    """
    stimulator = Stp24(port=port, show_log="Status")
    list_channels = []
    channel_number = 1
    channel_1 = Channel(
        mode=Modes.SINGLE,
        no_channel=channel_number,
        amplitude=10,
        pulse_width=100,
        frequency=50,
        device_type=Device.P24,
    )
    list_channels.append(channel_1)
    stimulator.init_stimulation(list_channels=list_channels)

    pulse_width_list = {channel_number: [100 + 5 * i for i in range(nb_pulses)]}
    amplitude_list = {channel_number: [10 + 0.2 * i for i in range(nb_pulses)]}
    pulse_interval_list = [20 + i for i in range(nb_pulses)]
    tic = time.time()
    stimulator.start_pulse_by_pulse_stimulation(
        upd_list_channels=list_channels,
        pulse_width_list=pulse_width_list,
        amplitude_list=amplitude_list,
        pulse_interval_list=pulse_interval_list,
    )
    stimulation_duration = time.time() - tic
    assert channel_1.get_pulse_width() == pulse_width_list[channel_number][-1]
    assert channel_1.get_amplitude() == amplitude_list[channel_number][-1]
    assert round(channel_1.get_frequency()) == round(1000 / pulse_interval_list[-1])
    assert stimulation_duration >= sum(pulse_interval_list) / 1000
    stimulator.close_port()


@pytest.mark.parametrize("nb_pulses_before_stop", [1, 5])
def test_pulse_by_pulse_stop_condition(port, nb_pulses_before_stop):
    """
    You will need to connect channel 1 to a stim box or to the skin, then start the test.
    The stimulation will stop as soon as the stop condition is met, before the end of the given pulse widths.
    """
    stimulator = Stp24(port=port, show_log="Status")
    list_channels = []
    channel_number = 1
    channel_1 = Channel(
        mode=Modes.SINGLE,
        no_channel=channel_number,
        amplitude=10,
        pulse_width=100,
        frequency=50,
        device_type=Device.P24,
    )
    list_channels.append(channel_1)
    stimulator.init_stimulation(list_channels=list_channels)

    pulse_width_list = {channel_number: [100 + 5 * i for i in range(50)]}
    pulse_interval_list = [20 for _ in range(50)]
    nb_pulses_sent = 0

    def stop_condition() -> bool:
        nonlocal nb_pulses_sent
        if nb_pulses_sent == nb_pulses_before_stop:
            return True
        nb_pulses_sent += 1
        return False

    stimulator.start_pulse_by_pulse_stimulation(
        upd_list_channels=list_channels,
        pulse_width_list=pulse_width_list,
        pulse_interval_list=pulse_interval_list,
        stop_condition=stop_condition,
    )
    assert nb_pulses_sent == nb_pulses_before_stop
    assert (
        channel_1.get_pulse_width()
        == pulse_width_list[channel_number][nb_pulses_before_stop - 1]
    )
    stimulator.close_port()


@pytest.mark.parametrize("mode", [Modes.SINGLE, Modes.DOUBLET, Modes.TRIPLET])
def test_update_mode(port, mode):
    """
    You will need to connect channel 2 to a stim box or to the skin, then start the test.
    The stimulation will be updated with a new mode
    """
    stimulator = Stp24(port=port, show_log="Status")
    list_channels = []
    channel_number = 1
    channel_1 = Channel(
        mode=mode,
        no_channel=channel_number,
        amplitude=20,
        pulse_width=350,
        frequency=10,
        device_type=Device.P24,
    )
    list_channels.append(channel_1)
    stimulator.init_stimulation(list_channels=list_channels)
    channel_1.set_mode(mode=mode)
    assert channel_1.get_mode() == mode.value
    stimulator.start_stimulation(
        upd_list_channels=list_channels, stimulation_duration=1, safety=True
    )
    stimulator.close_port()
