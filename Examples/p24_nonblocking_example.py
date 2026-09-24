"""
Non-blocking mid-level stimulation with the P24.

start_stimulation(..., blocking=False) returns as soon as the stimulation is running. A background thread keeps
it alive (the P24 stops a mid-level stimulation after 2 s without command) and checks the electrode errors, while
the main thread stays free: here it changes the amplitude after 2 s, then stops the stimulation.
"""

import time

from pysciencemode import Channel, Device, Modes, StimulationEvent
from pysciencemode import P24 as St


def on_event(event: StimulationEvent):
    """
    Called from the stimulation thread after each acknowledged update / keep-alive. Keep it short.
    event.t is a time.perf_counter() timestamp.
    """
    if event.kind == "update":
        print(f"[{event.t:.3f}] update {event.seq} applied")


channel_1 = Channel(
    mode=Modes.SINGLE,
    no_channel=1,
    amplitude=10,
    pulse_width=300,
    frequency=30,
    name="Biceps",
    device_type=Device.P24,
)
list_channels = [channel_1]

#  The with statement stops the stimulation, leaves the mid level and closes the port, even on error
with St(port="COM4", show_log="Status") as stimulator:  # Enter the port on which the P24 is connected
    stimulator.init_stimulation(list_channels=list_channels)

    #  Returns immediately: the stimulation runs until stop_stimulation (or for stimulation_duration if given)
    stimulator.start_stimulation(
        upd_list_channels=list_channels,
        blocking=False,
        callback=on_event,
        keep_alive_period=0.5,  # Must stay below the 2 s timeout of the device
    )

    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 2:
        # Do something useful here (read sensors, update a GUI...). A stimulation error (e.g. electrode
        # error) stops the thread and is raised by the next call to the stimulator.
        time.sleep(0.1)

    #  Hot update: the new parameters are queued and applied by the stimulation thread
    channel_1.set_amplitude(20)
    stimulator.update_stimulation(list_channels, wait=True)

    time.sleep(2)

    #  Sends a last zero-amplitude update and joins the thread. The mid level stays initialized.
    stimulator.stop_stimulation()
    stimulator.end_stimulation()
