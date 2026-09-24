"""Low-level cffi bindings to HASOMED's ScienceMode4 C library (P24).

Built from source (git submodule ``extern/ScienceMode4_c_library``) and shipped
with pysciencemode. The layout mirrors the former ``sciencemode_cffi`` wheel so
that ``from sciencemode import sciencemode`` keeps working::

    from sciencemode import sciencemode
    sciencemode.lib.smpt_open_serial_port(...)
    sciencemode.ffi.new("Smpt_device*")

The bundled C library is licensed under MPL-2.0 OR LGPL-3.0-or-later (license
texts in the ``.dist-info/licenses`` directory of the installed distribution).
"""
