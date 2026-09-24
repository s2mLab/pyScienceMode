"""
Hardware-free fake of the ``sciencemode`` cffi module (``from sciencemode import sciencemode``) used by the P24.

It records every ``smpt_send_*`` call and answers each one with an ack, like a P24 would, so that the P24 class can
be tested without a stimulator. It is not a protocol simulator: it only covers what pyScienceMode uses.

Usage (pytest)::

    from tests.fake_sciencemode import install_fake_sciencemode

    def test_something(monkeypatch):
        fake = install_fake_sciencemode(monkeypatch)
        stimulator = P24(port="COM_FAKE")
        ...
        assert fake.count("smpt_send_ml_update") == 1

Knobs of the FakeScienceMode instance (can be changed at any time, thread safe enough for tests):

* ``channel_states``: list of 8 Smpt_Ml_Channel_State values returned by the next Ml_get_current_data acks.
* ``respond``: if False, commands are recorded but not acknowledged (simulates a device that stopped answering).
* ``ack_result``: dict command_number -> Smpt_Result put in the ack of that command (default: successful).
* ``fail_send``: set of smpt_send_* function names that return False.
* ``ack_delay``: seconds before an ack becomes available.
* ``stray_acks``: list of command numbers of unexpected acks to deliver before the next ack.

Recorded data: ``calls`` is a list of ``FakeCall(t, name, data)`` with a ``time.perf_counter`` timestamp. For
``smpt_send_ml_update``, ``data`` is a dict {channel_index: (period, ramp, ((time, current), ...))} of the enabled
channels, copied when the command was sent.
"""

from collections import deque
from dataclasses import dataclass
import sys
import threading
import time
import types

from pysciencemode.enums import P24Commands

N_CHANNELS = 8
N_POINTS = 16


@dataclass
class FakeCall:
    t: float
    name: str
    data: object = None


