"""
Play a ``StimulationProfile`` (e.g. optimized with cocofest) on a P24, with the non-blocking mid-level API.

How it works
------------
1. The pulse train of every muscle is grouped into constant-frequency segments (``ChannelProfile.to_segments``):
   consecutive pulses with the same inter-pulse interval (IPI), pulse width and amplitude become one segment
   stimulated at ``frequency = 1 / IPI``. The segments of all the channels are merged into a list of global
   states, each one sent as a single ``Ml_update`` (all channels are updated together by the P24).
2. ``start_stimulation(..., blocking=False)`` sends the first state. Its ack defines the profile time 0.
3. A player thread sleeps until the absolute deadline ``t0 + t_k`` of every next state (no drift accumulates) and
   queues it with ``update_stimulation(wait=False)``. The stimulation thread of the P24 sends it and reports the
   ack time through its callback.
4. After the last state (all amplitudes at zero at ``profile.end_time``), ``stop_stimulation`` is called.

Timing accuracy: read before use
--------------------------------
* The updates are timed by the host, not by the device. The planned time of a state is the time at which its
  ``Ml_update`` is *acknowledged*; the delay between the command and the next pulse delivered by the device, and
  the phase of the pulses relative to the update, are not documented by HASOMED nor measured here. Expect the
  pulses of a new segment to occur up to one period after the update.
* The achieved times include the OS scheduling jitter (about 1-2 ms on Linux/macOS, up to ~15 ms on Windows
  without a high-resolution timer), the USB/serial round trip of the ``Ml_update`` (a few ms) and, when a
  keep-alive (``Ml_get_current_data``, sent every ``keep_alive_period`` <= 1.5 s to beat the 2 s device timeout)
  is in flight, its round trip too.
* Consequently, frequency segments lasting at least a few hundred ms are reproduced faithfully, while profiles
  whose every IPI differs (optimized pulse onsets, one update per pulse) are reproduced only approximately: each
  pulse is emitted by a one-pulse segment and the pulse count at segment edges can be off by one. Updates planned
  closer than the device round trip can be superseded (the stimulation thread only sends the latest request):
  they are reported as ``skipped``.
* ``PlaybackReport`` gives, for every update, the planned and achieved (ack) times, so the accuracy of a run can
  be checked afterwards. It does not observe the actual pulses: measure them (EMG artefact, oscilloscope) to
  validate a protocol.
"""

from dataclasses import dataclass, field
import math
import statistics
import threading
import time
from typing import Callable

from .channel import Channel
from .enums import Device, Modes
from .p24_continuous import DEFAULT_KEEP_ALIVE_PERIOD_S, StimulationEvent
from .profiles import P24_LIMITS, StimulationLimits, StimulationProfile, merge_segment_events


@dataclass
class PlannedUpdate:
    """
    One mid-level update of the schedule.

    Attributes
    ----------
    index : int
        Index in the schedule (0 is sent by start_stimulation).
    t : float
        Planned time in s relative to the start of the profile.
    state : dict
        {channel number: (frequency Hz, pulse width us, amplitude mA)} sent to the device. Amplitude 0 = off.
    requested : float | None
        Time (relative to t0) at which the update was queued to the stimulation thread.
    acked : float | None
        Time (relative to t0) at which the device acknowledged it. None if it was superseded by a later update
        before being sent (``skipped``) or not played (stopped before).
    seq : int | None
        Sequence number returned by update_stimulation.
    """

    index: int
    t: float
    state: dict
    requested: float | None = None
    acked: float | None = None
    seq: int | None = None

    @property
    def error(self) -> float | None:
        """Achieved minus planned time in s (None if not acknowledged)."""
        return None if self.acked is None else self.acked - self.t


