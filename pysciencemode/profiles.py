"""
Device-agnostic stimulation profiles, e.g. optimized offline with an FES muscle model (cocofest / bioptim), and
their conversion into frequency segments that a mid-level stimulator can play.

A ``StimulationProfile`` holds, for each stimulated muscle, a pulse train: the onset time of every pulse, and the
pulse width and amplitude of every pulse. Units are explicit in the JSON keys: seconds for times, microseconds
for pulse widths, milliamperes for amplitudes.

The mid-level mode of the P24 does not accept pulse times: it stimulates each channel periodically, and only the
period, pulse width and amplitude can be changed with an ``Ml_update``. ``ChannelProfile.to_segments`` therefore
groups consecutive pulses with the same inter-pulse interval (IPI), pulse width and amplitude into a
``Segment`` stimulated at ``frequency = 1 / IPI``. A profile with a constant frequency gives one segment, a
profile whose every IPI differs (e.g. optimized stimulation times) gives one segment per pulse, i.e. one update
per pulse. See ``pysciencemode.profile_player`` for the playback and its timing limits.

This module does not depend on the hardware library, nor on bioptim or cocofest: the loaders
(``pysciencemode.bioptim_bridge``) import them lazily.
"""

from dataclasses import dataclass, field, replace
import json
import math
from typing import Iterable, Sequence

FORMAT_NAME = "pysciencemode.stimulation_profile"
FORMAT_VERSION = 1


@dataclass(frozen=True)
class StimulationLimits:
    """
    Limits a profile must respect before being played. The defaults are the limits of the P24 mid level
    (Channel.check_value_param: amplitude [0, 130] mA, pulse width [0, 4095] us, period [0.5, 16383] ms).

    They are device limits, not physiological ones: for a participant, build tighter limits, e.g.
    ``StimulationLimits(max_amplitude=40, max_pulse_width=500, max_frequency=100)``.

    Attributes
    ----------
    max_amplitude : float
        Maximum pulse amplitude in mA.
    max_pulse_width : float
        Maximum pulse width (duration of one phase of the biphasic pulse) in us.
    min_pulse_width : float
        Minimum pulse width in us.
    max_frequency : float
        Maximum stimulation frequency in Hz, i.e. minimum inter-pulse interval 1 / max_frequency.
    min_frequency : float
        Minimum frequency of a mid-level segment in Hz (longest P24 period is 16383 ms). Longer inter-pulse
        intervals are played as a pulse followed by a zero-amplitude segment.
    max_charge : float | None
        Optional maximum charge per phase in nC (amplitude in mA x pulse width in us).
    """

    max_amplitude: float = 130.0
    max_pulse_width: float = 4095.0
    min_pulse_width: float = 0.0
    max_frequency: float = 2000.0
    min_frequency: float = 1000.0 / 16383.0
    max_charge: float | None = None

    def __post_init__(self):
        if self.max_amplitude < 0 or self.max_pulse_width < self.min_pulse_width or self.min_pulse_width < 0:
            raise ValueError("Invalid limits: check the amplitude and pulse width bounds.")
        if not 0 < self.min_frequency <= self.max_frequency:
            raise ValueError("Invalid limits: 0 < min_frequency <= max_frequency is required.")

    def tighten(self, other: "StimulationLimits") -> "StimulationLimits":
        """
        Return the intersection of these limits and ``other`` (the most restrictive bound of each).
        """
        charges = [c for c in (self.max_charge, other.max_charge) if c is not None]
        return StimulationLimits(
            max_amplitude=min(self.max_amplitude, other.max_amplitude),
            max_pulse_width=min(self.max_pulse_width, other.max_pulse_width),
            min_pulse_width=max(self.min_pulse_width, other.min_pulse_width),
            max_frequency=min(self.max_frequency, other.max_frequency),
            min_frequency=max(self.min_frequency, other.min_frequency),
            max_charge=min(charges) if charges else None,
        )


#  Limits of the P24 mid-level stimulation.
P24_LIMITS = StimulationLimits()


class ProfileValidationError(ValueError):
    """
    Raised when a profile violates limits. ``violations`` lists one message per problem.
    """

    def __init__(self, violations: list):
        self.violations = list(violations)
        shown = "\n  - ".join(self.violations[:20])
        more = f"\n  ... and {len(self.violations) - 20} more" if len(self.violations) > 20 else ""
        super().__init__(f"The stimulation profile violates the limits:\n  - {shown}{more}")


