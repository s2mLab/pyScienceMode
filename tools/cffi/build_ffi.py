"""Emit the C source of the ``sciencemode._sciencemode`` cffi extension (API mode).

Called by CMake at build time (see the top-level CMakeLists.txt)::

    python tools/cffi/build_ffi.py <output.c>

It only needs the ``cffi`` package (and its pure-Python ``pycparser``
dependency, used to parse the committed ``smpt_cdef.h``). The generated C file
is compiled and linked against the static ``smpt`` library by CMake, which
provides the include directories and the ``SMPT_LOW_LEVEL`` /
``SMPT_MID_LEVEL`` definitions.
"""

import sys
from pathlib import Path

from cffi import FFI

HERE = Path(__file__).resolve().parent

SOURCE = """
#include "smpt_definitions.h"
#include "smpt_client.h"
#include "smpt_client_utils.h"
#include "smpt_client_power.h"
#include "smpt_packet_number_generator.h"
#include "smpt_ll_definitions.h"
#include "smpt_ll_client.h"
#include "smpt_ml_definitions.h"
#include "smpt_ml_client.h"

#if !defined(_WIN32)
#include <stdlib.h>
#include <string.h>
/* Workaround for an upstream bug (ScienceMode4_c_library @ 0cb1201): on Linux
 * and macOS, smpt_check_serial_port_internal() is implemented with a
 * `Smpt_device *` parameter while its prototype, and smpt_check_serial_port(),
 * pass the port *name*: the library then writes into memory past the Python
 * string (heap corruption, segfault on macOS). Re-implement the check on top of
 * the public open/close functions, with a heap-allocated device. */
static bool pysciencemode_check_serial_port(const char *const device_name)
{
    bool ok;
    Smpt_device *device;
    if (device_name == NULL || strlen(device_name) >= Smpt_Length_Serial_Port_Chars)
        return false;
    device = (Smpt_device *)calloc(1, sizeof(Smpt_device));
    if (device == NULL)
        return false;
    ok = smpt_open_serial_port(device, device_name);
    if (ok)
        smpt_close_serial_port(device);
    free(device);
    return ok;
}
#define smpt_check_serial_port pysciencemode_check_serial_port
#endif
"""


def make_ffi() -> FFI:
    ffi = FFI()
    ffi.cdef((HERE / "smpt_cdef.h").read_text(encoding="utf-8"))
    ffi.set_source("sciencemode._sciencemode", SOURCE)
    return ffi


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <output.c>")
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    make_ffi().emit_c_code(str(out))


if __name__ == "__main__":
    main()
