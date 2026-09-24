"""
Closed-loop control of a stimulator: a user function recomputes the stimulation parameters at a fixed rate.

``ClosedLoopController`` runs a thread that, every ``1 / rate_hz`` seconds:

1. reads the sensors (``SensorSource.read()``, e.g. processed EMG from biosiglive),
2. calls ``controller_fn(t, sensor_data, current_channels)`` to get new target parameters,
3. applies the safety limits (``ChannelLimits``) to the targets,
4. queues the result with ``stimulator.update_stimulation(channels)`` (non-blocking, see
   ``P24.start_stimulation(..., blocking=False)``) if something changed.

The loop uses absolute deadlines (``time.perf_counter``): a late tick does not shift the following ones, and
ticks that are completely missed are skipped (counted as overruns) instead of being run in a burst. Timing
statistics are available at any time with ``ClosedLoopController.stats``.

Safety
------
The limits of ``ChannelLimits`` are applied to every set of parameters before it is sent, including the
initial parameters sent by ``start()``:

* ``max_amplitude`` (mA) and ``max_pulse_width`` (us): hard clamps of the target values.
* ``max_amplitude_step`` (mA) and ``max_pulse_width_step`` (us): largest change allowed per controller tick,
  relative to the last value sent. The maximal slope is therefore ``max_amplitude_step * rate_hz`` mA/s. If the
  controller asks for a larger change, the value moves toward the target by one step per tick (a ramp) until it
  reaches it, even on ticks where ``controller_fn`` returns None.
* ``min_frequency`` / ``max_frequency`` (Hz): clamp of the stimulation frequency.

Going to zero when the controller stops (``stop()``, end of the ``with`` block, error in the controller, the
sensors or the stimulator) is NOT rate limited: ``stimulator.stop_stimulation()`` sends a zero-amplitude
update immediately. The limits are a software safeguard for the controller output only: they do not replace
the device limits, the choice of conservative values for each subject, nor the emergency stop of the device.

Only the channels in SINGLE, DOUBLET or TRIPLET mode are supported (the amplitude and pulse width of a custom
pulse made of points are not defined).
"""

from dataclasses import dataclass
import math
import threading
import time
from typing import Any, Callable, Protocol, runtime_checkable

from .channel import Channel
from .enums import Device, Modes

#  Device limits (see Channel.check_value_param)
DEVICE_MAX_AMPLITUDE = {Device.P24.value: 130.0, Device.Rehastim2.value: 130.0}
DEVICE_MAX_PULSE_WIDTH = {Device.P24.value: 4095, Device.Rehastim2.value: 500}

#  The waiting loop sleeps by chunks of at most this duration, so that stop() is served quickly
_MAX_SLEEP_CHUNK_S = 0.01


