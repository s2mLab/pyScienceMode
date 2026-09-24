"""
EMG-driven proportional closed-loop control of the P24.

Every 20 ms (50 Hz), the controller reads an EMG envelope in [0, 1] and sets the amplitude of channel 1 to
    amplitude = BASELINE + GAIN * envelope
The safety limits (ChannelLimits) clamp the amplitude to MAX_AMPLITUDE and its change to MAX_STEP mA per tick
(MAX_STEP * RATE_HZ = 100 mA/s here) before it is sent. Leaving the with block (or any error: electrode error,
sensor error, exception in the controller) stops the loop and immediately sets the amplitude to zero.

By default the EMG is simulated (FakeEmgSensor), so the controller logic can be tried with the P24 connected
but without EMG. Set USE_BIOSIGLIVE = True to read a processed EMG streamed by a biosiglive server
(https://github.com/pyomeca/biosiglive, see its examples/server.py): a TCP client asks the server for the
last frame of the "proc_device_data" command in a background thread (ThreadedSensor).

Set the amplitudes, gains and limits for your subject before using this example.
"""

import math
import time

from pysciencemode import (
    Channel,
    ChannelLimits,
    ClosedLoopController,
    Device,
    Modes,
    ThreadedSensor,
)
from pysciencemode import P24 as St

PORT = "COM4"  # Port on which the P24 is connected
RATE_HZ = 50  # Controller rate
BASELINE = 5  # mA
GAIN = 20  # mA per unit of normalized EMG
MAX_AMPLITUDE = 25  # mA, safety clamp
MAX_STEP = 2  # mA per tick
DURATION = 10  # s
USE_BIOSIGLIVE = False


class FakeEmgSensor:
    """Simulated normalized EMG envelope: a 0.2 Hz half sine wave between 0 and 1."""

    def __init__(self):
        self.t0 = time.perf_counter()

    def read(self):
        t = time.perf_counter() - self.t0
        return max(0.0, math.sin(2 * math.pi * 0.2 * t))


def make_sensor():
    if not USE_BIOSIGLIVE:
        return FakeEmgSensor()

    from pysciencemode import BiosigliveSensor

    emg = BiosigliveSensor.tcp_client(
        server_ip="127.0.0.1",
        port=50000,
        device_name="processed EMG",
        nb_channels=1,
        rate=2000,
        command_name="proc_device_data",
        nb_frame_to_get=1,
    )
    #  Normalize with the MVC of the subject (processed EMG in the same unit as the MVC)
    mvc = 0.3
    #  The TCP request blocks until the server answers: read it in its own thread so that the controller
    #  never waits for the network (the controller then always gets the latest value).
    return ThreadedSensor(lambda: float(emg.read()[0]) / mvc, period=0.01)

    #  Any other biosiglive interface can be used directly, e.g. a Delsys Trigno through pytrigno:
    #    from biosiglive import PytrignoClient, DeviceType, RealTimeProcessingMethod
    #    interface = PytrignoClient(ip="127.0.0.1")
    #    interface.add_device(nb_channels=1, device_type=DeviceType.Emg, name="emg", rate=2000,
    #                         processing_method=RealTimeProcessingMethod.ProcessEmg, moving_average=True)
    #    return ThreadedSensor(BiosigliveSensor(interface, "emg", process=True))


def controller(t, emg, channels):
    """
    t: time in s since the start; emg: output of the sensor; channels: parameters last sent (ChannelState).
    Returns the new amplitude of channel 1 (None would keep the previous one).
    """
    if emg is None:  # ThreadedSensor before its first read
        return None
    envelope = min(max(emg, 0.0), 1.0)
    return {1: BASELINE + GAIN * envelope}


channel_1 = Channel(
    mode=Modes.SINGLE,
    no_channel=1,
    amplitude=BASELINE,
    pulse_width=300,
    frequency=30,
    name="Biceps",
    device_type=Device.P24,
)
list_channels = [channel_1]

safety = ChannelLimits(
    max_amplitude=MAX_AMPLITUDE, max_amplitude_step=MAX_STEP, max_pulse_width=400
)

with St(port=PORT) as stimulator:  # show_log="Status" would print every update
    stimulator.init_stimulation(list_channels=list_channels)

    loop = ClosedLoopController(
        stimulator,
        controller,
        rate_hz=RATE_HZ,
        sensors=make_sensor(),
        safety=safety,
    )
    #  start() starts the non-blocking stimulation, then the controller thread
    with loop:
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < DURATION:
            loop.check()  # raises here if the loop stopped on an error
            print(f"amplitude = {loop.current_channels[0].amplitude:5.1f} mA", end="\r")
            time.sleep(0.2)
    #  Here the stimulation is paused (zero amplitude); the mid level is left by the outer with block

    stats = loop.stats
    print(
        f"\n{stats.n_ticks} ticks at {stats.mean_rate_hz:.1f} Hz, {stats.n_updates} updates, "
        f"{stats.n_overruns} overruns, latency mean {1000 * stats.mean_latency:.2f} ms "
        f"max {1000 * stats.max_latency:.2f} ms, compute max {1000 * stats.max_compute_time:.2f} ms"
    )
