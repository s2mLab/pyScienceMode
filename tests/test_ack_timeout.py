"""
Unit tests (no hardware needed) for the acknowledgment timeout (issue #15).
"""

import time
from unittest import mock

import pytest

import pysciencemode.sciencemode as sm
from pysciencemode import AckTimeoutError
from pysciencemode.enums import Device


def _make_stimulator(device_type, ack_timeout=0.1):
    """Build a RehastimGeneric without calling __init__ (no serial port / device needed)."""
    stim = object.__new__(sm.RehastimGeneric)
    stim.device_type = device_type
    stim.port_name = "COM_TEST"
    stim.error_occured = False
    stim.is_motomed_connected = False
    stim.show_log = False
    stim.ack_received = []
    stim.last_ack = None
    stim.last_init_ack = None
    stim.ack_timeout = ack_timeout
    return stim


def _silent_port():
    port = mock.Mock()
    port.in_waiting = 0
    port.read.return_value = b""
    return port


def test_ack_timeout_error_is_timeout_error():
    assert issubclass(AckTimeoutError, TimeoutError)


def test_rehastim2_get_last_ack_timeout():
    stim = _make_stimulator(Device.Rehastim2.value, ack_timeout=0.1)
    stim.port = _silent_port()
    tic = time.perf_counter()
    with pytest.raises(AckTimeoutError):
        stim._get_last_ack()
    elapsed = time.perf_counter() - tic
    assert 0.1 <= elapsed < 1.0
    stim.port.inWaiting.assert_not_called()


def test_rehastim2_get_last_ack_returns_packet():
    stim = _make_stimulator(Device.Rehastim2.value)
    packet = bytes([0xF0, 1, 2, 3, 4, 5, 6, 7, 8, 0x0F])
    port = mock.Mock()
    type(port).in_waiting = mock.PropertyMock(side_effect=[len(packet), 0])
    port.read.return_value = packet
    stim.port = port
    assert stim._get_last_ack() == packet


def test_read_packet_without_deadline_waits_for_data():
    """Without deadline (e.g. from the catch-ack thread) _read_packet keeps waiting, using a blocking read."""
    stim = _make_stimulator(Device.Rehastim2.value)
    packet = bytes([0xF0, 1, 2, 3, 4, 5, 6, 7, 8, 0x0F])
    port = mock.Mock()
    # in_waiting stays 0, bytes come from the blocking read(1) calls (two empty reads first)
    port.in_waiting = 0
    port.read.side_effect = [b"", b""] + [bytes([b]) for b in packet]
    stim.port = port
    assert stim._read_packet() == [packet]


def test_motomed_get_last_ack_timeout():
    stim = _make_stimulator(Device.Rehastim2.value, ack_timeout=0.05)
    stim.is_motomed_connected = True
    with pytest.raises(AckTimeoutError):
        stim._get_last_ack()
    with pytest.raises(AckTimeoutError):
        stim._get_last_ack(init=True)


def test_p24_get_last_ack_timeout():
    stim = _make_stimulator(Device.P24.value, ack_timeout=0.05)
    stim.device = object()
    fake_sciencemode = mock.Mock()
    fake_sciencemode.lib.smpt_new_packet_received.return_value = False
    with mock.patch.object(sm, "sciencemode", fake_sciencemode, create=True):
        with pytest.raises(AckTimeoutError):
            stim._get_last_ack()
    fake_sciencemode.lib.smpt_last_ack.assert_not_called()


def test_p24_get_last_ack_no_timeout_when_packet_received():
    stim = _make_stimulator(Device.P24.value, ack_timeout=0.05)
    stim.device = object()
    stim.ack = object()
    fake_sciencemode = mock.Mock()
    fake_sciencemode.lib.smpt_new_packet_received.side_effect = [False, True]
    fake_sciencemode.lib.smpt_last_ack.return_value = True
    with mock.patch.object(sm, "sciencemode", fake_sciencemode, create=True):
        assert stim._get_last_ack() is True