@dataclass(frozen=True)
class ChannelLimits:
    """
    Safety limits applied to the output of the controller before it is sent to the stimulator.
    None means "no limit other than the device limit" (no rate limit for the *_step attributes).

    Attributes
    ----------
    max_amplitude : float | None
        Largest amplitude in mA.
    max_pulse_width : int | None
        Largest pulse width in us.
    max_amplitude_step : float | None
        Largest change of amplitude in mA between two consecutive controller ticks (slope limit
        max_amplitude_step * rate_hz in mA/s).
    max_pulse_width_step : float | None
        Largest change of pulse width in us between two consecutive controller ticks.
    min_frequency, max_frequency : float | None
        Allowed range of the stimulation frequency in Hz.
    """

    max_amplitude: float | None = None
    max_pulse_width: int | None = None
    max_amplitude_step: float | None = None
    max_pulse_width_step: float | None = None
    min_frequency: float | None = None
    max_frequency: float | None = None

    def __post_init__(self):
        for name in (
            "max_amplitude",
            "max_pulse_width",
            "min_frequency",
            "max_frequency",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be positive, value given {value}.")
        for name in ("max_amplitude_step", "max_pulse_width_step"):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise ValueError(
                    f"{name} must be strictly positive (or None for no rate limit), value given {value}."
                )
        if (
            self.min_frequency is not None
            and self.max_frequency is not None
            and self.min_frequency > self.max_frequency
        ):
            raise ValueError("min_frequency must be lower than max_frequency.")


@dataclass(frozen=True)
class ChannelState:
    """
    Parameters of one channel, as last sent to the stimulator (after the safety limits).
    A tuple of ChannelState is given to controller_fn as current_channels.
    """

    no_channel: int
    name: str
    amplitude: float
    pulse_width: float
    frequency: float


@dataclass(frozen=True)
class LoopStats:
    """
    Timing statistics of a ClosedLoopController (all times in seconds).

    Attributes
    ----------
    n_ticks : int
        Number of controller ticks run.
    n_updates : int
        Number of update_stimulation calls (ticks where the parameters changed).
    n_overruns : int
        Number of deadlines missed: a tick that started after the next deadline, or whose computation (sensor
        read + controller_fn + update) ended after the next deadline. Missed ticks are skipped.
    elapsed : float
        Time since start().
    mean_rate_hz : float
        n_ticks / elapsed.
    mean_latency, max_latency : float
        Delay between the deadline of a tick and its actual start (scheduling jitter).
    mean_compute_time, max_compute_time : float
        Duration of sensor read + controller_fn + safety + update_stimulation.
    """

    n_ticks: int = 0
    n_updates: int = 0
    n_overruns: int = 0
    elapsed: float = 0.0
    mean_rate_hz: float = 0.0
    mean_latency: float = 0.0
    max_latency: float = 0.0
    mean_compute_time: float = 0.0
    max_compute_time: float = 0.0


@runtime_checkable
class SensorSource(Protocol):
    """
    Anything with a read() method returning the latest sensor data. read() is called from the controller thread
    once per tick, before controller_fn: it should be fast (a blocking read paces, and may delay, the loop; wrap
    slow sources in ThreadedSensor).
    """

    def read(self) -> Any: ...


class CallableSensor:
    """
    SensorSource wrapping a function without argument: read() returns func().
    """

    def __init__(self, func: Callable[[], Any]):
        if not callable(func):
            raise TypeError("func must be callable")
        self.func = func

    def read(self) -> Any:
        return self.func()


class ThreadedSensor:
    """
    Read a slow or blocking SensorSource in its own thread, so that the controller never waits for it.
    read() returns the latest value (None before the first one), or raises the error of the reading thread.

    Can be used as a context manager; it is also started/stopped by ClosedLoopController.start()/stop().
    """

    def __init__(self, source, period: float = 0.0, name: str = "ThreadedSensor"):
        """
        Parameters
        ----------
        source : SensorSource | callable
            The source to read.
        period : float
            Minimal time in s between two reads (0: read continuously, which suits a blocking read paced by the
            device, like most biosiglive interfaces).
        """
        self.source = as_sensor(source)
        self.period = period
        self.name = name
        self._latest = None
        self._error = None
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self):
        try:
            while not self._stop.is_set():
                tic = time.perf_counter()
                value = self.source.read()
                with self._lock:
                    self._latest = value
                remaining = self.period - (time.perf_counter() - tic)
                if remaining > 0:
                    self._stop.wait(remaining)
        except BaseException as e:  # noqa: BLE001 - re-raised in the reader
            self._error = e

    def read(self) -> Any:
        if self._error is not None:
            raise self._error
        with self._lock:
            return self._latest

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()
        return False


