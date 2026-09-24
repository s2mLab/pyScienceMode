"""
Tests of the stimulation event log. No hardware is needed: the device internals and the sciencemode library are mocked.
"""

import csv
import json
import time
from unittest.mock import MagicMock

import pytest

from pysciencemode import Channel, Device, Modes, P24, Rehastim2
from pysciencemode import p24_interface
from pysciencemode.events import (
    ChannelState,
    CsvEventLogger,
    EventSink,
    MemorySink,
    StimEvent,
)


def _p24_channel(no_channel=1, amplitude=10, pulse_width=300, frequency=20):
    return Channel(
        mode=Modes.SINGLE,
        no_channel=no_channel,
        amplitude=amplitude,
        pulse_width=pulse_width,
        frequency=frequency,
        device_type=Device.P24,
    )


# ---------------------------------------------------------------- StimEvent


def test_stim_event_snapshot():
    channel = _p24_channel(amplitude=12, pulse_width=250, frequency=40)
    event = StimEvent.create("P24", "start", [channel], stimulation_duration=1)
    channel.set_amplitude(30)  # The event keeps the values at emission time

    assert event.device == "P24"
    assert event.command == "start"
    assert event.channels == [
        ChannelState(
            channel=1,
            amplitude=12,
            pulse_width=250,
            frequency=40,
            mode="SINGLE",
            name="muscle_1",
        )
    ]
    assert event.extra == {"stimulation_duration": 1}
    assert event.t_wall_utc.endswith("+00:00")
    decoded = json.loads(event.to_json())
    assert decoded["channels"][0]["amplitude"] == 12


def test_stim_event_backdated_timestamp():
    t0 = time.perf_counter_ns()
    time.sleep(0.02)
    event = StimEvent.create("P24", "stop", t_perf_ns=t0)
    assert event.t_perf_ns == t0
    later = StimEvent.create("P24", "stop")
    assert later.t_perf_ns > t0
    assert later.event_id > event.event_id


# ---------------------------------------------------------------- sinks


def test_csv_logger(tmp_path):
    path = tmp_path / "events.csv"
    with CsvEventLogger(path) as sink:
        sink.emit(
            StimEvent.create(
                "P24", "pulse", [_p24_channel(1), _p24_channel(2)], pulse_index=3
            )
        )
        sink.emit(StimEvent.create("P24", "stop", ack="Stimulation stopped"))
        # Flushed after each event: readable while still open
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
    assert [r["command"] for r in rows] == ["pulse", "pulse", "stop"]
    assert [r["channel"] for r in rows] == ["1", "2", ""]
    assert rows[0]["event_id"] == rows[1]["event_id"]
    assert json.loads(rows[0]["extra"]) == {"pulse_index": 3}
    assert rows[2]["ack"] == "Stimulation stopped"

    # Append mode does not rewrite the header
    with CsvEventLogger(path, mode="a") as sink:
        sink.emit(StimEvent.create("P24", "init"))
    with open(path, newline="") as f:
        lines = f.read().splitlines()
    assert sum(line.startswith("event_id") for line in lines) == 1
    assert len(lines) == 5


def test_emit_after_close_is_ignored(tmp_path):
    sink = CsvEventLogger(tmp_path / "events.csv")
    sink.close()
    sink.emit(StimEvent.create("P24", "stop"))  # must not raise


def test_lsl_outlet():
    pylsl = pytest.importorskip("pylsl")
    from pysciencemode.events import LslMarkerOutlet

    outlet = LslMarkerOutlet(name="pysciencemode-test", source_id="psm-test")
    streams = pylsl.resolve_byprop("name", "pysciencemode-test", timeout=5)
    assert streams, "LSL stream not found"
    inlet = pylsl.StreamInlet(streams[0])
    inlet.open_stream(timeout=5)
    time.sleep(0.5)

    t0 = time.perf_counter_ns()
    t_lsl = pylsl.local_clock()
    time.sleep(0.05)
    outlet.emit(StimEvent.create("P24", "start", [_p24_channel()], t_perf_ns=t0))
    sample, timestamp = inlet.pull_sample(timeout=5)
    assert sample is not None
    marker = json.loads(sample[0])
    assert marker["command"] == "start"
    assert marker["channels"][0]["amplitude"] == 10
    # The marker is back-dated to the time of the command, not the time of emission
    assert abs(timestamp - t_lsl) < 0.02
    outlet.close()


# ---------------------------------------------------------------- mixin


class _FailingSink(EventSink):
    def emit(self, event):
        raise RuntimeError("disk full")


