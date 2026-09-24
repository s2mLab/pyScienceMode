"""
Tests of the closed-loop controller, without hardware (P24 on the fake sciencemode lib, see tests/fake_sciencemode.py).
Timing tolerances are loose on purpose: CI machines are noisy.
"""

import threading
import time

import numpy as np
import pytest

from pysciencemode import (
    P24,
    BiosigliveSensor,
    Channel,
    ChannelLimits,
    ChannelState,
    ClosedLoopController,
    Device,
    Modes,
    ThreadedSensor,
)
from tests.fake_sciencemode import install_fake_sciencemode


@pytest.fixture
def fake(monkeypatch):
    return install_fake_sciencemode(monkeypatch)


@pytest.fixture
def stimulator(fake):
    stim = P24(port="COM_FAKE")
    yield stim
    stim._stop_continuous(pause=False, raise_error=False)


def make_channels(amplitude=10, numbers=(1,)):
    return [
        Channel(
            mode=Modes.SINGLE,
            no_channel=n,
            amplitude=amplitude,
            pulse_width=300,
            frequency=50,
            name=f"muscle_{n}",
            device_type=Device.P24,
        )
        for n in numbers
    ]


def init(stimulator, **kwargs):
    channels = make_channels(**kwargs)
    stimulator.init_stimulation(list_channels=channels)
    return channels


def wait_until(condition, timeout=2.0):
    end = time.perf_counter() + timeout
    while not condition():
        if time.perf_counter() > end:
            raise AssertionError("Condition not met in time")
        time.sleep(0.005)


def test_rate_and_stats(fake, stimulator):
    init(stimulator)
    times = []

    def controller(t, data, channels):
        times.append(time.perf_counter())
        return None

    loop = ClosedLoopController(stimulator, controller, rate_hz=100)
    loop.start()
    time.sleep(1.0)
    loop.stop()
    stats = loop.stats
    assert 70 <= len(times) <= 105
    assert stats.n_ticks == len(times)
    assert 70 <= stats.mean_rate_hz <= 105
    #  Absolute deadlines: no drift, even if individual ticks are late
    assert times[-1] - times[0] == pytest.approx((len(times) - 1) / 100, abs=0.05)
    assert stats.mean_latency < 0.01
    assert stats.n_updates == 0
    assert not loop.is_running


def test_controller_none_sends_nothing(fake, stimulator):
    init(stimulator)
    loop = ClosedLoopController(stimulator, lambda t, d, c: None, rate_hz=200)
    with loop:
        time.sleep(0.2)
    #  Initial update, final zero update: nothing in between
    assert fake.ml_update_amplitudes() == [10, 0]
    assert loop.stats.n_ticks > 10


def test_dict_updates_and_sensor(fake, stimulator):
    init(stimulator, numbers=(1, 2))
    values = iter([0.5, 1.0])
    received = []

    def controller(t, emg, channels):
        received.append((emg, channels))
        if emg is None:
            return None
        return {1: 20 * emg, "muscle_2": {"pulse_width": 250, "frequency": 40}}

    sensor = lambda: next(values, None)  # noqa: E731 - callable sensors are accepted
    with ClosedLoopController(
        stimulator, controller, rate_hz=100, sensors=sensor
    ) as loop:
        wait_until(lambda: loop.stats.n_ticks >= 4)
        stimulator._continuous.wait_applied(3, 1.0)
    assert fake.ml_update_amplitudes(0) == [10, 10, 20, 0]
    last_before_stop = fake.of("smpt_send_ml_update")[-2].data
    period, _, points = last_before_stop[1]
    assert period == pytest.approx(25.0)  # 40 Hz
    assert points[0] == (250, 10)
    #  current_channels reflect what was sent
    emg, channels = received[1]
    assert isinstance(channels[0], ChannelState)
    assert channels[0].amplitude == 10 and channels[1].pulse_width == 250


def test_dict_of_sensors(fake, stimulator):
    init(stimulator)
    got = []

    class Source:
        def read(self):
            return 3

    def controller(t, data, channels):
        got.append(data)

    with ClosedLoopController(
        stimulator, controller, rate_hz=100, sensors={"a": Source(), "b": lambda: 4}
    ):
        wait_until(lambda: len(got) >= 1)
    assert got[0] == {"a": 3, "b": 4}