class BiosigliveSensor:
    """
    SensorSource reading one device of a biosiglive interface (https://github.com/pyomeca/biosiglive, tested
    against the API of biosiglive 2.0): TcpClient (data from a biosiglive Server), PytrignoClient,
    ViconClient, TrignoSDKClient or any GenericInterface.

    read() calls ``interface.get_device_data(device_name=device_name, **get_kwargs)`` and, if ``process`` is
    True, returns ``interface.get_device(name=device_name).process()`` (the real-time processing configured with
    ``add_device(..., processing_method=...)``, e.g. RealTimeProcessingMethod.ProcessEmg), otherwise the new raw
    frames. The result is a numpy array (n_channels, n_frames); with ``last_frame=True`` only the last frame is
    returned, as an array (n_channels,).

    The interface is used as is (duck typing): biosiglive is only imported by BiosigliveSensor.tcp_client.
    Note that the get_device_data of most biosiglive interfaces blocks until the next frame is available: wrap
    the sensor in ThreadedSensor if its rate is lower than the controller rate.
    """

    def __init__(
        self,
        interface,
        device_name: str,
        process: bool = False,
        last_frame: bool = True,
        get_kwargs: dict = None,
    ):
        if not hasattr(interface, "get_device_data"):
            raise TypeError(
                "interface must be a biosiglive interface (with a get_device_data method)"
            )
        self.interface = interface
        self.device_name = device_name
        self.process = process
        self.last_frame = last_frame
        self.get_kwargs = dict(get_kwargs or {})

    @classmethod
    def tcp_client(
        cls,
        server_ip: str,
        port: int,
        device_name: str,
        nb_channels: int,
        rate: float,
        command_name: str = "proc_device_data",
        read_frequency: float = 100,
        device_type: str = "emg",
        last_frame: bool = True,
        nb_frame_to_get: int = 1,
    ) -> "BiosigliveSensor":
        """
        Create a biosiglive TcpClient connected to a running biosiglive Server (see the biosiglive examples
        server.py / get_from_server.py) and read one of its devices.

        Parameters
        ----------
        server_ip, port : str, int
            Address of the biosiglive server ("127.0.0.1" rather than "localhost" on the same computer).
        device_name : str
            Name given to the device.
        nb_channels : int
            Number of channels of the device.
        rate : float
            Rate of the device in Hz.
        command_name : str
            Key of the data in the dictionary streamed by the server (e.g. "proc_device_data").
        read_frequency : float
            Read frequency given to the TcpClient.
        device_type : str
            biosiglive DeviceType name ("emg", "imu", "generic"...).
        nb_frame_to_get : int
            Number of frames asked to the server at each read.
        """
        try:
            from biosiglive import DeviceType, TcpClient
        except ImportError as e:
            raise ImportError(
                "BiosigliveSensor.tcp_client requires biosiglive (https://github.com/pyomeca/biosiglive), "
                "e.g. 'conda install -c conda-forge biosiglive' or 'pip install biosiglive'."
            ) from e
        client = TcpClient(server_ip, port, read_frequency=read_frequency)
        client.add_device(
            nb_channels,
            command_name=command_name,
            device_type=(
                DeviceType(device_type) if isinstance(device_type, str) else device_type
            ),
            name=device_name,
            rate=rate,
        )
        return cls(
            client,
            device_name,
            process=False,
            last_frame=last_frame,
            get_kwargs={"nb_frame_to_get": nb_frame_to_get},
        )

    def read(self):
        import numpy as np

        data = self.interface.get_device_data(
            device_name=self.device_name, **self.get_kwargs
        )
        if self.process:
            data = self.interface.get_device(name=self.device_name).process()
        data = np.asarray(data)
        if self.last_frame and data.ndim >= 2:
            data = data[..., -1]
        return data


def as_sensor(source) -> SensorSource:
    """
    Return source if it has a read() method, a CallableSensor if it is callable.
    """
    if hasattr(source, "read") and callable(source.read):
        return source
    if callable(source):
        return CallableSensor(source)
    raise TypeError("A sensor must have a read() method or be callable")


def _limit_step(target: float, previous: float, max_step: float | None) -> float:
    if max_step is None:
        return target
    return min(max(target, previous - max_step), previous + max_step)


def _clamp(value: float, low: float | None, high: float | None) -> float:
    if low is not None and value < low:
        value = low
    if high is not None and value > high:
        value = high
    return value


