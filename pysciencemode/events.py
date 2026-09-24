"""
Timestamped stimulation events, used to synchronize the stimulation with other recordings (EMG, IMU, motion capture).

Each stimulation command sent by a device (init, start, pause, stop, pulse-by-pulse update...) can be turned into a
:class:`StimEvent` and dispatched to one or several :class:`EventSink`:

- :class:`CsvEventLogger` writes the events to a CSV file (one row per channel), flushed after each event;
- :class:`LslMarkerOutlet` streams the events as JSON markers on a Lab Streaming Layer outlet (requires ``pylsl``);
- :class:`MemorySink` keeps the events in a list (tests, online processing).

Example
-------
>>> from pysciencemode import P24
>>> from pysciencemode.events import CsvEventLogger, LslMarkerOutlet
>>> stimulator = P24("COM4", event_sinks=[CsvEventLogger("stim_events.csv"), LslMarkerOutlet()])
"""

from __future__ import annotations

import csv
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from itertools import count
from typing import Any, Iterable

logger = logging.getLogger(__name__)


@dataclass
class ChannelState:
    """
    Stimulation parameters of one channel at the time of the event.
    """

    channel: int
    amplitude: float | None = None
    pulse_width: float | None = None
    frequency: float | None = None
    mode: str | None = None
    name: str | None = None

    @classmethod
    def from_channel(cls, channel) -> "ChannelState":
        """
        Build a snapshot from a :class:`pysciencemode.Channel` (the values are copied, later changes of the channel
        are not reflected).
        """

        def _get(getter):
            try:
                return getattr(channel, getter)()
            except Exception:  # A snapshot must never break the stimulation
                return None

        mode = _get("get_mode")
        return cls(
            channel=_get("get_no_channel"),
            amplitude=_get("get_amplitude"),
            pulse_width=_get("get_pulse_width"),
            frequency=_get("get_frequency"),
            mode=_mode_name(mode),
            name=_get("get_name"),
        )


def _mode_name(mode) -> str | None:
    if mode is None:
        return None
    try:
        from .enums import Modes

        return Modes(mode).name
    except Exception:
        return str(mode)


_event_ids = count()


@dataclass
class StimEvent:
    """
    A timestamped stimulation event.

    Attributes
    ----------
    t_perf_ns : int
        Monotonic timestamp (``time.perf_counter_ns()``) taken just before the command was sent to the device.
        Use it to compute precise durations between events.
    t_wall_utc : str
        Wall-clock UTC time (ISO 8601) corresponding to ``t_perf_ns``. Useful to align with systems that only log
        absolute time, but subject to NTP adjustments.
    device : str
        Device type ("Rehastim2" or "P24").
    command : str
        Command name: "init", "start", "pause", "stop", "pulse", "ll_start", "ll_stop"...
    channels : list[ChannelState]
        Parameters of each channel involved in the command (may be empty, e.g. for "stop").
    ack : str | None
        Acknowledgement status returned by the device when known, None otherwise.
    extra : dict
        Additional command-specific information (e.g. ``pulse_index``, ``stimulation_duration``).
    event_id : int
        Sequential identifier, unique within the Python process.
    """

    t_perf_ns: int
    t_wall_utc: str
    device: str
    command: str
    channels: list[ChannelState] = field(default_factory=list)
    ack: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    event_id: int = field(default_factory=lambda: next(_event_ids))

    @classmethod
    def create(
        cls,
        device: str,
        command: str,
        channels: Iterable | None = None,
        t_perf_ns: int | None = None,
        ack: Any = None,
        **extra,
    ) -> "StimEvent":
        """
        Create an event. ``channels`` can contain :class:`pysciencemode.Channel` or :class:`ChannelState` objects.
        If ``t_perf_ns`` is given (captured earlier with ``time.perf_counter_ns()``), the wall-clock time is
        back-dated accordingly.
        """
        now_perf = time.perf_counter_ns()
        now_wall = time.time_ns()
        if t_perf_ns is None:
            t_perf_ns = now_perf
        wall_ns = now_wall - (now_perf - t_perf_ns)
        t_wall = datetime.fromtimestamp(wall_ns / 1e9, tz=timezone.utc).isoformat()
        states = [
            c if isinstance(c, ChannelState) else ChannelState.from_channel(c)
            for c in (channels or [])
        ]
        return cls(
            t_perf_ns=t_perf_ns,
            t_wall_utc=t_wall,
            device=str(device),
            command=command,
            channels=states,
            ack=None if ack is None else str(ack),
            extra=extra,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str, separators=(",", ":"))


class EventSink:
    """
    Base class of the event consumers. Subclasses must implement :meth:`emit`.
    ``emit`` is called synchronously in the stimulation loop: keep it fast.
    """

    def emit(self, event: StimEvent) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class MemorySink(EventSink):
    """
    Keep the events in memory (``self.events``).
    """

    def __init__(self):
        self.events: list[StimEvent] = []
        self._lock = threading.Lock()

    def emit(self, event: StimEvent) -> None:
        with self._lock:
            self.events.append(event)


