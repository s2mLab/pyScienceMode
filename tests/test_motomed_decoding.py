"""
Hardware-free tests of the MOTOmed packet decoding (actual values and phase result).

The packets are built with the same byte-stuffing routine as the one used to send
commands (utils._stuff_packet_byte), then decoded by RehastimGeneric.
"""

import threading

import pytest

from pysciencemode import RehastimGeneric
from pysciencemode.utils import _stuff_packet_byte

HEADER = [0xF0, 0x81, 0x00, 0x81, 0x00, 0x00, 0x00]  # 7 bytes, data starts at index 7


def _decoder():
    decoder = object.__new__(RehastimGeneric)
    decoder.motomed_values = None
    decoder.max_motomed_values = 100
    decoder.last_phase_result = None
    decoder.max_phase_result = 100
    decoder.is_phase_result = threading.Event()
    return decoder


def _u16(value):
    return [(value >> 8) & 0xFF, value & 0xFF]


def _packet(data):
    return bytes(HEADER + _stuff_packet_byte(list(data), command_data=True) + [0x0F])


@pytest.mark.parametrize(
    "angle",
    [0, 45, 255, 256, 300, 359, 0x100 + 0x0A, 0x100 + 0x0F, 0x100 + 0x55, 0x100 + 0xF0],
)
@pytest.mark.parametrize("speed, torque", [(30, -5), (0x0F, 0x55), (-16, 10)])
def test_actual_values_decoding(angle, speed, torque):
    data = _u16(angle) + [0, speed & 0xFF, 0, torque & 0xFF]
    decoder = _decoder()
    decoder._actual_values_ack(_packet(data))
    assert decoder.get_angle() == angle
    assert decoder.get_speed() == speed
    assert decoder.get_torque() == torque


@pytest.mark.parametrize(
    "u16_value", [0, 12, 255, 256, 1000, 0x0100 + 0x0F, 0x0200 + 0x81, 0x0300 + 0xF0]
)
def test_phase_result_decoding(u16_value):
    expected = [
        7,  # phase_number
        u16_value,  # passive_distance
        u16_value + 1,  # active_distance
        0x0A,  # average_power (stuffed byte)
        40,  # maximum_power
        u16_value,  # phase_duration
        u16_value,  # active_phase_duration
        u16_value,  # phase_work
        1,  # success_value
        -3,  # symmetry
        20,  # average_muscle_tone
    ]
    data = (
        [expected[0]]
        + _u16(expected[1])
        + _u16(expected[2])
        + [expected[3], expected[4]]
        + _u16(expected[5])
        + _u16(expected[6])
        + _u16(expected[7])
        + [expected[8], expected[9] & 0xFF, expected[10]]
    )
    decoder = _decoder()
    assert decoder._phase_result_ack(_packet(data)) == "PhaseResult"
    assert decoder.last_phase_result[:, -1].tolist() == expected