class ClosedLoopController:
    """
    Run controller_fn at a fixed rate and send its output to a stimulator, through the safety limits.

    Example::

        def controller(t, emg, channels):
            return {1: 5 + 30 * emg[0]}  # amplitude of channel 1 in mA

        stimulator.init_stimulation(list_channels=channels)
        limits = ChannelLimits(max_amplitude=40, max_amplitude_step=2)
        with ClosedLoopController(stimulator, controller, rate_hz=50, sensors=emg_sensor, safety=limits) as loop:
            time.sleep(10)
        print(loop.stats)

    Threading: controller_fn and the sensors' read() run in the controller thread. An exception raised by one of
    them, or by the stimulator (e.g. an electrode error of the P24 stimulation thread), stops the loop, pauses
    the stimulation, and is re-raised in the caller thread by stop(), check(), is_running or the end of the with
    block.
    """

    def __init__(
        self,
        stimulator,
        controller_fn: Callable,
        rate_hz: float,
        sensors=None,
        safety: ChannelLimits | dict | None = None,
        channels: list = None,
        name: str = "ClosedLoopController",
    ):
        """
        Parameters
        ----------
        stimulator : P24
            The stimulator, with the mid level initialized (init_stimulation). It must support
            start_stimulation(..., blocking=False), update_stimulation, stop_stimulation and is_stimulating.
        controller_fn : callable
            controller_fn(t, sensor_data, current_channels) called at each tick, where t is the time in s since
            start(), sensor_data the output of the sensors (see below) and current_channels a tuple of
            ChannelState (parameters last sent, after the safety limits). It returns:
              * None: keep the previous targets (nothing is sent, unless a rate-limited ramp toward the previous
                targets is still in progress);
              * a dict {channel: change} where channel is the channel number (int, 1-8) or name (str) and change
                is either a number (new amplitude in mA) or a dict with any of the keys "amplitude",
                "pulse_width", "frequency". Channels not in the dict keep their targets;
              * a list of Channel: the targets are read from the amplitude, pulse width and frequency of each
                Channel (matched by channel number). The Channel objects are not kept nor modified.
        rate_hz : float
            Rate of the controller in Hz. With the P24, updates are coalesced by the stimulation thread, so
            rates much higher than the stimulation frequency are useless.
        sensors : SensorSource | callable | dict | None
            None: sensor_data is None. A SensorSource (or a callable): sensor_data = sensors.read(). A dict
            {name: SensorSource or callable}: sensor_data = {name: read()}.
        safety : ChannelLimits | dict | None
            Limits applied to every channel (ChannelLimits), or a dict {channel number: ChannelLimits} (channels
            not in the dict use the key None if present, the device limits otherwise). None: device limits only.
            See the module documentation.
        channels : list[Channel]
            Channels to control. Default: stimulator.list_channels (the channels given to init_stimulation).
            The initial targets are their current parameters. The Channel objects are copied.
        """
        if not callable(controller_fn):
            raise TypeError("controller_fn must be callable")
        if not rate_hz or rate_hz <= 0 or not math.isfinite(rate_hz):
            raise ValueError(
                f"rate_hz must be strictly positive, value given {rate_hz}."
            )
        channels = (
            channels
            if channels is not None
            else getattr(stimulator, "list_channels", None)
        )
        if not channels:
            raise ValueError(
                "No channel to control: call stimulator.init_stimulation first or give channels."
            )
        for channel in channels:
            if channel.get_mode() == Modes.NONE.value:
                raise ValueError(
                    f"Channel {channel.get_no_channel()} uses a custom pulse (mode None): only the SINGLE, "
                    "DOUBLET and TRIPLET modes are supported by the closed loop."
                )

        self.stimulator = stimulator
        self.controller_fn = controller_fn
        self.rate_hz = float(rate_hz)
        self.period = 1.0 / self.rate_hz
        self.name = name

        if sensors is None:
            self._sensors = None
        elif isinstance(sensors, dict):
            self._sensors = {key: as_sensor(value) for key, value in sensors.items()}
        else:
            self._sensors = as_sensor(sensors)

        if safety is None:
            safety = ChannelLimits()
        if not isinstance(safety, ChannelLimits | dict):
            raise TypeError(
                "safety must be a ChannelLimits, a dict {channel: ChannelLimits} or None"
            )
        self._safety = safety

        #  Own copies of the channels: only the controller thread modifies them after start()
        self._channels = [self._copy_channel(channel) for channel in channels]
        self._by_number = {c.get_no_channel(): c for c in self._channels}
        self._by_name = {c.get_name(): c for c in self._channels}
        #  Targets asked by the controller, per channel number: [amplitude, pulse_width, frequency]
        self._targets = {
            c.get_no_channel(): [
                c.get_amplitude(),
                c.get_pulse_width(),
                c.get_frequency(),
            ]
            for c in self._channels
        }
        #  The initial parameters are only clamped (no previous value to rate limit against)
        for channel in self._channels:
            self._apply_limits(channel, rate_limit=False)

        self._thread = None
        self._stop_event = threading.Event()
        self._error = None
        self._error_raised = False
        self._stimulation_stopped = False
        self._pause_lock = threading.Lock()
        self._t0 = None
        self._stats_lock = threading.Lock()
        self._reset_stats()

    #  Public API
    def start(self):
        """
        Start the non-blocking stimulation with the initial (limited) parameters if it is not running yet,
        then the controller thread. Returns immediately.
        """
        if self._thread is not None:
            raise RuntimeError(
                "The controller was already started (create a new one to restart)."
            )
        self._start_sensors()
        try:
            if self.stimulator.is_stimulating:
                self.stimulator.update_stimulation(self._channels)
            else:
                self.stimulator.start_stimulation(
                    upd_list_channels=self._channels, blocking=False
                )
        except BaseException:
            self._stop_sensors()
            raise
        self._reset_stats()
        self._t0 = time.perf_counter()
        self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self._thread.start()
        return self

    def stop(self, timeout: float = 3.0):
        """
        Stop the controller thread and pause the stimulation (zero-amplitude update, not rate limited, then
        stimulator.stop_stimulation()). Re-raises the error that stopped the loop, if any (only once). Safe to
        call several times.
        """
        self._stop_event.set()
        errors = []
        try:
            if (
                self._thread is not None
                and self._thread is not threading.current_thread()
            ):
                self._thread.join(timeout)
                if self._thread.is_alive():
                    errors.append(
                        TimeoutError(
                            f"The controller thread did not stop within {timeout} s "
                            "(controller_fn or a sensor read is blocking?)."
                        )
                    )
        finally:
            try:
                self._pause_stimulation()
            except BaseException as e:  # noqa: BLE001
                errors.append(e)
            self._stop_sensors()
        if self._error is not None and not self._error_raised:
            self._error_raised = True
            raise self._error
        if errors:
            raise errors[0]

    def check(self):
        """
        Re-raise, in the caller thread, the error that stopped the controller (only once).
        """
        if self._error is not None and not self._error_raised:
            if self._thread is not None:
                self._thread.join(1.0)
            self._error_raised = True
            raise self._error

    @property
    def is_running(self) -> bool:
        """True while the controller thread runs. Raises the error that stopped it, if any."""
        self.check()
        return self._thread is not None and self._thread.is_alive()

    def join(self, timeout: float = None):
        """Wait for the controller thread to end (after stop() or an error), then re-raise its error if any."""
        if self._thread is not None:
            self._thread.join(timeout)
        self.check()

    @property
    def stats(self) -> LoopStats:
        """Snapshot of the timing statistics."""
        with self._stats_lock:
            n = self._n_ticks
            elapsed = (
                (self._t_end if self._t_end is not None else time.perf_counter())
                - self._t0
                if self._t0 is not None
                else 0.0
            )
            return LoopStats(
                n_ticks=n,
                n_updates=self._n_updates,
                n_overruns=self._n_overruns,
                elapsed=elapsed,
                mean_rate_hz=n / elapsed if elapsed > 0 else 0.0,
                mean_latency=self._sum_latency / n if n else 0.0,
                max_latency=self._max_latency,
                mean_compute_time=self._sum_compute / n if n else 0.0,
                max_compute_time=self._max_compute,
            )

    @property
    def current_channels(self) -> tuple:
        """Parameters last sent to the stimulator (tuple of ChannelState)."""
        return self._channel_states()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.stop()
        except BaseException:
            if exc_type is None:
                raise
        return False

    #  Internals
    @staticmethod
    def _copy_channel(channel: Channel) -> Channel:
        return Channel(
            mode=Modes(channel.get_mode()),
            no_channel=channel.get_no_channel(),
            amplitude=channel.get_amplitude(),
            pulse_width=channel.get_pulse_width(),
            enable_low_frequency=channel.get_enable_low_frequency(),
            name=channel.get_name(),
            device_type=Device(channel.get_device_type()),
            frequency=channel.get_frequency(),
            ramp=channel.get_ramp(),
        )

    def _limits(self, no_channel: int) -> ChannelLimits:
        if isinstance(self._safety, ChannelLimits):
            return self._safety
        return self._safety.get(no_channel, self._safety.get(None, ChannelLimits()))

    def _apply_limits(self, channel: Channel, rate_limit: bool = True) -> bool:
        """
        Move channel toward its targets within the limits. Returns True if a parameter changed.
        """
        no_channel = channel.get_no_channel()
        limits = self._limits(no_channel)
        device = channel.get_device_type()
        amplitude, pulse_width, frequency = self._targets[no_channel]

        max_amplitude = DEVICE_MAX_AMPLITUDE.get(device, 130.0)
        if limits.max_amplitude is not None:
            max_amplitude = min(max_amplitude, limits.max_amplitude)
        max_pulse_width = DEVICE_MAX_PULSE_WIDTH.get(device, 4095)
        if limits.max_pulse_width is not None:
            max_pulse_width = min(max_pulse_width, limits.max_pulse_width)

        amplitude = _clamp(float(amplitude), 0.0, max_amplitude)
        pulse_width = _clamp(float(pulse_width), 0.0, max_pulse_width)
        frequency = _clamp(float(frequency), limits.min_frequency, limits.max_frequency)
        if rate_limit:
            amplitude = _limit_step(
                amplitude, channel.get_amplitude(), limits.max_amplitude_step
            )
            pulse_width = _limit_step(
                pulse_width, channel.get_pulse_width(), limits.max_pulse_width_step
            )
        pulse_width = int(round(pulse_width))
        if pulse_width > max_pulse_width:  # rounding
            pulse_width -= 1

        changed = False
        if amplitude != channel.get_amplitude():
            channel._amplitude = amplitude
            changed = True
        if pulse_width != channel.get_pulse_width():
            channel._pulse_width = pulse_width
            changed = True
        if not math.isclose(frequency, channel.get_frequency()):
            channel._period = 1000.0 / frequency
            changed = True
        if changed:
            channel.check_value_param()
            channel.generate_pulse()
        return changed

    def _set_targets(self, result):
        if isinstance(result, dict):
            for key, change in result.items():
                channel = self._find_channel(key)
                target = self._targets[channel.get_no_channel()]
                if isinstance(change, dict):
                    unknown = set(change) - {"amplitude", "pulse_width", "frequency"}
                    if unknown:
                        raise KeyError(
                            f"Unknown parameter(s) {sorted(unknown)} for channel {key}: allowed keys are "
                            "'amplitude', 'pulse_width' and 'frequency'."
                        )
                    for index, param in enumerate(
                        ("amplitude", "pulse_width", "frequency")
                    ):
                        if param in change:
                            target[index] = self._check_number(
                                change[param], param, key
                            )
                else:
                    target[0] = self._check_number(change, "amplitude", key)
        elif isinstance(result, list | tuple):
            for new in result:
                if not isinstance(new, Channel):
                    raise TypeError(
                        "controller_fn must return None, a dict or a list of Channel, "
                        f"got a list containing {type(new).__name__}."
                    )
                channel = self._find_channel(new.get_no_channel())
                self._targets[channel.get_no_channel()] = [
                    self._check_number(
                        new.get_amplitude(), "amplitude", new.get_no_channel()
                    ),
                    self._check_number(
                        new.get_pulse_width(), "pulse_width", new.get_no_channel()
                    ),
                    self._check_number(
                        new.get_frequency(), "frequency", new.get_no_channel()
                    ),
                ]
        else:
            raise TypeError(
                f"controller_fn must return None, a dict or a list of Channel, got {type(result).__name__}."
            )

    @staticmethod
    def _check_number(value, param, key) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise TypeError(
                f"The {param} of channel {key} must be a number, got {value!r}."
            ) from None
        if not math.isfinite(value):
            raise ValueError(
                f"The {param} of channel {key} must be finite, got {value}."
            )
        if param == "frequency" and value <= 0:
            raise ValueError(
                f"The frequency of channel {key} must be positive, got {value}."
            )
        return value

    def _find_channel(self, key) -> Channel:
        if isinstance(key, str):
            channel = self._by_name.get(key)
        else:
            channel = self._by_number.get(key)
        if channel is None:
            raise KeyError(
                f"Unknown channel {key!r}: controlled channels are {sorted(self._by_number)} "
                f"({sorted(self._by_name)})."
            )
        return channel

    def _channel_states(self) -> tuple:
        return tuple(
            ChannelState(
                no_channel=c.get_no_channel(),
                name=c.get_name(),
                amplitude=c.get_amplitude(),
                pulse_width=c.get_pulse_width(),
                frequency=c.get_frequency(),
            )
            for c in self._channels
        )

    def _read_sensors(self):
        if self._sensors is None:
            return None
        if isinstance(self._sensors, dict):
            return {key: sensor.read() for key, sensor in self._sensors.items()}
        return self._sensors.read()

    def _all_sensors(self) -> list:
        if self._sensors is None:
            return []
        if isinstance(self._sensors, dict):
            return list(self._sensors.values())
        return [self._sensors]

    def _start_sensors(self):
        for sensor in self._all_sensors():
            if isinstance(sensor, ThreadedSensor):
                sensor.start()

    def _stop_sensors(self):
        for sensor in self._all_sensors():
            if isinstance(sensor, ThreadedSensor):
                sensor.stop()

    def _reset_stats(self):
        with self._stats_lock:
            self._n_ticks = 0
            self._n_updates = 0
            self._n_overruns = 0
            self._sum_latency = 0.0
            self._max_latency = 0.0
            self._sum_compute = 0.0
            self._max_compute = 0.0
            self._t_end = None

    def _tick(self, t: float) -> bool:
        sensor_data = self._read_sensors()
        result = self.controller_fn(t, sensor_data, self._channel_states())
        if result is not None:
            self._set_targets(result)
        changed = False
        for channel in self._channels:
            changed |= self._apply_limits(channel)
        if changed:
            self.stimulator.update_stimulation(self._channels)
        return changed

    def _run(self):
        period = self.period
        deadline = self._t0
        try:
            while not self._stop_event.is_set():
                start = time.perf_counter()
                latency = start - deadline
                changed = self._tick(start - self._t0)
                end = time.perf_counter()

                #  Next absolute deadline; skip the ticks that are already missed
                deadline += period
                overrun = False
                if end > deadline:
                    overrun = True
                    missed = math.floor((end - deadline) / period) + 1
                    deadline += missed * period
                with self._stats_lock:
                    self._n_ticks += 1
                    self._n_updates += changed
                    self._n_overruns += overrun
                    self._sum_latency += latency
                    self._max_latency = max(self._max_latency, latency)
                    compute = end - start
                    self._sum_compute += compute
                    self._max_compute = max(self._max_compute, compute)

                #  time.sleep has a high resolution on Windows since Python 3.11 (Event.wait has not)
                while not self._stop_event.is_set():
                    remaining = deadline - time.perf_counter()
                    if remaining <= 0:
                        break
                    time.sleep(min(remaining, _MAX_SLEEP_CHUNK_S))
        except BaseException as e:  # noqa: BLE001 - re-raised in the caller thread
            self._error = e
            try:
                self._pause_stimulation()
            except BaseException:  # noqa: BLE001 - the first error is the relevant one
                pass
        finally:
            with self._stats_lock:
                self._t_end = time.perf_counter()

    def _pause_stimulation(self):
        """Zero the stimulation immediately (no rate limit) and stop the stimulation thread. Done once."""
        with self._pause_lock:
            if self._stimulation_stopped or self._thread is None:
                return
            self._stimulation_stopped = True
            self.stimulator.stop_stimulation(pause=True)
