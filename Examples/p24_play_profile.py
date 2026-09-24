"""
Step 2 of the cocofest -> P24 workflow: play a StimulationProfile (exported by Examples/cocofest_export_profile.py,
or written by hand) on the P24. Run this in the stimulation environment (pyScienceMode + sciencemode library);
cocofest / bioptim are not needed here.

Safety: the profile is validated against the P24 limits AND the limits of the participant below; playback is
refused if a pulse violates them. Clamping is never implicit (see profile.clamped). Always check the electrode
placement and start with low amplitudes. The P24 stops by itself 2 s after the last command if this script dies.
"""

import sys

from pysciencemode import P24, ProfilePlayer, StimulationLimits, StimulationProfile, StimulationEvent

path = sys.argv[1] if len(sys.argv) > 1 else "cocofest_profile.json"
profile = StimulationProfile.from_json(path)
print(f"Profile {path}: {profile.names}, {profile.end_time:.3f} s, metadata {profile.metadata}")

#  Limits of the participant (not only of the device): adapt them to your protocol
limits = StimulationLimits(max_amplitude=40, max_pulse_width=600, max_frequency=100)
problems = profile.violations(limits)
if problems:
    print("\n".join(problems))
    # To play anyway with clamped values, uncomment (and review the changes):
    # profile, changes = profile.clamped(limits); print("\n".join(changes))
    raise SystemExit("The profile violates the limits.")

#  Profile muscle name -> P24 channel [1, 8]. Every muscle of the profile must be mapped.
channel_map = {name: number for number, name in enumerate(profile.names, start=1)}


def on_event(event: StimulationEvent):
    #  Called from the stimulation thread: keep it short
    if event.kind == "keep_alive" and any(event.channel_states):
        print("channel states:", event.channel_states)


with P24(port="COM4", show_log="Status") as stimulator:  # Enter the port on which the P24 is connected
    player = ProfilePlayer(stimulator, profile, channel_map, limits=limits, callback=on_event)
    print(f"{len(player.schedule)} mid-level updates planned over {player.planned_duration:.3f} s")
    try:
        report = player.play()  # initializes the mid level, plays, then pauses (zero amplitude)
    except KeyboardInterrupt:
        player.stop()
        raise
    stimulator.end_stimulation()

print(report)
for update in report.updates:
    achieved = "skipped" if update.acked is None else f"{1000 * update.acked:8.2f} ms"
    print(f"planned {1000 * update.t:8.2f} ms  achieved {achieved}  {update.state}")