def test_failing_sink_does_not_break(caplog):
    stim = P24.__new__(P24)
    stim.device_type = Device.P24.value
    memory = MemorySink()
    stim.add_event_sink(_FailingSink())
    stim.add_event_sink(memory)
    stim._emit("stop")
    assert [e.command for e in memory.events] == ["stop"]
    assert "disk full" in caplog.text


def test_no_sink_no_event():
    stim = P24.__new__(P24)
    assert stim._emit("stop") is None
    with pytest.raises(TypeError):
        stim.add_event_sink(object())


# ---------------------------------------------------------------- device wiring


@pytest.fixture
def fake_p24(monkeypatch):
    """A P24 whose communication layer is mocked."""
    monkeypatch.setattr(p24_interface, "sciencemode", MagicMock(), raising=False)
    stim = P24.__new__(P24)
    stim.device_type = Device.P24.value
    stim.show_log = False
    stim.list_channels = None
    stim.electrode_number = 0
    stim.stimulation_started = None
    stim._current_stim_duration = None
    stim._safety = True
    stim.ml_update = MagicMock()
    stim.P24Commands = MagicMock()
    stim.device = MagicMock()
    for name in (
        "get_next_packet_number",
        "_get_last_ack",
        "_get_current_data",
        "check_stimulation_errors",
        "log",
    ):
        setattr(stim, name, MagicMock())
    memory = stim.add_event_sink(MemorySink())
    return stim, memory


def test_p24_mid_level_events(fake_p24):
    stim, memory = fake_p24
    channels = [_p24_channel(1, amplitude=15)]
    stim.init_stimulation(channels)
    stim.start_stimulation(channels, stimulation_duration=0.01)
    stim.end_stimulation()

    commands = [e.command for e in memory.events]
    assert commands == ["init", "start", "pause", "stop"]
    start = memory.events[1]
    assert start.device == "P24"
    assert start.channels[0].amplitude == 15
    assert start.extra == {"stimulation_duration": 0.01}
    assert memory.events[2].extra == {"paused_channels": [1]}
    t = [e.t_perf_ns for e in memory.events]
    assert t == sorted(t)


def test_p24_pulse_by_pulse_events(fake_p24):
    stim, memory = fake_p24
    channels = [_p24_channel(1), _p24_channel(2)]
    stim.init_stimulation(channels)
    stim.start_pulse_by_pulse_stimulation(
        channels,
        pulse_width_list={1: [100, 200, 300], 2: [150, 250, 350]},
        amplitude_list={1: [5, 6, 7], 2: [8, 9, 10]},
    )
    pulses = [e for e in memory.events if e.command == "pulse"]
    assert [e.extra["pulse_index"] for e in pulses] == [0, 1, 2]
    assert [c.pulse_width for c in pulses[2].channels] == [300, 350]
    assert [c.amplitude for c in pulses[1].channels] == [6, 9]
    assert memory.events[-1].command == "pause"


def test_p24_constructor_accepts_sinks(monkeypatch):
    memory = MemorySink()
    monkeypatch.setattr(
        p24_interface.RehastimGeneric, "__init__", lambda self, *a, **k: None
    )
    stim = P24("COM_FAKE", event_sinks=[memory])
    assert stim.event_sinks == [memory]


def test_rehastim2_events():
    stim = Rehastim2.__new__(Rehastim2)
    stim.device_type = Device.Rehastim2.value
    stim.stimulation_active = False
    stim.inter_pulse_interval = 2
    stim.low_frequency_factor = 0
    stim._send_packet = MagicMock()
    stim._get_last_ack = MagicMock(return_value="packet")
    stim._calling_ack = MagicMock(return_value="Stimulation initialized")
    memory = stim.add_event_sink(MemorySink())

    channel = Channel(
        mode=Modes.SINGLE,
        no_channel=2,
        amplitude=20,
        pulse_width=300,
        device_type=Device.Rehastim2,
    )
    stim.init_channel(stimulation_interval=30, list_channels=[channel])
    stim.start_stimulation(stimulation_duration=0.05)
    stim.end_stimulation()

    assert [e.command for e in memory.events] == ["init", "start", "pause", "stop"]
    init = memory.events[0]
    assert init.device == "Rehastim2"
    assert init.ack == "Stimulation initialized"
    assert init.extra["stimulation_interval"] == 30
    assert init.channels[0].channel == 2
    assert init.channels[0].amplitude == 20
    assert memory.events[2].extra == {"paused_channels": [2]}