@dataclass(frozen=True)
class Segment:
    """
    Constant mid-level stimulation of one channel from ``start`` (included) to ``end`` (excluded), in s.
    The pulses are expected at start, start + 1 / frequency, ... (``n_pulses`` pulses).
    """

    start: float
    end: float
    frequency: float
    pulse_width: float
    amplitude: float
    n_pulses: int


def _as_list(values, n: int, name: str, channel: str) -> list:
    if isinstance(values, (int, float)):
        return [float(values)] * n
    values = [float(v) for v in values]
    if len(values) == 1 and n != 1:
        return values * n
    if len(values) != n:
        raise ValueError(
            f"Channel '{channel}': {name} has {len(values)} values for {n} pulses "
            f"(give one value per pulse or a single value)."
        )
    return values


@dataclass
class ChannelProfile:
    """
    Pulse train of one muscle / channel.

    Attributes
    ----------
    name : str
        Muscle (or channel) name, used as the key of the channel map of the player.
    pulse_times : list[float]
        Onset time of every pulse in s, strictly increasing, relative to the start of the profile.
    pulse_widths : list[float]
        Pulse width of every pulse in us (a single value is broadcast to all the pulses).
    amplitudes : list[float]
        Amplitude of every pulse in mA (a single value is broadcast to all the pulses).
    last_interval : float | None
        Interval in s allotted to the last pulse, i.e. when the channel is switched off after it. Defaults to the
        previous inter-pulse interval (or 0.05 s for a single pulse), capped by the end of the profile.
    """

    name: str
    pulse_times: list
    pulse_widths: list
    amplitudes: list
    last_interval: float | None = None

    def __post_init__(self):
        self.name = str(self.name)
        self.pulse_times = [float(t) for t in self.pulse_times]
        n = len(self.pulse_times)
        self.pulse_widths = _as_list(self.pulse_widths, n, "pulse_widths", self.name)
        self.amplitudes = _as_list(self.amplitudes, n, "amplitudes", self.name)
        for a, b in zip(self.pulse_times, self.pulse_times[1:]):
            if not b > a:
                raise ValueError(f"Channel '{self.name}': pulse times must be strictly increasing ({a} then {b}).")
        if any(not math.isfinite(v) for v in self.pulse_times + self.pulse_widths + self.amplitudes):
            raise ValueError(f"Channel '{self.name}': non finite value in the pulse train.")
        if self.last_interval is not None and self.last_interval <= 0:
            raise ValueError(f"Channel '{self.name}': last_interval must be positive.")

    @classmethod
    def from_segments(cls, name: str, segments: Iterable[dict], last_interval: float | None = None):
        """
        Build a pulse train from constant-frequency segments, each a dict with the keys "start" (s),
        "duration" (s), "frequency" (Hz), "pulse_width" (us) and "amplitude" (mA). Pulses are generated at
        start, start + 1 / frequency, ... strictly before start + duration.
        """
        times, widths, amps = [], [], []
        for seg in segments:
            start, duration, frequency = float(seg["start"]), float(seg["duration"]), float(seg["frequency"])
            if frequency <= 0 or duration <= 0:
                raise ValueError(f"Channel '{name}': segments need a positive frequency and duration.")
            n = int(math.ceil(duration * frequency - 1e-9))
            for k in range(n):
                times.append(start + k / frequency)
                widths.append(float(seg["pulse_width"]))
                amps.append(float(seg["amplitude"]))
        order = sorted(range(len(times)), key=times.__getitem__)
        return cls(
            name,
            [times[i] for i in order],
            [widths[i] for i in order],
            [amps[i] for i in order],
            last_interval=last_interval,
        )

    @property
    def n_pulses(self) -> int:
        return len(self.pulse_times)

    def intervals(self) -> list:
        """Inter-pulse intervals in s."""
        return [b - a for a, b in zip(self.pulse_times, self.pulse_times[1:])]

    def _last_interval(self, end_time: float | None) -> float:
        if self.last_interval is not None:
            interval = self.last_interval
        elif self.n_pulses > 1:
            interval = self.pulse_times[-1] - self.pulse_times[-2]
        else:
            interval = 0.05
        if end_time is not None and end_time > self.pulse_times[-1]:
            interval = min(interval, end_time - self.pulse_times[-1])
        return interval

    def to_segments(
        self,
        end_time: float | None = None,
        interval_tolerance: float = 1e-4,
        value_tolerance: float = 1e-6,
        max_interval: float | None = None,
    ) -> list:
        """
        Group consecutive pulses sharing the same inter-pulse interval (within ``interval_tolerance`` s), pulse
        width and amplitude (within ``value_tolerance``) into constant-frequency segments.

        Parameters
        ----------
        end_time : float | None
            End of the profile, caps the interval given to the last pulse.
        interval_tolerance : float
            Absolute tolerance in s on the inter-pulse intervals of one segment.
        value_tolerance : float
            Absolute tolerance on the pulse widths (us) and amplitudes (mA) of one segment.
        max_interval : float | None
            Longest inter-pulse interval that can be played as a frequency (1 / min_frequency). A longer interval is
            played as a one-pulse segment of duration max_interval followed by a gap (zero amplitude).

        Returns
        -------
        list[Segment], sorted and non overlapping. Gaps between segments are periods without stimulation.
        """
        n = self.n_pulses
        if n == 0:
            return []
        t = self.pulse_times
        ipis = self.intervals() + [self._last_interval(end_time)]
        if max_interval is not None:
            ipis = [min(ipi, max_interval) for ipi in ipis]
        segments = []
        i = 0
        while i < n:
            j = i
            while (
                j + 1 < n
                and abs(ipis[j + 1] - ipis[i]) <= interval_tolerance
                and abs(t[j + 1] - t[j] - ipis[i]) <= interval_tolerance  # contiguous (no capped gap)
                and abs(self.pulse_widths[j + 1] - self.pulse_widths[i]) <= value_tolerance
                and abs(self.amplitudes[j + 1] - self.amplitudes[i]) <= value_tolerance
            ):
                j += 1
            #  Mean interval of the group: more accurate than the first one when the IPIs are slightly jittered
            if j > i:
                ipi = (t[j] - t[i]) / (j - i)
            else:
                ipi = ipis[i]
            segments.append(
                Segment(
                    start=t[i],
                    end=t[j] + ipi,
                    frequency=1.0 / ipi,
                    pulse_width=self.pulse_widths[i],
                    amplitude=self.amplitudes[i],
                    n_pulses=j - i + 1,
                )
            )
            i = j + 1
        return segments

    def to_dict(self) -> dict:
        data = {
            "name": self.name,
            "pulse_times_s": list(self.pulse_times),
            "pulse_widths_us": list(self.pulse_widths),
            "amplitudes_mA": list(self.amplitudes),
        }
        if self.last_interval is not None:
            data["last_interval_s"] = self.last_interval
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ChannelProfile":
        if "pulse_times_s" not in data and "segments" in data:
            return cls.from_segments(data["name"], data["segments"], data.get("last_interval_s"))
        return cls(
            name=data["name"],
            pulse_times=data["pulse_times_s"],
            pulse_widths=data["pulse_widths_us"],
            amplitudes=data["amplitudes_mA"],
            last_interval=data.get("last_interval_s"),
        )


