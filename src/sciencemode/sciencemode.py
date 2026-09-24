"""Backward-compatible entry point (same API as the former ``sciencemode_cffi``).

Exposes ``lib`` and ``ffi`` and, like the original module, re-exports every
symbol of ``lib`` at module level (e.g. ``sciencemode.smpt_send_reset``).
"""

from sciencemode._sciencemode import ffi, lib

for __name in dir(lib):
    globals()[__name] = getattr(lib, __name)
del __name
