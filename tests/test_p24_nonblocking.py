"""
Tests of the non-blocking mid-level stimulation of the P24, without hardware (see tests/fake_sciencemode.py).
"""

import threading
import time

import pytest

from pysciencemode import P24, Channel, Device, Modes, StimulationEvent
from tests.fake_sciencemode import install_fake_sciencemode

PERIOD = 0.05  # Short keep-alive period to keep the tests fast


@pytest.fixture
def fake(monkeypatch):
    return install_fake_sciencemode(monkeypatch)


@pytest.fixture
def stimulator(fake):
    stim = P24(port="COM_FAKE")
    yield stim
    #  Never leave a thread running between tests
    stim._stop_continuous(pause=False, raise_error=False)


def make_channels(amplitude=20):
    channel = Channel(
        mode=Modes.SINGLE,
        no_channel=1,
        amplitude=amplitude,
        pulse_width=300,
        frequency=50,
        device_type=Device.P24,
    )
    return [channel]


def start(stimulator, channels, **kwargs):
    stimulator.init_stimulation(list_channels=channels)
    kwargs.setdefault("keep_alive_period", PERIOD)
    stimulator.start_stimulation(upd_list_channels=channels, blocking=False, **kwargs)


def wait_until(condition, timeout=2.0):
    end = time.perf_counter() + timeout
    while not condition():
        if time.perf_counter() > end:
            raise AssertionError("Condition not met in time")
        time.sleep(0.005)


def test_blocking_start_without_duration_is_unchanged(fake, stimulator):
    channels = make_channels()
    stimulator.init_stimulation(list_channels=channels)
    stimulator.start_stimulation(upd_list_channels=channels)
    assert fake.ml_update_amplitudes() == [20, 0]  # update then pause, as before
    assert stimulator._continuous is None
    assert not stimulator.is_stimulating


def test_start_returns_and_keeps_alive(fake, stimulator):
    channels = make_channels()
    tic = time.perf_counter()
    start(stimulator, channels)
    assert time.perf_counter() - tic < 0.5
    assert stimulator.is_stimulating
    assert fake.ml_update_amplitudes() == [20]

    time.sleep(10 * PERIOD)
    keep_alives = fake.of("smpt_send_ml_get_current_data")
    assert len(keep_alives) >= 4
    #  Deadline based scheduling: regular intervals, far below the 2 s device timeout
    intervals = [b.t - a.t for a, b in zip(keep_alives, keep_alives[1:])]
    assert max(intervals) < 0.5
    assert fake.count("smpt_send_ml_stop") == 0

    stimulator.stop_stimulation()
    assert not stimulator.is_stimulating
    assert fake.ml_update_amplitudes() == [20, 0]  # final zero-amplitude update
    n_calls = len(fake.calls)
    time.sleep(3 * PERIOD)
    assert len(fake.calls) == n_calls  # the thread is really gone
    assert not any(t.name == "P24ContinuousStimulation" for t in threading.enumerate())


def test_hot_update_and_callback(fake, stimulator):
    events = []
    channels = make_channels()
    start(stimulator, channels, callback=events.append)

    channels[0].set_amplitude(30)
    seq = stimulator.update_stimulation(channels, wait=True)
    assert seq == 2
    assert fake.ml_update_amplitudes() == [20, 30]
    #  The Channel objects can be modified while the thread runs: only the snapshot is sent
    channels[0].set_amplitude(45)
    time.sleep(3 * PERIOD)
    assert fake.ml_update_amplitudes() == [20, 30]

    stimulator.stop_stimulation()
    assert fake.ml_update_amplitudes() == [20, 30, 0]

    assert all(isinstance(e, StimulationEvent) for e in events)
    updates = [e for e in events if e.kind == "update"]
    assert [e.seq for e in updates] == [1, 2, 0]
    keep_alives = [e for e in events if e.kind == "keep_alive"]
    assert keep_alives and all(len(e.channel_states) == 8 for e in keep_alives)
    times = [e.t for e in events]
    assert times == sorted(times)


def test_latest_update_wins(fake, stimulator):
    channels = make_channels()
    start(stimulator, channels)
    fake.ack_delay = 0.03  # slow device: requests pile up while an update is in flight
    for amplitude in (22, 24, 26, 28, 30):
        channels[0].set_amplitude(amplitude)
        seq = stimulator.update_stimulation(channels)
    stimulator._continuous.wait_applied(seq, 1.0)
    sent = fake.ml_update_amplitudes()
    assert sent[-1] == 30
    assert len(sent) < 1 + 5  # some intermediate requests were coalesced


def test_start_again_while_running_updates(fake, stimulator):
    channels = make_channels()
    start(stimulator, channels)
    thread = stimulator._continuous.thread
    channels[0].set_amplitude(35)
    stimulator.start_stimulation(channels, blocking=False)
    stimulator._continuous.wait_applied(2, 1.0)
    assert stimulator._continuous.thread is thread
    assert fake.ml_update_amplitudes() == [20, 35]


def test_electrode_error_is_raised_in_caller(fake, stimulator):
    channels = make_channels()
    start(stimulator, channels)
    fake.channel_states[0] = fake.lib.Smpt_Ml_Channel_State_Electrode_Error
    wait_until(lambda: not stimulator._continuous.is_alive())
    with pytest.raises(RuntimeError, match="Electrode error on channel 1"):
        stimulator.update_stimulation(channels)
    #  Raised only once, and a best effort pause was sent
    assert not stimulator.is_stimulating
    assert fake.ml_update_amplitudes()[-1] == 0