@dataclass
class PlaybackReport:
    """
    Planned versus achieved timing of a playback.
    """

    updates: list = field(default_factory=list)
    t0: float | None = None  # time.perf_counter() of the ack of the first update
    completed: bool = False
    error: BaseException | None = None

    @property
    def played(self) -> list:
        return [u for u in self.updates if u.acked is not None]

    @property
    def skipped(self) -> list:
        """Updates requested but superseded by a later one before the stimulation thread could send them."""
        return [u for u in self.updates if u.requested is not None and u.acked is None]

    def errors(self) -> list:
        """Timing errors (achieved - planned) in s of the acknowledged updates, the first one excluded (it is 0
        by definition)."""
        return [u.error for u in self.played if u.index > 0]

    def summary(self) -> dict:
        errors = self.errors()
        abs_errors = [abs(e) for e in errors]
        return {
            "n_planned": len(self.updates),
            "n_played": len(self.played),
            "n_skipped": len(self.skipped),
            "completed": self.completed,
            "mean_error_ms": 1000 * statistics.fmean(errors) if errors else None,
            "max_abs_error_ms": 1000 * max(abs_errors) if abs_errors else None,
            "p95_abs_error_ms": 1000 * _percentile(abs_errors, 95) if abs_errors else None,
        }

    def __str__(self) -> str:
        s = self.summary()
        fmt = lambda v: "n/a" if v is None else f"{v:.2f} ms"  # noqa: E731
        return (
            f"Playback {'completed' if s['completed'] else 'NOT completed'}: {s['n_played']}/{s['n_planned']} "
            f"updates acknowledged, {s['n_skipped']} skipped; timing error mean {fmt(s['mean_error_ms'])}, "
            f"p95 |err| {fmt(s['p95_abs_error_ms'])}, max |err| {fmt(s['max_abs_error_ms'])}"
        )


def _percentile(values: list, q: float) -> float:
    values = sorted(values)
    k = (len(values) - 1) * q / 100
    lo, hi = math.floor(k), math.ceil(k)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