class CsvEventLogger(EventSink):
    """
    Write the events to a CSV file, one row per channel (one row with empty channel fields for events without
    channel). The file is flushed after each event so that it remains usable if the program crashes.

    Parameters
    ----------
    path : str
        Path of the CSV file.
    mode : str
        "w" to overwrite (default) or "a" to append (the header is only written if the file is empty).
    """

    FIELDS = [
        "event_id",
        "t_perf_ns",
        "t_wall_utc",
        "device",
        "command",
        "channel",
        "amplitude",
        "pulse_width",
        "frequency",
        "mode",
        "name",
        "ack",
        "extra",
    ]

    def __init__(self, path, mode: str = "w"):
        if mode not in ("w", "a"):
            raise ValueError("mode must be 'w' or 'a'.")
        self.path = path
        self._lock = threading.Lock()
        self._file = open(path, mode, newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=self.FIELDS)
        if self._file.tell() == 0:
            self._writer.writeheader()
            self._file.flush()

    def emit(self, event: StimEvent) -> None:
        base = {
            "event_id": event.event_id,
            "t_perf_ns": event.t_perf_ns,
            "t_wall_utc": event.t_wall_utc,
            "device": event.device,
            "command": event.command,
            "ack": event.ack if event.ack is not None else "",
            "extra": (
                json.dumps(event.extra, default=str, separators=(",", ":"))
                if event.extra
                else ""
            ),
        }
        rows = []
        for ch in event.channels or [None]:
            row = dict(base)
            if ch is not None:
                row.update({k: ("" if v is None else v) for k, v in asdict(ch).items()})
            rows.append(row)
        with self._lock:
            if self._file.closed:
                return
            self._writer.writerows(rows)
            self._file.flush()

    def close(self) -> None:
        with self._lock:
            if not self._file.closed:
                self._file.close()


class LslMarkerOutlet(EventSink):
    """
    Stream the events as Lab Streaming Layer markers (one JSON string per event, irregular rate).

    The LSL timestamp of each marker is ``pylsl.local_clock()`` back-dated to the moment the command was sent
    (``t_perf_ns``), so that LabRecorder can align it with the other streams (EMG, IMU...).

    Parameters
    ----------
    name : str
        Name of the LSL stream.
    stream_type : str
        Type of the LSL stream ("Markers" is what LabRecorder and most tools expect).
    source_id : str
        Unique source identifier, allowing LabRecorder to recover the stream after a restart.
    """

    def __init__(
        self,
        name: str = "pysciencemode",
        stream_type: str = "Markers",
        source_id: str = "pysciencemode-stim-events",
    ):
        try:
            import pylsl
        except ImportError as e:  # pragma: no cover - depends on the environment
            raise ImportError(
                "LslMarkerOutlet requires pylsl. Install it with `pip install pylsl` "
                "or `pip install pysciencemode[lsl]`."
            ) from e
        self._pylsl = pylsl
        info = pylsl.StreamInfo(
            name, stream_type, 1, pylsl.IRREGULAR_RATE, pylsl.cf_string, source_id
        )
        info.desc().append_child_value("manufacturer", "pysciencemode")
        info.desc().append_child_value("format", "json")
        self._outlet = pylsl.StreamOutlet(info)
        self._lock = threading.Lock()

    def emit(self, event: StimEvent) -> None:
        delay_s = (time.perf_counter_ns() - event.t_perf_ns) / 1e9
        timestamp = self._pylsl.local_clock() - max(delay_s, 0.0)
        with self._lock:
            self._outlet.push_sample([event.to_json()], timestamp)

    def close(self) -> None:
        self._outlet = None


class EventEmitterMixin:
    """
    Give an object the ability to dispatch :class:`StimEvent` to a list of :class:`EventSink`.
    The sink list is created lazily, so no ``__init__`` call is needed.
    """

    @property
    def event_sinks(self) -> list:
        sinks = self.__dict__.get("_event_sinks")
        if sinks is None:
            sinks = self.__dict__["_event_sinks"] = []
        return sinks

    def add_event_sink(self, sink: EventSink) -> EventSink:
        """
        Register a sink which will receive every stimulation event. Returns the sink.
        """
        if not hasattr(sink, "emit"):
            raise TypeError("An event sink must implement an emit(event) method.")
        self.event_sinks.append(sink)
        return sink

    def remove_event_sink(self, sink: EventSink) -> None:
        self.event_sinks.remove(sink)

    def _emit(
        self,
        command: str,
        channels: Iterable | None = None,
        t_perf_ns: int | None = None,
        ack: Any = None,
        **extra,
    ) -> StimEvent | None:
        """
        Build a StimEvent and send it to all the registered sinks. A failing sink is logged, never raised,
        so that logging can not interrupt a stimulation.
        """
        sinks = self.__dict__.get("_event_sinks")
        if not sinks:
            return None
        event = StimEvent.create(
            getattr(self, "device_type", None),
            command,
            channels,
            t_perf_ns=t_perf_ns,
            ack=ack,
            **extra,
        )
        for sink in list(sinks):
            try:
                sink.emit(event)
            except Exception:
                logger.exception("Event sink %r failed on %s event", sink, command)
        return event
