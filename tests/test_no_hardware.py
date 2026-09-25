"""
Smoke tests that run without any stimulator connected (used by the CI).
"""

import pytest

import pysciencemode
from pysciencemode import Channel, Device, Modes, Point
from pysciencemode.utils import calc_electrode_number, check_pulse_interval_list


def test_public_api_importable():
    for name in ("P24", "Rehastim2", "Channel", "Point", "Device", "Modes"):
        assert hasattr(pysciencemode, name)


@pytest.mark.parametrize("device_type", [Device.P24, "p24"])
def test_p24_single_channel_is_symmetric_biphasic(device_type):
    channel = Channel(
        mode=Modes.SINGLE,
        no_channel=1,
        amplitude=20,
        pulse_width=300,
        frequency=10,
        device_type=device_type,
    )
    assert len(channel.list_point) == 2
    assert channel.is_pulse_symmetric()


def test_asymmetric_pulse_detected():
    channel = Channel(no_channel=1, frequency=10, device_type=Device.P24)
    channel.list_point.append(Point(350, 20))
    assert not channel.is_pulse_symmetric()


def test_invalid_device_type():
    with pytest.raises(ValueError, match="device_type must be one of the following"):
        Channel(no_channel=1, device_type="unknown")
    with pytest.raises(TypeError, match="device_type must be a string or a Device"):
        Channel(no_channel=1)


def test_rehastim2_limits():
    with pytest.raises(ValueError, match="Amplitude min = 0, max = 130"):
        Channel(
            mode=Modes.SINGLE,
            no_channel=1,
            amplitude=200,
            pulse_width=300,
            device_type=Device.Rehastim2,
        )
    with pytest.raises(RuntimeError, match="Frequency can not be set"):
        Channel(
            mode=Modes.SINGLE,
            no_channel=1,
            amplitude=10,
            pulse_width=300,
            frequency=30,
            device_type=Device.Rehastim2,
        )


def test_calc_electrode_number():
    channels = [
        Channel(mode=Modes.SINGLE, no_channel=n, amplitude=10, pulse_width=300, device_type=Device.Rehastim2)
        for n in (1, 4)
    ]
    assert calc_electrode_number(channels) == 2**0 + 2**3


def test_check_pulse_interval_list():
    check_pulse_interval_list([20, 20, 20], 3)
    with pytest.raises(ValueError, match="one pulse interval must be given for each pulse"):
        check_pulse_interval_list([20, 20], 3)
    with pytest.raises(ValueError, match="pulse interval min = 0.5ms"):
        check_pulse_interval_list([0], 1)
    with pytest.raises(TypeError, match="must be a list"):
        check_pulse_interval_list((20,), 1)