def test_list_of_channels_is_copied(fake, stimulator):
    user_channels = init(stimulator)
    new = make_channels(amplitude=25)

    def controller(t, data, channels):
        return new

    with ClosedLoopController(stimulator, controller, rate_hz=100) as loop:
        wait_until(lambda: loop.stats.n_updates >= 1)
        stimulator._continuous.wait_applied(2, 1.0)
    assert fake.ml_update_amplitudes() == [10, 25, 0]
    assert user_channels[0].get_amplitude() == 10  # the user objects are not modified
    assert new[0].get_amplitude() == 25


def test_clamping_and_rate_limit(fake, stimulator):
    init(stimulator, amplitude=50)  # above max_amplitude: clamped at start too
    limits = ChannelLimits(max_amplitude=30, max_amplitude_step=4, max_pulse_width=200)
    calls = []

    def controller(t, data, channels):
        calls.append(channels[0].amplitude)
        return {1: {"amplitude": 0 if len(calls) <= 3 else 100, "pulse_width": 1000}}

    with ClosedLoopController(
        stimulator, controller, rate_hz=200, safety=limits
    ) as loop:
        wait_until(lambda: loop.current_channels[0].amplitude == 30 and len(calls) > 12)
        time.sleep(0.05)
    sent = fake.ml_update_amplitudes()
    assert sent[0] == 30  # initial value clamped
    assert sent[-1] == 0  # stop is immediate, not rate limited
    ramp = sent[:-1]
    assert max(ramp) == 30
    assert all(abs(b - a) <= 4 + 1e-9 for a, b in zip(ramp, ramp[1:]))
    assert ramp[:4] == [30, 26, 22, 18]  # going down by steps of 4
    widths = {call.data[0][2][0][0] for call in fake.of("smpt_send_ml_update")}
    assert widths == {200}


def test_rate_limit_continues_when_controller_returns_none(fake, stimulator):
    init(stimulator, amplitude=0)
    limits = ChannelLimits(max_amplitude_step=5)
    first = [True]

    def controller(t, data, channels):
        if first[0]:
            first[0] = False
            return {1: 20}
        return None

    with ClosedLoopController(
        stimulator, controller, rate_hz=200, safety=limits
    ) as loop:
        wait_until(lambda: loop.current_channels[0].amplitude == 20)
        stimulator._continuous.wait_applied(5, 1.0)
    assert loop.stats.n_updates == 4  # 4 ticks to ramp from 0 to 20 by steps of 5
    sent = fake.ml_update_amplitudes()
    #  The P24 thread may coalesce queued updates (latest wins), hence the subset
    assert set(sent) <= {0, 5, 10, 15, 20} and sent[-2:] == [20, 0]


def test_per_channel_limits(fake, stimulator):
    init(stimulator, numbers=(1, 2))
    safety = {1: ChannelLimits(max_amplitude=15), None: ChannelLimits(max_amplitude=25)}
    with ClosedLoopController(
        stimulator, lambda t, d, c: {1: 100, 2: 100}, rate_hz=100, safety=safety
    ) as loop:
        wait_until(lambda: loop.stats.n_updates >= 1)
        states = loop.current_channels
    assert (states[0].amplitude, states[1].amplitude) == (15, 25)


def test_exception_propagates_and_stimulation_is_zeroed(fake, stimulator):
    init(stimulator)

    def controller(t, data, channels):
        if t > 0.05:
            raise ValueError("boom")
        return {1: 20}

    loop = ClosedLoopController(stimulator, controller, rate_hz=100)
    loop.start()
    wait_until(lambda: loop._thread is not None and not loop._thread.is_alive())
    #  Stimulation already paused by the controller thread
    assert fake.ml_update_amplitudes()[-1] == 0
    assert not stimulator.is_stimulating
    with pytest.raises(ValueError, match="boom"):
        loop.stop()
    loop.stop()  # raised only once, stop is idempotent
    assert fake.ml_update_amplitudes() == [10, 20, 0]


