# Playing cocofest-optimized stimulations on the P24

[cocofest](https://github.com/pyomeca/cocofest) is the FES optimal control package of the S2M lab, built on
[bioptim](https://github.com/pyomeca/bioptim). It optimizes stimulation trains with FES muscle models (Ding2003,
Ding2007, Hmed2018, Marion, Veltink), for a single muscle or a musculoskeletal model. pyScienceMode can play the
result on a P24:

1. **Optimize** in cocofest (conda environment).
2. **Export** the solution as a `StimulationProfile` JSON file (`from_cocofest_solution(sol, ...).to_json(...)`).
3. **Play** the file on the P24 with `ProfilePlayer` (stimulation environment).

cocofest is not a dependency of pyScienceMode (it is not on PyPI; install it from source with conda, see its
README: `conda env create -f environment.yml`, then `pip install -e .`). To export in the cocofest environment,
also install pyScienceMode there (`pip install -e <pyScienceMode clone>`): the export does not need the stimulator
library. The bridge targets **cocofest 1.1.0** (commit `56ef741`, bioptim 3.4.0).

## 1-2. Optimize and export

See `Examples/cocofest_export_profile.py`:

```python
from pysciencemode import from_cocofest_solution, StimulationLimits

sol = ocp.solve()  # OCP built with a cocofest model and n_shooting = model.get_n_shooting(final_time)
profile = from_cocofest_solution(sol, amplitude=30)  # Ding2007: the amplitude is not optimized
profile.validate(StimulationLimits(max_amplitude=40, max_pulse_width=600, max_frequency=100))
profile.to_json("cocofest_profile.json")
```

What is read from the solution (cocofest 1.1.0):

| Model (cocofest class) | Pulse onsets | Pulse width | Amplitude |
|---|---|---|---|
| Ding2003 `DingModelFrequency`, Marion2009/2013 | `model.stim_time` | `pulse_width=` (user, us) | `amplitude=` (user, mA) |
| Ding2007 `DingModelPulseWidthFrequency`, Marion "modified" | `model.stim_time` | control `last_pulse_width[_<muscle>]` at the pulse node (s → us) | `amplitude=` (user, mA) |
| Hmed2018 `DingModelPulseIntensityFrequency` | `model.stim_time` | `pulse_width=` (user, us) | parameter `pulse_intensity[_<muscle>]` (mA, one per pulse) |
| Veltink | not supported (continuous current control `I`, no pulse) | | |

* cocofest does **not** optimize the pulse onsets: they are the `stim_time` given to the model. For a
  `FesMskModel`, each muscle model in `model.muscles_dynamics_model` gives one channel named after its
  `muscle_name`.
* `drop_pd0_pulses=True` removes the Ding2007 pulses left at the model threshold `pd0`. In the model they produce
  no force, and cocofest uses `pd0` as "off". A real muscle **is** stimulated by a pulse of about 131 us.
* Solutions saved to files: `from_cocofest_file("sol.pkl", stim_time=[...], amplitude=...)` reads the pickles of
  `cocofest.SolutionToPickle` (these do not contain the stim times) and the `.pkl`/`.npz` exports of the
  multibody examples (`save_sol_in_pkl`, which contain `"stim_time"`). Only open pickles you trust.
* Other tools: build the profile directly, or write the JSON below.

## The profile format

```json
{
  "format": "pysciencemode.stimulation_profile",
  "version": 1,
  "duration_s": 0.2,
  "metadata": {"source": "cocofest", "model": ["DingModelPulseWidthFrequency"], "optimized": ["pulse_width"]},
  "channels": [
    {"name": "BIClong", "pulse_times_s": [0.0, 0.02, 0.04], "pulse_widths_us": [250, 310, 420], "amplitudes_mA": [30, 30, 30]}
  ]
}
```

A channel can also be given as constant-frequency segments:
`{"name": "m", "segments": [{"start": 0, "duration": 1, "frequency": 30, "pulse_width": 300, "amplitude": 20}]}`.

## 3. Play on the P24

See `Examples/p24_play_profile.py`:

```python
from pysciencemode import P24, ProfilePlayer, StimulationLimits, StimulationProfile

profile = StimulationProfile.from_json("cocofest_profile.json")
limits = StimulationLimits(max_amplitude=40, max_pulse_width=600, max_frequency=100)
with P24(port="COM4") as stimulator:
    player = ProfilePlayer(stimulator, profile, channel_map={"BIClong": 1}, limits=limits)
    report = player.play()
print(report)  # planned vs achieved update times
```

`ProfilePlayer` groups the consecutive pulses of each muscle that share the same inter-pulse interval (IPI),
pulse width and amplitude into a segment. Each segment is played at `frequency = 1 / IPI` with the mid-level
stimulation. The segments of all the muscles are merged into a list of `Ml_update`s, which a background thread
sends at absolute deadlines through the non-blocking API (`start_stimulation(blocking=False)`,
`update_stimulation`, `stop_stimulation`). `player.start()` / `player.wait()` / `player.stop()` give a
non-blocking control.

### Timing accuracy

* **Updates are timed by the host, not by the stimulator.** The mid level has no notion of pulse time: the P24
  fires each channel periodically. The phase of the pulses relative to an update, and the delay from the command
  to the next pulse, are not documented. Expect up to one period of offset at each segment change.
* The achieved update times include OS jitter (~1-2 ms on Linux/macOS, up to ~15 ms on Windows), the serial
  round trip (a few ms), and sometimes an in-flight keep-alive. The keep-alive is sent at least every 1.5 s,
  because the P24 stops after 2 s without a command.
* Constant-frequency segments that last a few hundred ms or more are reproduced well. Profiles in which every IPI
  differs need one update per pulse, so they are only approximated: the pulse count at segment edges can be off
  by one. Updates planned closer than the device round trip can be superseded; they are reported as `skipped`.
* `PlaybackReport` gives the planned and acknowledged time of every update (`summary()`: mean / p95 / max error).
  It does not see the pulses themselves. Validate a protocol by measuring the stimulation artefact (EMG,
  oscilloscope).
* `start_pulse_by_pulse_stimulation` has the same limitation (host-timed `Ml_update`s, not synchronized with the
  device pulses) and blocks the caller.

### Safety

* The profile is always validated against the P24 limits and the `limits` of the participant. A violating profile
  is refused (`ProfileValidationError` lists every violation). Clamping is explicit only:
  `profile, changes = profile.clamped(limits)`.
* The optimized amplitudes and widths are only as good as the identified muscle model. Always start with lower
  amplitudes, check electrode placement, and keep the emergency stop within reach.
* The player sends a zero-amplitude update at the end, on `stop()`, on error, and on `KeyboardInterrupt` in
  `play()`. A watchdog (`stimulation_duration` = profile duration + 1 s) pauses the stimulation if updates stop
  being scheduled. If the process dies, the P24 stops by itself 2 s after the last command.
