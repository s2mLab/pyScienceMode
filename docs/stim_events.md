# Stimulation event log and LSL markers

To analyse the effect of a stimulation on EMG, IMU or motion capture data, you need to know *when* each stimulation
command was sent and with which parameters. pyScienceMode can emit a timestamped `StimEvent` for every stimulation
command and dispatch it to one or several *sinks*.

## Events

| command    | device    | emitted by                                                        |
|------------|-----------|-------------------------------------------------------------------|
| `init`     | both      | `P24.init_stimulation`, `Rehastim2.init_channel`                  |
| `start`    | both      | `start_stimulation` (and `P24.update_stimulation`, which calls it) |
| `pulse`    | P24       | each update of `start_pulse_by_pulse_stimulation` (`pulse_index`) |
| `pause`    | both      | `pause_stimulation` (also called at the end of a timed stimulation) |
| `stop`     | both      | `end_stimulation`                                                 |
| `ll_start` | P24       | `start_stim_one_channel_stimulation` (low level)                  |
| `ll_stop`  | P24       | `end_stim_one_channel` (low level)                                |

Each event contains:

- `t_perf_ns`: `time.perf_counter_ns()` taken just **before** the command was sent (monotonic, ns);
- `t_wall_utc`: the corresponding UTC wall-clock time (ISO 8601);
- `device`, `command`, `event_id`;
- `channels`: for each channel, `channel`, `amplitude` (mA), `pulse_width` (μs), `frequency` (Hz), `mode`, `name`;
- `ack`: the decoded acknowledgement when known (Rehastim2), otherwise empty;
- `extra`: command specific values (`stimulation_duration`, `pulse_index`, `paused_channels`, ...).

The event is emitted once the command has been sent (and acknowledged), but is back-dated to the moment the command
was issued. A failing sink is logged and never interrupts the stimulation.

## Sinks

```python
from pysciencemode import P24
from pysciencemode.events import CsvEventLogger, LslMarkerOutlet, MemorySink

stimulator = P24("COM4", event_sinks=[CsvEventLogger("stim_events.csv"), LslMarkerOutlet()])
memory = stimulator.add_event_sink(MemorySink())  # sinks can also be added later
```

- `CsvEventLogger(path, mode="w")`: one row per channel, flushed after each event.
- `LslMarkerOutlet(name="pysciencemode")`: a `Markers` LSL stream (irregular rate, one JSON string per event).
  Requires `pylsl` (`pip install pylsl` or `pip install pysciencemode[lsl]`).
- `MemorySink()`: keeps the events in `memory.events`.
- Your own sink: subclass `EventSink` and implement `emit(event)` (it is called in the stimulation loop, keep it fast).

## Recording with LabRecorder alongside EMG / IMU

1. Start the LSL applications of your other devices (e.g. the Delsys/Noraxon/Xsens LSL apps, or a Vicon LSL bridge).
2. Start your Python script with an `LslMarkerOutlet`: the stream `pysciencemode` (type `Markers`) appears.
3. In [LabRecorder](https://github.com/labstreaminglayer/App-LabRecorder), click *Update*, select all the streams,
   then *Start*. Run the stimulation, then *Stop*.
4. Load the `.xdf` file (`pyxdf.load_xdf`): all the streams, including the stimulation markers, are expressed in
   the same time base after LabRecorder's clock-offset correction. Decode each marker with `json.loads`.

For systems not supported by LSL (e.g. Vicon Nexus with a hardware trigger), use the CSV log and a common physical
event (a sync pulse, or the first stimulation artefact visible on the EMG) to align the clocks.

## How the clocks relate

- `t_perf_ns` comes from `time.perf_counter_ns()`: monotonic, high resolution, but with an arbitrary origin specific
  to the computer. Use it for durations and ordering within the CSV log.
- `t_wall_utc` is `time.time_ns()` shifted to `t_perf_ns`. It allows a coarse alignment with other logs that use the
  wall clock, but can jump with NTP corrections.
- The LSL timestamp of a marker is `pylsl.local_clock()` (also monotonic, but with its own origin) minus the delay
  between `t_perf_ns` and the moment the marker is pushed. LabRecorder then maps each stream's `local_clock` to a common
  time base. Within one computer, `local_clock` and `perf_counter` both rely on the OS monotonic clock and advance at (practically) the same rate, so the offset between
  them is constant during a recording: the CSV and the LSL markers can be matched with `event_id`.

The timestamps give the time at which the command left Python, not the time of the pulse on the electrodes: the USB
latency and the stimulator scheduling (a few ms) are not included. For sub-millisecond alignment, rely on the
stimulation artefact recorded by the EMG amplifier.

A complete example is given in `examples/stim_events_lsl_example.py`.