class ProfilePlayer:
    """
    Play a StimulationProfile on a P24 with the non-blocking mid-level stimulation. See the module docstring for
    the timing limits.

    Example
    -------
    >>> profile = StimulationProfile.from_json("profile.json")
    >>> limits = StimulationLimits(max_amplitude=40, max_pulse_width=500, max_frequency=100)
    >>> with P24(port="COM4") as stimulator:
    ...     player = ProfilePlayer(stimulator, profile, channel_map={"BIClong": 1, "TRIlong": 2}, limits=limits)
    ...     report = player.play()
    ...     print(report)
    """

    def __init__(
        self,
        stimulator,
        profile: StimulationProfile,
        channel_map: dict,
        limits: StimulationLimits | None = None,
        mode: Modes = Modes.SINGLE,
        ramp: int = 0,
        merge_window: float = 1e-3,
        interval_tolerance: float = 1e-4,
        spin_time: float = 0.002,
        keep_alive_period: float = DEFAULT_KEEP_ALIVE_PERIOD_S,
        callback: Callable[[StimulationEvent], None] | None = None,
    ):
        """
        Parameters
        ----------
        stimulator : P24
            Connected stimulator. The mid level is initialized by play/start (init_stimulation) unless
            initialize=False is given to them.
        profile : StimulationProfile
            Profile to play. It is validated against the P24 limits and ``limits`` (ProfileValidationError).
            Use ``profile.clamped(limits)`` beforehand to clamp it explicitly.
        channel_map : dict
            {profile channel name: P24 channel number [1, 8]}. Every channel of the profile must be mapped (a
            profile channel is never silently ignored); several names can not share a channel.
        limits : StimulationLimits | None
            Safety limits for the participant, intersected with the P24 limits. None = P24 limits only.
        mode : Modes
            Pulse shape: Modes.SINGLE (one biphasic pulse per period, default), DOUBLET or TRIPLET.
        ramp : int
            P24 ramp (number of pulses to reach the amplitude, [0, 16]) applied at each update. Keep 0 to
            reproduce the optimized amplitudes.
        merge_window : float
            Segment boundaries of different channels closer than this (s) are sent as one update.
        interval_tolerance : float
            Inter-pulse intervals differing by less than this (s) are considered equal (same segment).
        spin_time : float
            The player sleeps until spin_time s before each deadline, then busy-waits (better than time.sleep
            resolution, costs CPU during spin_time).
        keep_alive_period : float
            Keep-alive period of the stimulation thread, see P24.start_stimulation.
        callback : callable | None
            Called with every StimulationEvent of the stimulation thread (after the player bookkeeping).
        """
        if getattr(stimulator, "device_type", None) != Device.P24.value:
            raise TypeError("ProfilePlayer requires a P24 stimulator (non-blocking mid-level stimulation).")
        if not isinstance(profile, StimulationProfile):
            raise TypeError("profile must be a StimulationProfile.")
        self.limits = P24_LIMITS if limits is None else P24_LIMITS.tighten(limits)
        profile.validate(self.limits)

        missing = [name for name in profile.names if name not in channel_map]
        if missing:
            raise ValueError(f"Profile channels {missing} are not in channel_map {channel_map}.")
        unknown = [name for name in channel_map if name not in profile.names]
        if unknown:
            raise ValueError(f"channel_map names {unknown} are not in the profile (channels: {profile.names}).")
        numbers = list(channel_map.values())
        if len(set(numbers)) != len(numbers):
            raise ValueError(f"Several profile channels are mapped on the same P24 channel: {channel_map}.")
        for number in numbers:
            if not isinstance(number, int) or not 1 <= number <= 8:
                raise ValueError(f"P24 channel numbers must be integers in [1, 8], got {number}.")
        if mode not in (Modes.SINGLE, Modes.DOUBLET, Modes.TRIPLET):
            raise ValueError("mode must be Modes.SINGLE, Modes.DOUBLET or Modes.TRIPLET.")
        if callback is not None and not callable(callback):
            raise TypeError("callback must be callable.")

        self.stimulator = stimulator
        self.profile = profile
        self.channel_map = dict(channel_map)
        self.mode = mode
        self.ramp = ramp
        self.spin_time = spin_time
        self.keep_alive_period = keep_alive_period
        self.user_callback = callback

        segments = profile.segments(self.limits, interval_tolerance=interval_tolerance)
        self.schedule = self._build_schedule(segments, profile.end_time, merge_window)
        #  Channel objects of every update, built in advance to keep the work at each deadline minimal
        self._channel_lists = [self._make_channels(u.state) for u in self.schedule]
        self.report = PlaybackReport(updates=self.schedule)

        self._lock = threading.Lock()
        self._seq_to_update = {}
        self._stop_event = threading.Event()
        self._thread = None
        self._first_ack = None

    #  Schedule
    def _build_schedule(self, segments: dict, end_time: float, merge_window: float) -> list:
        states = merge_segment_events(segments, end_time, merge_window)
        last = {}  # Frequency / pulse width kept on a channel while it is off (amplitude 0)
        schedule = []
        for index, (t, state) in enumerate(states):
            device_state = {}
            for name, seg in state.items():
                number = self.channel_map[name]
                if seg is None:
                    frequency, pulse_width = last.get(number, self._off_parameters(segments[name]))
                    device_state[number] = (frequency, pulse_width, 0.0)
                else:
                    last[number] = (seg.frequency, seg.pulse_width)
                    device_state[number] = (seg.frequency, seg.pulse_width, seg.amplitude)
            schedule.append(PlannedUpdate(index=index, t=t, state=dict(sorted(device_state.items()))))
        return schedule

    @staticmethod
    def _off_parameters(segments: list) -> tuple:
        #  Before the first pulse of a channel: its first frequency / pulse width (at zero amplitude), so that only
        #  the amplitude changes when it starts
        return (segments[0].frequency, segments[0].pulse_width) if segments else (1.0, 0.0)

    def _make_channels(self, state: dict) -> list:
        channels = []
        for number, (frequency, pulse_width, amplitude) in state.items():
            channels.append(
                Channel(
                    mode=self.mode,
                    no_channel=number,
                    amplitude=float(amplitude),
                    pulse_width=int(round(pulse_width)),
                    frequency=float(frequency),
                    ramp=self.ramp,
                    name=next(n for n, c in self.channel_map.items() if c == number),
                    device_type=Device.P24,
                )
            )
        return channels

    @property
    def channels(self) -> list:
        """Channel objects of the first update (used to initialize the mid level)."""
        return self._channel_lists[0]

    @property
    def planned_duration(self) -> float:
        return self.schedule[-1].t

    #  Playback
    def play(self, initialize: bool = True, timeout: float | None = None) -> PlaybackReport:
        """
        Play the profile and return when it is over (or on error / KeyboardInterrupt, after stopping the
        stimulation).

        Parameters
        ----------
        initialize : bool
            If True, call stimulator.init_stimulation with the channels of the profile first.
        timeout : float | None
            Maximum time to wait in s (default: planned duration + 5 s).
        """
        self.start(initialize=initialize)
        try:
            self.wait(timeout)
        except BaseException:
            self.stop()
            raise
        return self.report

    def start(self, initialize: bool = True):
        """
        Start the playback and return immediately (the profile is played by a background thread). Use wait()
        or stop() afterwards.
        """
        if self._thread is not None:
            raise RuntimeError("The profile has already been played: create a new ProfilePlayer.")
        stim = self.stimulator
        if initialize:
            stim.init_stimulation(list_channels=self.channels)
        stim.start_stimulation(
            upd_list_channels=self._channel_lists[0],
            blocking=False,
            callback=self._on_event,
            keep_alive_period=self.keep_alive_period,
            #  Watchdog: the device is paused even if this process stops scheduling updates
            stimulation_duration=self.planned_duration + 1.0,
        )
        with self._lock:
            first = self.schedule[0]
            if self._first_ack is None:  # The seq 1 event is normally received before start_stimulation returns
                self._first_ack = time.perf_counter()
            self.report.t0 = self._first_ack
            first.requested = first.acked = 0.0
            first.seq = 1
        self._thread = threading.Thread(target=self._run, name="P24ProfilePlayer", daemon=True)
        self._thread.start()

    def wait(self, timeout: float | None = None) -> PlaybackReport:
        """
        Wait for the end of the playback. Raises the error of the playback, if any.
        """
        if self._thread is None:
            raise RuntimeError("The playback has not been started.")
        if timeout is None:
            timeout = self.planned_duration + 5.0
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise TimeoutError(f"The playback did not end within {timeout} s.")
        if self.report.error is not None:
            raise self.report.error
        return self.report

    def stop(self):
        """
        Interrupt the playback: the stimulation is paused (zero amplitude) and the stimulation thread stopped.
        """
        self._stop_event.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(5.0)
        try:
            self.stimulator.stop_stimulation()
        except Exception:
            if self.report.error is None:
                raise

    @property
    def is_playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _on_event(self, event: StimulationEvent):
        if event.kind == "update":
            with self._lock:
                if event.seq == 1 and self._first_ack is None:
                    self._first_ack = event.t
                update = self._seq_to_update.get(event.seq)
                if update is not None and self._first_ack is not None:
                    update.acked = event.t - self._first_ack
        if self.user_callback is not None:
            self.user_callback(event)

    def _sleep_until(self, deadline: float) -> bool:
        """Sleep until the perf_counter deadline. Returns False if stop was requested."""
        while True:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return not self._stop_event.is_set()
            if remaining > self.spin_time:
                if self._stop_event.wait(remaining - self.spin_time):
                    return False
            elif self._stop_event.is_set():
                return False

    def _run(self):
        stim = self.stimulator
        t0 = self.report.t0
        try:
            for update, channels in zip(self.schedule[1:], self._channel_lists[1:]):
                if not self._sleep_until(t0 + update.t):
                    return
                with self._lock:
                    update.requested = time.perf_counter() - t0
                    seq = stim.update_stimulation(channels, wait=False)
                    update.seq = seq
                    self._seq_to_update[seq] = update
            #  Last state is all-zero: let the device ack it, then stop the stimulation thread
            last = self.schedule[-1]
            if last.seq is not None and last.index > 0:
                deadline = time.perf_counter() + 1.0
                while last.acked is None and time.perf_counter() < deadline and stim.is_stimulating:
                    time.sleep(0.001)
            stim.stop_stimulation()
            self.report.completed = True
        except BaseException as e:
            self.report.error = e
            try:
                stim.stop_stimulation()
            except BaseException:
                pass