def test_exception_in_with_block(fake, stimulator):
    init(stimulator)

    def controller(t, data, channels):
        raise RuntimeError("controller failed")

    with pytest.raises(RuntimeError, match="controller failed"):
        with ClosedLoopController(stimulator, controller, rate_hz=100) as loop:
            loop.join(timeout=2.0)
    assert fake.ml_update_amplitudes() == [10, 0]


def test_sensor_exception_propagates(fake, stimulator):
    init(stimulator)

    def sensor():
        raise OSError("sensor lost")

    loop = ClosedLoopController(
        stimulator, lambda t, d, c: None, rate_hz=100, sensors=sensor
    )
    loop.start()
    with pytest.raises(OSError, match="sensor lost"):
        loop.join(timeout=2.0)
    loop.stop()
    assert not stimulator.is_stimulating


def test_stimulator_error_propagates(fake, stimulator):
    init(stimulator)
    counter = [0]

    def controller(t, data, channels):
        counter[0] += 1
        return {1: 10 + counter[0] % 2}  # an update at every tick

    loop = ClosedLoopController(stimulator, controller, rate_hz=100)
    loop.start()
    fake.channel_states[0] = fake.lib.Smpt_Ml_Channel_State_Electrode_Error
    with pytest.raises(RuntimeError, match="Electrode error on channel 1"):
        loop.join(timeout=3.0)
    loop.stop()
    assert not stimulator.is_stimulating
    assert fake.ml_update_amplitudes()[-1] == 0


def test_invalid_return_type(fake, stimulator):
    init(stimulator)
    loop = ClosedLoopController(stimulator, lambda t, d, c: 42, rate_hz=100)
    loop.start()
    with pytest.raises(TypeError, match="must return None"):
        loop.join(timeout=2.0)
    loop.stop()


def test_unknown_channel_and_nan(fake, stimulator):
    init(stimulator)
    for result, error in (({5: 10}, KeyError), ({1: float("nan")}, ValueError)):
        loop = ClosedLoopController(
            stimulator, lambda t, d, c, r=result: r, rate_hz=100
        )
        loop.start()
        with pytest.raises(error):
            loop.join(timeout=2.0)
        loop.stop()


def test_stop_joins_and_stops_updates(fake, stimulator):
    init(stimulator)
    loop = ClosedLoopController(
        stimulator, lambda t, d, c: {1: 10 + int(t * 100) % 5}, rate_hz=100
    )
    loop.start()
    time.sleep(0.1)
    tic = time.perf_counter()
    loop.stop()
    assert time.perf_counter() - tic < 0.5
    assert not any(t.name == "ClosedLoopController" for t in threading.enumerate())
    assert not stimulator.is_stimulating
    assert stimulator._continuous is None
    n = len(fake.calls)
    time.sleep(0.1)
    assert len(fake.calls) == n
    assert fake.ml_update_amplitudes()[-1] == 0
    with pytest.raises(RuntimeError, match="already started"):
        loop.start()


def test_uses_running_stimulation(fake, stimulator):
    channels = init(stimulator)
    stimulator.start_stimulation(channels, blocking=False, keep_alive_period=0.05)
    thread = stimulator._continuous.thread
    with ClosedLoopController(stimulator, lambda t, d, c: {1: 15}, rate_hz=100) as loop:
        wait_until(lambda: loop.stats.n_updates >= 1)
        assert stimulator._continuous.thread is thread
    assert not stimulator.is_stimulating


def test_overruns_are_counted_and_skipped(fake, stimulator):
    init(stimulator)
    times = []

    def slow(t, data, channels):
        times.append(t)
        time.sleep(0.035)  # 3.5 periods

    with ClosedLoopController(stimulator, slow, rate_hz=100) as loop:
        time.sleep(0.5)
    stats = loop.stats
    assert stats.n_overruns == stats.n_ticks or stats.n_overruns >= stats.n_ticks - 1
    assert stats.max_compute_time >= 0.03
    #  No burst after a late tick: consecutive ticks stay ~4 periods apart
    intervals = np.diff(times)
    assert intervals.min() > 0.03


