"""
This example shows how to record a timestamped log of the stimulation commands, to synchronize the stimulation with
other recordings (EMG, IMU, motion capture...).

Each command sent to the stimulator (init, start, pause, stop, pulse-by-pulse update) produces a StimEvent which is:
- written to a CSV file (one row per channel, flushed after each event);
- streamed as a JSON marker on a Lab Streaming Layer (LSL) outlet named "pysciencemode", which can be recorded by
  LabRecorder together with the EMG / IMU streams (requires `pip install pylsl` or `pip install pysciencemode[lsl]`).

See docs/stim_events.md for how the clocks relate.
"""

import logging

from pysciencemode import Channel, Device, Modes
from pysciencemode import P24 as St
from pysciencemode.events import CsvEventLogger, LslMarkerOutlet

logging.basicConfig(level=logging.INFO)

sinks = [CsvEventLogger("stim_events.csv")]
try:
    sinks.append(LslMarkerOutlet(name="pysciencemode"))
except ImportError as e:
    logging.warning("LSL markers disabled: %s", e)

# Create the stimulator with the event sinks (sinks can also be added later with stimulator.add_event_sink(...))
stimulator = St(port="COM4", show_log="Status", event_sinks=sinks)

channel_1 = Channel(
    no_channel=1,
    name="Biceps",
    amplitude=20,
    pulse_width=350,
    frequency=30,
    mode=Modes.SINGLE,
    device_type=Device.P24,
)
list_channels = [channel_1]

stimulator.init_stimulation(list_channels=list_channels)  # -> "init" event

# 2 s of stimulation -> "start" event, then "pause" event at the end
stimulator.start_stimulation(upd_list_channels=list_channels, stimulation_duration=2)

# Pulse by pulse: one "pulse" event per update, carrying the parameters sent
stimulator.start_pulse_by_pulse_stimulation(
    upd_list_channels=list_channels,
    pulse_width_list={1: [200, 250, 300, 350, 400]},
    amplitude_list={1: [10, 12, 14, 16, 18]},
    pulse_interval_list=[40, 40, 40, 40, 40],
)

stimulator.end_stimulation()  # -> "stop" event
stimulator.close_port()

for sink in sinks:
    sink.close()
