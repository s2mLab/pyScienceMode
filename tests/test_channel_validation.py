"""
Pure-Python tests for Channel validation (no hardware, no sciencemode/crccheck needed).

The channel and enums modules are loaded directly, bypassing pysciencemode/__init__.py,
which imports the hardware interfaces.
"""

import importlib.util
import pathlib
import sys
import types

import pytest

_PKG_DIR = pathlib.Path(__file__).resolve().parent.parent / "pysciencemode"
_PKG_NAME = "_psm_channel_only"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"{_PKG_NAME}.{name}", _PKG_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_pkg = types.ModuleType(_PKG_NAME)
_pkg.__path__ = [str(_PKG_DIR)]
sys.modules.setdefault(_PKG_NAME, _pkg)
_enums = _load("enums")
_channel = _load("channel")

Channel = _channel.Channel
Device = _enums.Device
Modes = _enums.Modes


def _p24_channel(mode=Modes.SINGLE, frequency=50.0):
    return Channel(
        mode=mode,
        no_channel=1,
        amplitude=20,
        pulse_width=300,
        device_type=Device.P24,
        frequency=frequency,
    )


@pytest.mark.parametrize("frequency", [5000, 2001])
def test_set_frequency_out_of_bounds_raises(frequency):
    channel = _p24_channel(frequency=50.0)
    with pytest.raises(ValueError):
        channel.set_frequency(frequency)
    # The previous (valid) frequency is kept
    assert channel.get_frequency() == pytest.approx(50.0)


def test_constructor_and_set_frequency_share_bounds():
    with pytest.raises(ValueError):
        _p24_channel(frequency=5000)
    channel = _p24_channel(frequency=50.0)
    channel.set_frequency(2000)
    assert channel.get_frequency() == pytest.approx(2000)
    channel.set_frequency(0.5)
    assert channel.get_frequency() == pytest.approx(0.5)


def test_set_frequency_non_positive_raises():
    channel = _p24_channel()
    with pytest.raises(ValueError):
        channel.set_frequency(0)


@pytest.mark.parametrize("mode, n_points", [(Modes.DOUBLET, 7), (Modes.TRIPLET, 12)])
def test_multiplet_points_are_not_aliased(mode, n_points):
    channel = _p24_channel(mode=mode)
    points = channel.list_point
    assert len(points) == n_points
    assert len({id(p) for p in points}) == n_points

    # Modifying the first pulse must not modify the following ones
    points[0].set_amplitude(50)
    assert points[5].amplitude == 20
    assert points[1].amplitude == -20
    assert points[6].amplitude == -20