def test_parameter_validation(fake, stimulator):
    init(stimulator)
    with pytest.raises(ValueError, match="rate_hz"):
        ClosedLoopController(stimulator, lambda *a: None, rate_hz=0)
    with pytest.raises(TypeError, match="callable"):
        ClosedLoopController(stimulator, 42, rate_hz=10)
    with pytest.raises(TypeError, match="safety"):
        ClosedLoopController(stimulator, lambda *a: None, rate_hz=10, safety=3)
    with pytest.raises(ValueError, match="max_amplitude_step"):
        ChannelLimits(max_amplitude_step=0)
    custom = Channel(no_channel=1, device_type=Device.P24)
    custom.add_point(300, 10)
    custom.add_point(300, -10)
    with pytest.raises(ValueError, match="custom pulse"):
        ClosedLoopController(stimulator, lambda *a: None, rate_hz=10, channels=[custom])
    with pytest.raises(ValueError, match="No channel"):
        ClosedLoopController(P24(port="COM_FAKE"), lambda *a: None, rate_hz=10)


def test_threaded_sensor():
    counter = [0]

    def blocking_read():
        time.sleep(0.02)
        counter[0] += 1
        return counter[0]

    sensor = ThreadedSensor(blocking_read)
    assert sensor.read() is None
    with sensor:
        wait_until(lambda: sensor.read() is not None and sensor.read() >= 2)
        tic = time.perf_counter()
        sensor.read()
        assert time.perf_counter() - tic < 0.01  # never blocks

    def failing():
        raise OSError("gone")

    sensor = ThreadedSensor(failing)
    with sensor:
        wait_until(lambda: sensor._error is not None)
        with pytest.raises(OSError, match="gone"):
            sensor.read()


class FakeBiosigliveDevice:
    def __init__(self):
        self.new_data = None

    def process(self):
        return np.abs(self.new_data) * 2


class FakeBiosigliveInterface:
    """Mimics the biosiglive 2.0 GenericInterface API used by BiosigliveSensor."""

    def __init__(self):
        self.devices = [FakeBiosigliveDevice()]
        self.calls = []

    def get_device_data(self, device_name="all", **kwargs):
        self.calls.append((device_name, kwargs))
        data = -np.arange(6, dtype=float).reshape(2, 3)
        self.devices[0].new_data = data
        return data

    def get_device(self, name=None, idx=None):
        assert name == "emg"
        return self.devices[0]


def test_biosiglive_sensor():
    interface = FakeBiosigliveInterface()
    raw = BiosigliveSensor(interface, "emg", get_kwargs={"nb_frame_to_get": 3})
    np.testing.assert_array_equal(raw.read(), [-2, -5])
    assert interface.calls[-1] == ("emg", {"nb_frame_to_get": 3})
    processed = BiosigliveSensor(interface, "emg", process=True, last_frame=False)
    assert processed.read().shape == (2, 3)
    np.testing.assert_array_equal(processed.read()[:, -1], [4, 10])
    with pytest.raises(TypeError):
        BiosigliveSensor(object(), "emg")


def test_biosiglive_missing_gives_clear_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "biosiglive" or name.startswith("biosiglive."):
            raise ImportError("No module named 'biosiglive'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError, match="requires biosiglive"):
        BiosigliveSensor.tcp_client("127.0.0.1", 50000, "emg", nb_channels=2, rate=2000)


def test_emg_proportional_control_end_to_end(fake, stimulator):
    """The scenario of the example: amplitude proportional to a (fake) EMG envelope."""
    init(stimulator, amplitude=0)
    envelope = [0.0]
    limits = ChannelLimits(max_amplitude=30, max_amplitude_step=10)

    def controller(t, emg, channels):
        return {1: 40 * emg}

    with ClosedLoopController(
        stimulator, controller, rate_hz=100, sensors=lambda: envelope[0], safety=limits
    ) as loop:
        envelope[0] = 0.5
        wait_until(lambda: loop.current_channels[0].amplitude == 20)
        envelope[0] = 1.0
        wait_until(lambda: loop.current_channels[0].amplitude == 30)  # clamped
        time.sleep(0.05)
    sent = fake.ml_update_amplitudes()
    assert max(sent) == 30 and sent[-1] == 0