@dataclass
class StimulationProfile:
    """
    Stimulation profile of several muscles, independent of the stimulator.

    Attributes
    ----------
    channels : list[ChannelProfile]
        One pulse train per muscle (unique names).
    duration : float | None
        Duration of the profile in s (e.g. the final time of the optimal control problem). If None, the profile
        ends after the last pulse of all the channels.
    metadata : dict
        Free JSON-serializable information, e.g. {"model": "DingModelPulseWidthFrequency", "source": "cocofest",
        "cocofest_version": "..."}.
    """

    channels: list
    duration: float | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        self.channels = list(self.channels)
        names = [c.name for c in self.channels]
        if len(set(names)) != len(names):
            raise ValueError(f"Channel names must be unique, got {names}.")
        if self.duration is not None:
            self.duration = float(self.duration)
            if self.duration <= 0:
                raise ValueError("duration must be positive.")
            for c in self.channels:
                if c.pulse_times and c.pulse_times[-1] >= self.duration:
                    raise ValueError(
                        f"Channel '{c.name}': pulse at {c.pulse_times[-1]} s after the end of the profile "
                        f"({self.duration} s)."
                    )
        for c in self.channels:
            if c.pulse_times and c.pulse_times[0] < 0:
                raise ValueError(f"Channel '{c.name}': negative pulse time {c.pulse_times[0]} s.")

    #  Access
    @property
    def names(self) -> list:
        return [c.name for c in self.channels]

    def __getitem__(self, name: str) -> ChannelProfile:
        for c in self.channels:
            if c.name == name:
                return c
        raise KeyError(f"No channel '{name}' in the profile (channels: {self.names}).")

    @property
    def end_time(self) -> float:
        """End of the profile in s: duration if given, otherwise end of the last segment of all channels."""
        if self.duration is not None:
            return self.duration
        ends = [c.pulse_times[-1] + c._last_interval(None) for c in self.channels if c.n_pulses]
        return max(ends, default=0.0)

    def segments(self, limits: StimulationLimits | None = None, **kwargs) -> dict:
        """
        Segments of every channel, {name: [Segment, ...]}. See ChannelProfile.to_segments for kwargs.
        """
        if limits is not None:
            kwargs.setdefault("max_interval", 1.0 / limits.min_frequency)
        return {c.name: c.to_segments(end_time=self.duration, **kwargs) for c in self.channels}

    #  Validation
    def violations(self, limits: StimulationLimits = P24_LIMITS) -> list:
        """
        List (as messages) the pulses violating the limits. Empty if the profile is valid.
        """
        messages = []
        min_ipi = 1.0 / limits.max_frequency
        for c in self.channels:
            for k, (t, pw, amp) in enumerate(zip(c.pulse_times, c.pulse_widths, c.amplitudes)):
                where = f"channel '{c.name}', pulse {k} (t = {t:.4f} s)"
                if amp < 0 or amp > limits.max_amplitude:
                    messages.append(f"{where}: amplitude {amp:g} mA outside [0, {limits.max_amplitude:g}] mA")
                if pw < limits.min_pulse_width or pw > limits.max_pulse_width:
                    messages.append(
                        f"{where}: pulse width {pw:g} us outside "
                        f"[{limits.min_pulse_width:g}, {limits.max_pulse_width:g}] us"
                    )
                if limits.max_charge is not None and amp * pw > limits.max_charge:
                    messages.append(f"{where}: charge {amp * pw:g} nC above {limits.max_charge:g} nC")
            for k, ipi in enumerate(c.intervals()):
                if ipi < min_ipi * (1 - 1e-9):
                    messages.append(
                        f"channel '{c.name}', pulses {k}-{k + 1}: interval {ipi * 1000:.3f} ms, i.e. "
                        f"{1 / ipi:.1f} Hz above {limits.max_frequency:g} Hz"
                    )
        return messages

    def validate(self, limits: StimulationLimits = P24_LIMITS) -> "StimulationProfile":
        """
        Raise ProfileValidationError if the profile violates the limits. Returns self to allow chaining.
        """
        messages = self.violations(limits)
        if messages:
            raise ProfileValidationError(messages)
        return self

    def clamped(self, limits: StimulationLimits) -> tuple:
        """
        Return a copy of the profile whose amplitudes and pulse widths are clamped to the limits (the charge is
        limited by reducing the amplitude) and whose pulses closer than 1 / max_frequency to the previous kept
        pulse are dropped, with the list of the changes made.

        Returns
        -------
        (StimulationProfile, list[str])
        """
        changes = []
        min_ipi = 1.0 / limits.max_frequency
        new_channels = []
        for c in self.channels:
            times, widths, amps = [], [], []
            for k, (t, pw, amp) in enumerate(zip(c.pulse_times, c.pulse_widths, c.amplitudes)):
                if times and t - times[-1] < min_ipi * (1 - 1e-9):
                    changes.append(f"channel '{c.name}', pulse {k} (t = {t:.4f} s) dropped (frequency limit)")
                    continue
                new_pw = min(max(pw, limits.min_pulse_width), limits.max_pulse_width)
                new_amp = min(max(amp, 0.0), limits.max_amplitude)
                if limits.max_charge is not None and new_pw > 0 and new_amp * new_pw > limits.max_charge:
                    new_amp = limits.max_charge / new_pw
                if new_pw != pw:
                    changes.append(f"channel '{c.name}', pulse {k}: pulse width {pw:g} -> {new_pw:g} us")
                if new_amp != amp:
                    changes.append(f"channel '{c.name}', pulse {k}: amplitude {amp:g} -> {new_amp:g} mA")
                times.append(t)
                widths.append(new_pw)
                amps.append(new_amp)
            new_channels.append(ChannelProfile(c.name, times, widths, amps, last_interval=c.last_interval))
        metadata = dict(self.metadata)
        if changes:
            metadata["clamped"] = True
        return replace(self, channels=new_channels, metadata=metadata), changes

    #  Serialization
    def to_dict(self) -> dict:
        return {
            "format": FORMAT_NAME,
            "version": FORMAT_VERSION,
            "duration_s": self.duration,
            "metadata": self.metadata,
            "channels": [c.to_dict() for c in self.channels],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StimulationProfile":
        if data.get("format", FORMAT_NAME) != FORMAT_NAME:
            raise ValueError(f"Unknown profile format '{data.get('format')}'.")
        if int(data.get("version", FORMAT_VERSION)) > FORMAT_VERSION:
            raise ValueError(
                f"Profile format version {data['version']} is newer than the supported one ({FORMAT_VERSION})."
            )
        return cls(
            channels=[ChannelProfile.from_dict(c) for c in data["channels"]],
            duration=data.get("duration_s"),
            metadata=dict(data.get("metadata") or {}),
        )

    def to_json(self, path: str | None = None, indent: int | None = 2) -> str:
        """
        Serialize the profile to JSON. If path is given, the JSON is also written to that file.
        """
        text = json.dumps(self.to_dict(), indent=indent, default=_json_default)
        if path is not None:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        return text

    @classmethod
    def from_json(cls, text_or_path: str) -> "StimulationProfile":
        """
        Load a profile from a JSON string or from the path of a JSON file.
        """
        text = text_or_path
        if not text_or_path.lstrip().startswith("{"):
            with open(text_or_path, "r", encoding="utf-8") as f:
                text = f.read()
        return cls.from_dict(json.loads(text))

    #  Construction helpers
    @classmethod
    def constant(
        cls,
        channels: dict,
        frequency: float,
        duration: float,
        pulse_width: float,
        amplitude: float,
        metadata: dict | None = None,
    ) -> "StimulationProfile":
        """
        Profile with the same constant-frequency pulse train on every named channel.

        Parameters
        ----------
        channels : dict | Sequence[str]
            Channel names (a dict name -> anything is accepted, only its keys are used).
        """
        return cls(
            [
                ChannelProfile.from_segments(
                    name,
                    [dict(start=0.0, duration=duration, frequency=frequency, pulse_width=pulse_width,
                          amplitude=amplitude)],
                )
                for name in channels
            ],
            duration=duration,
            metadata=metadata or {},
        )


def _json_default(obj):
    """Serialize numpy scalars / arrays found in metadata."""
    if hasattr(obj, "tolist"):
        return obj.tolist()
    if hasattr(obj, "item"):
        return obj.item()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def merge_segment_events(segments: dict, end_time: float, merge_window: float = 1e-3) -> list:
    """
    Merge the segments of all the channels into a list of global states.

    Parameters
    ----------
    segments : dict
        {name: [Segment, ...]}, as returned by StimulationProfile.segments.
    end_time : float
        End of the profile in s: every channel is off from then on.
    merge_window : float
        Boundaries of different channels closer than this (s) are merged into a single update, at the earliest
        of them.

    Returns
    -------
    list of (time, {name: Segment | None}), sorted by time, starting at 0 and ending with an all-off state at
    end_time (kept even if the channels are already off, so that the playback lasts the whole profile). None means
    the channel is off (zero amplitude). Consecutive identical states are removed.
    """
    boundaries = {0.0, float(end_time)}
    for segs in segments.values():
        for s in segs:
            boundaries.add(s.start)
            if s.end < end_time:
                boundaries.add(s.end)
    times = sorted(t for t in boundaries if t <= end_time)
    merged = []
    for t in times:
        if merged and t - merged[-1] < merge_window and t != end_time:
            continue
        merged.append(t)
    if merged[-1] != end_time:
        if end_time - merged[-1] < merge_window:
            merged[-1] = end_time
        else:
            merged.append(end_time)

    def active(segs: Sequence, t: float, t_next: float):
        #  Segment containing the middle of [t, t_next): robust to the boundaries moved by the merge window
        mid = 0.5 * (t + t_next)
        for s in segs:
            if s.start <= mid < s.end:
                return s
        for s in segs:  # Segment shorter than the merge window, starting just after t
            if t - 1e-12 <= s.start < t + merge_window:
                return s
        return None

    states = []
    for k, t in enumerate(merged):
        if t >= end_time:
            state = {name: None for name in segments}
        else:
            t_next = merged[k + 1]
            state = {name: active(segs, t, t_next) for name, segs in segments.items()}
        if states and states[-1][1] == state and t < end_time:
            continue
        states.append((t, state))
    return states
