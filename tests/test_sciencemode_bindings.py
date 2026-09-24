"""Hardware-free checks of the compiled `sciencemode` cffi bindings (P24 backend)."""

import os
import sys

import pytest

sciencemode = pytest.importorskip("sciencemode.sciencemode")
ffi, lib = sciencemode.ffi, sciencemode.lib


def test_library_loads():
    version = lib.smpt_library_version()
    assert (version.major, version.minor, version.revision) >= (4, 0, 0)
    assert ffi.sizeof("Smpt_device") > 0


def test_symbols_used_by_pysciencemode():
    # Enum constants are resolved by the C compiler (cdef uses `...`).
    assert lib.Smpt_Cmd_Ml_Update != lib.Smpt_Cmd_Ll_Init
    assert {lib.Smpt_Channel_Red, lib.Smpt_Channel_Blue, lib.Smpt_Channel_Black, lib.Smpt_Channel_White} == {0, 1, 2, 3}
    for name in ("Smpt_ll_init", "Smpt_ll_channel_config", "Smpt_ml_init", "Smpt_ml_update", "Smpt_ack"):
        ffi.new(f"{name}*")
    # Backward compatibility with the former sciencemode_cffi module: lib symbols at module level.
    assert sciencemode.smpt_send_get_extended_version is lib.smpt_send_get_extended_version


def test_check_missing_serial_port():
    name = b"COM250" if sys.platform == "win32" else b"/dev/pysciencemode-does-not-exist"
    for _ in range(20):  # used to corrupt memory on Linux/macOS (upstream bug, see build_ffi.py)
        assert not lib.smpt_check_serial_port(name)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX pseudo-terminal")
def test_posix_serial_roundtrip_on_pty():
    """Open a pseudo-terminal through the C library and check the framed packet it writes."""
    master, slave = os.openpty()
    try:
        port = os.ttyname(slave).encode()
        assert lib.smpt_check_serial_port(port)

        device = ffi.new("Smpt_device*")
        assert lib.smpt_open_serial_port(device, port)
        try:
            assert lib.smpt_send_get_device_id(device, lib.smpt_packet_number_generator_next(device))
            packet = os.read(master, 64)
        finally:
            lib.smpt_close_serial_port(device)
        assert packet[0] == 0xF0 and packet[-1] == 0x0F  # ScienceMode start/stop bytes
    finally:
        os.close(master)
        os.close(slave)