def test_error_on_other_channel_is_ignored(fake, stimulator):
    channels = make_channels()
    start(stimulator, channels)
    fake.channel_states[5] = fake.lib.Smpt_Ml_Channel_State_Electrode_Error
    time.sleep(4 * PERIOD)
    assert stimulator.is_stimulating


def test_missing_ack_is_raised_in_caller(fake, stimulator):
    channels = make_channels()
    start(stimulator, channels, ack_timeout=0.1)
    fake.respond = False
    wait_until(lambda: not stimulator._continuous.is_alive())
    with pytest.raises(TimeoutError):
        stimulator.stop_stimulation()


def test_ack_error_result(fake, stimulator):
    channels = make_channels()
    start(stimulator, channels)
    fake.ack_result[fake.lib.Smpt_Cmd_Ml_Update_Ack] = 2
    channels[0].set_amplitude(30)
    seq = stimulator.update_stimulation(channels)
    with pytest.raises(RuntimeError, match="Parameter error"):
        stimulator._continuous.wait_applied(seq, 1.0)


def test_stray_acks_are_discarded(fake, stimulator):
    channels = make_channels()
    start(stimulator, channels)
    fake.stray_acks = [fake.lib.Smpt_Cmd_Get_Battery_Status_Ack]
    channels[0].set_amplitude(30)
    stimulator.update_stimulation(channels, wait=True)
    time.sleep(2 * PERIOD)
    assert stimulator.is_stimulating


def test_first_update_failure_raises_in_start(fake, stimulator):
    channels = make_channels()
    stimulator.init_stimulation(list_channels=channels)
    fake.fail_send.add("smpt_send_ml_update")
    with pytest.raises(RuntimeError, match="Failed to send stimulation update"):
        stimulator.start_stimulation(channels, blocking=False, keep_alive_period=PERIOD)
    assert stimulator._continuous is None


def test_callback_exception_stops_stimulation(fake, stimulator):
    def callback(event):
        if event.kind == "keep_alive":
            raise ValueError("boom")

    channels = make_channels()
    start(stimulator, channels, callback=callback)
    wait_until(lambda: not stimulator._continuous.is_alive())
    with pytest.raises(ValueError, match="boom"):
        _ = stimulator.is_stimulating


def test_update_from_callback(fake, stimulator):
    """Closed-loop style: the callback computes the next amplitude and queues it."""
    channels = make_channels()
    amplitudes = iter([22, 24, 26])

    def callback(event):
        if event.kind == "keep_alive":
            amplitude = next(amplitudes, None)
            if amplitude is not None:
                channels[0].set_amplitude(amplitude)
                stimulator.update_stimulation(channels)

    start(stimulator, channels, callback=callback)
    wait_until(lambda: fake.ml_update_amplitudes()[-1:] == [26])
    stimulator.stop_stimulation()
    assert fake.ml_update_amplitudes() == [20, 22, 24, 26, 0]


def test_other_commands_refused_while_running(fake, stimulator):
    channels = make_channels()
    start(stimulator, channels)
    with pytest.raises(RuntimeError, match="non-blocking stimulation is running"):
        stimulator.get_battery_status()
    stimulator.stop_stimulation()
    stimulator.get_battery_status()


def test_duration_stops_automatically(fake, stimulator):
    channels = make_channels()
    start(stimulator, channels, stimulation_duration=0.2)
    assert stimulator.is_stimulating
    wait_until(lambda: not stimulator._continuous.is_alive())
    assert fake.ml_update_amplitudes() == [20, 0]
    with pytest.raises(RuntimeError, match="has ended"):
        stimulator.update_stimulation(channels)
    assert not stimulator.is_stimulating


def test_end_stimulation_joins_thread(fake, stimulator):
    channels = make_channels()
    start(stimulator, channels)
    stimulator.end_stimulation()
    assert not stimulator.is_stimulating
    assert fake.names()[-1] == "smpt_send_ml_stop"
    assert fake.ml_update_amplitudes() == [20]  # no pause needed before Ml_stop
    assert stimulator.stimulation_started is False


def test_init_stimulation_while_running(fake, stimulator):
    channels = make_channels()
    start(stimulator, channels)
    stimulator.init_stimulation(list_channels=channels)
    assert not stimulator.is_stimulating
    assert fake.count("smpt_send_ml_stop") == 1


def test_context_manager(fake):
    channels = make_channels()
    with P24(port="COM_FAKE") as stimulator:
        start(stimulator, channels)
    assert stimulator._continuous is None
    assert fake.names()[-2:] == ["smpt_send_ml_stop", "smpt_close_serial_port"]


def test_parameter_validation(fake, stimulator):
    channels = make_channels()
    stimulator.init_stimulation(list_channels=channels)
    with pytest.raises(ValueError, match="keep_alive_period"):
        stimulator.start_stimulation(channels, blocking=False, keep_alive_period=2.0)
    with pytest.raises(TypeError, match="callable"):
        stimulator.start_stimulation(channels, blocking=False, callback=42)
    assert stimulator._continuous is None