class _Struct:
    """Minimal stand-in for a cffi struct pointer: attributes are created on assignment, unknown ones read 0."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return 0


def _new_ml_update():
    return _Struct(
        packet_number=0,
        enable_channel=[False] * N_CHANNELS,
        channel_config=[
            _Struct(
                period=0,
                ramp=0,
                number_of_points=0,
                points=[_Struct(time=0, current=0) for _ in range(N_POINTS)],
            )
            for _ in range(N_CHANNELS)
        ],
    )


class FakeFFI:
    def new(self, ctype: str, init=None):
        if ctype == "char[]":
            return bytes(init or b"")
        if ctype == "Smpt_ml_update*":
            return _new_ml_update()
        if ctype == "Smpt_ml_get_current_data_ack*":
            return _Struct(
                channel_data=_Struct(channel_state=[0] * N_CHANNELS), result=0
            )
        if ctype == "Smpt_ack*":
            return _Struct(packet_number=0, command_number=0, result=0)
        if ctype == "Smpt_ll_channel_config*":
            return _Struct(points=[_Struct(time=0, current=0) for _ in range(N_POINTS)])
        return _Struct()


class FakeLib:
    """Constants and smpt_* functions. Created by FakeScienceMode, which holds the state."""

    Smpt_Result_Successful = 0
    Smpt_Result_Transfer_Error = 1
    Smpt_Result_Parameter_Error = 2

    Smpt_Ml_Channel_State_Ok = 0
    Smpt_Ml_Channel_State_Electrode_Error = 1
    Smpt_Ml_Channel_State_Timeout_Error = 2
    Smpt_Ml_Channel_State_Low_Current_Error = 3
    Smpt_Ml_Channel_State_Last_Item = 4

    Smpt_Ml_Data_Channels = 4

    Smpt_Channel_Red, Smpt_Channel_Blue, Smpt_Channel_Black, Smpt_Channel_White = range(4)
    Smpt_Connector_Yellow, Smpt_Connector_Green = range(2)
    Smpt_High_Voltage_Default = 0

    def __init__(self, owner: "FakeScienceMode"):
        self._owner = owner


#  Command constants (Smpt_Cmd_*), taken from pysciencemode.enums.P24Commands
for _command in P24Commands:
    setattr(FakeLib, _command.name, _command.value)

#  smpt_send_* function name -> command number of the ack it produces
_SEND_TO_ACK = {
    "smpt_send_get_extended_version": FakeLib.Smpt_Cmd_Get_Extended_Version_Ack,
    "smpt_send_get_device_id": FakeLib.Smpt_Cmd_Get_Device_Id_Ack,
    "smpt_send_get_stim_status": FakeLib.Smpt_Cmd_Get_Stim_Status_Ack,
    "smpt_send_get_battery_status": FakeLib.Smpt_Cmd_Get_Battery_Status_Ack,
    "smpt_send_get_main_status": FakeLib.Smpt_Cmd_Get_Main_Status_Ack,
    "smpt_send_reset": FakeLib.Smpt_Cmd_Reset_Ack,
    "smpt_send_ll_init": FakeLib.Smpt_Cmd_Ll_Init_Ack,
    "smpt_send_ll_channel_config": FakeLib.Smpt_Cmd_Ll_Channel_Config_Ack,
    "smpt_send_ll_stop": FakeLib.Smpt_Cmd_Ll_Stop_Ack,
    "smpt_send_ml_init": FakeLib.Smpt_Cmd_Ml_Init_Ack,
    "smpt_send_ml_update": FakeLib.Smpt_Cmd_Ml_Update_Ack,
    "smpt_send_ml_stop": FakeLib.Smpt_Cmd_Ml_Stop_Ack,
    "smpt_send_ml_get_current_data": FakeLib.Smpt_Cmd_Ml_Get_Current_Data_Ack,
}


class FakeScienceMode:
    """The fake ``sciencemode.sciencemode`` module: exposes ``ffi``, ``lib`` and the lib functions."""

    def __init__(self):
        self.ffi = FakeFFI()
        self.lib = FakeLib(self)
        self.calls = []
        self.channel_states = [FakeLib.Smpt_Ml_Channel_State_Ok] * N_CHANNELS
        self.respond = True
        self.ack_result = {}
        self.fail_send = set()
        self.ack_delay = 0.0
        self.stray_acks = []
        self._acks = deque()  # (available_at, command_number, packet_number, result)
        self._packet_number = 0
        self._lock = threading.Lock()
        self._install_functions()

    #  Helpers for the tests
    def names(self) -> list:
        return [call.name for call in self.calls]

    def count(self, name: str) -> int:
        return sum(call.name == name for call in self.calls)

    def of(self, name: str) -> list:
        return [call for call in self.calls if call.name == name]

    def ml_update_amplitudes(self, channel_index: int = 0) -> list:
        """Positive-phase amplitude sent to channel_index by each ml_update."""
        return [
            call.data[channel_index][2][0][1]
            for call in self.of("smpt_send_ml_update")
            if channel_index in call.data
        ]

    #  Fake lib functions
    def _record(self, name, data=None):
        with self._lock:
            self.calls.append(FakeCall(time.perf_counter(), name, data))

    def _send(self, name, packet_number, data=None):
        self._record(name, data)
        if name in self.fail_send:
            return False
        if self.respond:
            command = _SEND_TO_ACK[name]
            now = time.perf_counter()
            with self._lock:
                for stray in self.stray_acks:
                    self._acks.append((now, stray, 0, 0))
                self.stray_acks = []
                self._acks.append(
                    (
                        now + self.ack_delay,
                        command,
                        packet_number,
                        self.ack_result.get(command, 0),
                    )
                )
        return True

    def _install_functions(self):
        lib = self.lib

        def generic_sender(name):
            def send(device, arg=0):
                packet_number = arg if isinstance(arg, int) else getattr(arg, "packet_number", 0)
                return self._send(name, packet_number)

            return send

        for name in _SEND_TO_ACK:
            setattr(lib, name, generic_sender(name))

        def smpt_send_ml_update(device, ml_update):
            data = {
                index: (
                    config.period,
                    config.ramp,
                    tuple(
                        (config.points[j].time, config.points[j].current)
                        for j in range(config.number_of_points)
                    ),
                )
                for index, config in enumerate(ml_update.channel_config)
                if ml_update.enable_channel[index]
            }
            return self._send("smpt_send_ml_update", ml_update.packet_number, data)

        lib.smpt_send_ml_update = smpt_send_ml_update

        def smpt_packet_number_generator_next(device):
            with self._lock:
                self._packet_number = (self._packet_number + 1) % 64
                return self._packet_number

        def smpt_new_packet_received(device):
            with self._lock:
                return bool(self._acks) and self._acks[0][0] <= time.perf_counter()

        def smpt_last_ack(device, ack):
            with self._lock:
                _, command, packet_number, result = self._acks.popleft()
            ack.command_number = command
            ack.packet_number = packet_number
            ack.result = result
            return True

        def smpt_get_ml_get_current_data_ack(device, data_ack):
            data_ack.channel_data.channel_state = list(self.channel_states)
            return True

        lib.smpt_check_serial_port = lambda com: True
        lib.smpt_open_serial_port = lambda device, com: True
        lib.smpt_close_serial_port = lambda device: self._record("smpt_close_serial_port") or True
        lib.smpt_packet_number_generator_next = smpt_packet_number_generator_next
        lib.smpt_new_packet_received = smpt_new_packet_received
        lib.smpt_last_ack = smpt_last_ack
        lib.smpt_get_ml_get_current_data_ack = smpt_get_ml_get_current_data_ack
        for name in (
            "smpt_get_ll_init_ack",
            "smpt_get_ll_channel_config_ack",
            "smpt_get_get_extended_version_ack",
            "smpt_get_get_device_id_ack",
            "smpt_get_get_stim_status_ack",
            "smpt_get_get_battery_status_ack",
            "smpt_get_get_main_status_ack",
        ):
            setattr(lib, name, lambda device, ack: True)

    def __getattr__(self, name):
        #  The real module re-exports the lib symbols (sciencemode.smpt_send_... is used by check_port_device)
        if name.startswith("smpt_") or name.startswith("Smpt_"):
            return getattr(self.lib, name)
        raise AttributeError(name)


def install_fake_sciencemode(monkeypatch) -> FakeScienceMode:
    """
    Replace the sciencemode cffi module by a new FakeScienceMode in sys.modules and in every pysciencemode module
    that imported it. Undone automatically by monkeypatch at the end of the test.
    """
    import pysciencemode.sciencemode
    import pysciencemode.p24_interface

    fake = FakeScienceMode()
    package = types.ModuleType("sciencemode")
    package.sciencemode = fake
    monkeypatch.setitem(sys.modules, "sciencemode", package)
    monkeypatch.setitem(sys.modules, "sciencemode.sciencemode", fake)
    for module in (pysciencemode.sciencemode, pysciencemode.p24_interface):
        monkeypatch.setattr(module, "sciencemode", fake, raising=False)
    return fake
