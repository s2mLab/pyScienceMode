# Closed-loop control (P24)

`ClosedLoopController` calls a user function at a fixed rate to recompute the stimulation parameters from
sensor data (EMG, kinematics, forces...), applies safety limits, and sends the result to the P24 with the
non-blocking mid-level stimulation (`P24.start_stimulation(..., blocking=False)` / `update_stimulation`).

Full example: `Examples/closed_loop_emg_example.py` (EMG-proportional control, simulated EMG or biosiglive).

## Quick start

```python
import time
from pysciencemode import P24, Channel, ChannelLimits, ClosedLoopController, Device, Modes

channels = [Channel(mode=Modes.SINGLE, no_channel=1, amplitude=5, pulse_width=300, frequency=30,
                    device_type=Device.P24)]

def controller(t, emg, current_channels):
    # t: s since start, emg: output of the sensor, current_channels: tuple of ChannelState (last sent values)
    return {1: 5 + 20 * emg}          # new amplitude (mA) of channel 1

with P24(port="COM4") as stimulator:
    stimulator.init_stimulation(list_channels=channels)
    safety = ChannelLimits(max_amplitude=25, max_amplitude_step=2)   # mA, mA per tick
    with ClosedLoopController(stimulator, controller, rate_hz=50, sensors=my_emg_sensor, safety=safety) as loop:
        time.sleep(10)                 # the loop runs in its own thread
    print(loop.stats)
```

## The controller function

`controller_fn(t, sensor_data, current_channels)` is called from the controller thread at every tick. It
returns:

| Return value | Effect |
|---|---|
| `None` | Keep the previous targets. Nothing is sent, unless a rate-limited ramp toward the previous targets is still in progress. |
| `{1: 20.0}` | New amplitude (mA) of channel 1. Keys are channel numbers (1-8) or channel names. |
| `{1: {"amplitude": 20, "pulse_width": 250, "frequency": 40}}` | Any subset of amplitude (mA), pulse width (us), frequency (Hz). |
| `[Channel, ...]` | Targets read from the amplitude, pulse width and frequency of each Channel (matched by channel number). The objects are neither kept nor modified. |

Channels that are not mentioned keep their targets. Only the channels in SINGLE, DOUBLET or TRIPLET mode are
supported. An `update_stimulation` is queued only on ticks where a parameter actually changed.

## Timing

The loop uses absolute deadlines computed with `time.perf_counter()`: a late tick does not shift the next
ones (no drift), and ticks that are completely missed (slow controller or sensor) are skipped and counted as
overruns rather than run in a burst. `loop.stats` returns a `LoopStats` with `n_ticks`, `n_updates`,
`n_overruns`, `mean_rate_hz`, the scheduling latency (mean/max delay between a deadline and the actual start
of the tick) and the compute time (sensor read + controller + update).

The P24 stimulation thread coalesces the updates it has not sent yet (the latest wins), so a controller rate
much higher than the stimulation frequency (or than the serial link can follow) brings nothing. 20-100 Hz is
a reasonable range. Python threads are not real-time: expect jitters of about 1 ms, occasionally more.

## Safety

`safety` is a `ChannelLimits` applied to all channels, or a dict `{channel number: ChannelLimits}` (the key
`None` gives the default for the other channels). The limits are applied to **every** set of parameters before
it is sent, including the initial one sent by `start()`:

- `max_amplitude` (mA), `max_pulse_width` (us): hard clamps (the device limits always apply too).
- `max_amplitude_step` (mA), `max_pulse_width_step` (us): largest change per tick relative to the last value
  sent, i.e. a maximal slope of `max_amplitude_step * rate_hz` mA/s. A larger request becomes a ramp.
- `min_frequency`, `max_frequency` (Hz).

`None` (the default of each field) means no limit beyond the device limit, and no rate limit. **Set them for
each subject.**

Stopping is not rate limited: `stop()`, the end of the `with` block, and any error in the controller, a sensor
or the stimulator (e.g. an electrode error detected by the P24 keep-alive) stop the loop and immediately send
a zero-amplitude update (`stimulator.stop_stimulation()`). The error is then re-raised in your thread by
`stop()`, `check()`, `join()`, `is_running` or the end of the `with` block. These limits protect against
controller mistakes; they do not replace the emergency stop of the device.

## Sensors

`sensors` can be:

- `None`: `sensor_data` is `None`;
- any object with a `read()` method (`SensorSource` protocol) or a function without argument;
- a dict `{name: source}`: `sensor_data` is `{name: source.read()}`.

`read()` runs in the controller thread, before the controller. If it is slow or blocking, wrap the source in
`ThreadedSensor(source)`: it is read continuously in its own thread and `read()` returns the latest value
immediately (`None` before the first one). ThreadedSensors given to the controller are started and stopped
with it.

### biosiglive

[biosiglive](https://github.com/pyomeca/biosiglive) is an optional dependency. `BiosigliveSensor` reads one
device of any biosiglive interface (`TcpClient`, `PytrignoClient`, `ViconClient`, `TrignoSDKClient`...): each
`read()` calls `interface.get_device_data(device_name=...)`, optionally the real-time processing configured on
the device (`process=True`, e.g. `RealTimeProcessingMethod.ProcessEmg`), and returns the last frame
(`numpy` array of shape `(n_channels,)`, or all the new frames with `last_frame=False`).

```python
from pysciencemode import BiosigliveSensor, ThreadedSensor

# Processed EMG streamed by a biosiglive Server (see biosiglive/examples/server.py)
emg = BiosigliveSensor.tcp_client("127.0.0.1", 50000, device_name="processed EMG", nb_channels=2, rate=2000,
                                  command_name="proc_device_data")
sensors = ThreadedSensor(emg)            # the TCP request blocks: read it in its own thread

# Or directly from a Delsys Trigno through pytrigno, with biosiglive's EMG processing
from biosiglive import PytrignoClient, DeviceType, RealTimeProcessingMethod
interface = PytrignoClient(ip="127.0.0.1")
interface.add_device(nb_channels=2, device_type=DeviceType.Emg, name="emg", rate=2000,
                     processing_method=RealTimeProcessingMethod.ProcessEmg, moving_average=True)
sensors = ThreadedSensor(BiosigliveSensor(interface, "emg", process=True))
```

`BiosigliveSensor` only uses the interface through `get_device_data` / `get_device(name).process()`, so it
does not import biosiglive; `BiosigliveSensor.tcp_client` does, and raises an explicit `ImportError` if it is
not installed.
