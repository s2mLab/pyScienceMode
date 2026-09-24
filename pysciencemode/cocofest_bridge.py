"""
Bridge between cocofest (FES optimal control on top of bioptim, https://github.com/pyomeca/cocofest) and
pyScienceMode: convert an optimized cocofest solution into a ``StimulationProfile`` that ``ProfilePlayer`` plays
on a P24.

cocofest is NOT a dependency of pyScienceMode: nothing here imports it (nor bioptim) at module level. The
conversion only reads plain attributes / arrays of the solution, so ``from_cocofest_solution`` runs in the
cocofest environment and the resulting JSON file is played in the stimulation environment.

Targeted version: cocofest 1.1.0 (main branch, commit 56ef741, 2026-08-20), bioptim 3.4.0.

Where cocofest stores the stimulation (cocofest 1.1.0)
------------------------------------------------------
* Pulse onsets are NOT optimized by cocofest: they are fixed on the model before the OCP is built,
  ``ModelMaker.create_model(..., stim_time=[...])`` or ``FesMskModel(..., stim_time=[...])``, and read back from
  ``sol.ocp.nlp[0].model.stim_time`` (single muscle) or ``sol.ocp.nlp[0].model.muscles_dynamics_model[i].stim_time``
  (musculoskeletal model, one list per muscle, identical for all muscles in cocofest 1.1.0), in s.
  ``previous_stim`` pulses (before t = 0) are not part of the profile.
* Pulse width (Ding2007 ``DingModelPulseWidthFrequency``, Marion "modified" models): bioptim *control*
  ``"last_pulse_width"`` (single muscle model, even with a muscle_name) or ``"last_pulse_width_<muscle>"``
  (``FesMskModel``), in s, one row,
  constant on each shooting interval. The width of the pulse at ``stim_time[j]`` is the control of the node at
  that time (the shooting grid is built by ``model.get_n_shooting`` so that every pulse falls on a node).
* Pulse intensity (Hmed2018 ``DingModelPulseIntensityFrequency``): bioptim *parameter* ``"pulse_intensity"`` or
  ``"pulse_intensity_<muscle>"``, in mA, one value per pulse. If the parameter is absent, the last row of the
  sliding-window control of the same name at the pulse node is used (it is constrained equal to the parameter of
  the latest pulse by ``CustomConstraint.pulse_intensity_sliding_window_constraint``).
* Ding2003 / Marion models (frequency only) optimize neither: the stim times are the whole profile and the pulse
  width and amplitude must be given by the user. Veltink models use a continuous current control ``"I"``
  without pulse times: they are not supported.

Units of the profile: pulse widths in us (cocofest seconds x 1e6), amplitudes in mA.

Export files
------------
cocofest has no standard export format. Supported:

* the recommended path: ``from_cocofest_solution(sol, ...).to_json("profile.json")`` in the cocofest environment
  (see ``Examples/cocofest_export_profile.py``);
* ``from_cocofest_file`` for pickles / npz saved by cocofest: ``SolutionToPickle`` (keys "time", "control",
  "parameters"; it does not save the stim times, give them with ``stim_time=``) and the example-style exports
  (``save_sol_in_pkl`` in examples/fes_multibody: keys "time", "stim_time" and the flattened control names at top
  level, pickle or ``.npz``).
"""

import math
import pickle

import numpy as np

from .profiles import ChannelProfile, StimulationProfile

COCOFEST_TARGET_VERSION = "1.1.0"
PULSE_WIDTH_KEY = "last_pulse_width"
PULSE_INTENSITY_KEY = "pulse_intensity"
VELTINK_INTENSITY_KEY = "I"


def _suffixed(key: str, muscle: str | None) -> str:
    return key + ("_" + str(muscle) if muscle else "")


def _find_key(base: str, muscle: str | None, single: bool, *dicts) -> str:
    """
    Name of the variable of a muscle. In cocofest 1.1.0 a single muscle model (not FesMskModel) with a
    muscle_name has an unsuffixed "last_pulse_width" control (configure_last_pulse_width is called without
    muscle_name) but a suffixed "pulse_intensity_<muscle>": for a single muscle, both spellings are accepted.
    """
    key = _suffixed(base, muscle)
    if single and muscle and not any(key in d for d in dicts) and any(base in d for d in dicts):
        return base
    return key


def _per_muscle(value, muscle: str | None, what: str):
    """Scalar, or dict {muscle: value}."""
    if isinstance(value, dict):
        key = muscle if muscle in value else None
        if key is None and len(value) == 1 and muscle is None:
            key = next(iter(value))
        if key is None:
            raise ValueError(f"No {what} given for muscle '{muscle}' (given for {list(value)}).")
        return value[key]
    return value


def _node_index(node_times: np.ndarray, t: float, muscle: str) -> int:
    k = int(np.argmin(np.abs(node_times - t)))
    dt = (node_times[-1] - node_times[0]) / max(len(node_times) - 1, 1)
    if abs(node_times[k] - t) > 0.01 * dt + 1e-9:
        raise ValueError(
            f"Muscle '{muscle}': pulse at {t} s does not fall on a shooting node (closest node {node_times[k]} s). "
            f"Was the OCP built with n_shooting = model.get_n_shooting(final_time)?"
        )
    return k


def from_cocofest_data(
    stim_time,
    controls: dict,
    parameters: dict | None,
    final_time: float,
    muscles: list | None = None,
    amplitude: float | dict | None = None,
    pulse_width: float | dict | None = None,
    start_time: float = 0.0,
    min_pulse_width: float | None = None,
    metadata: dict | None = None,
) -> StimulationProfile:
    """
    Build a profile from the raw arrays of a cocofest solution. ``from_cocofest_solution`` and
    ``from_cocofest_file`` call it; use it directly for a custom export.

    Parameters
    ----------
    stim_time : list[float] | dict
        Pulse onsets in s, shared by all the muscles, or {muscle: list} per muscle.
    controls : dict
        {name: array (n_rows, n_shooting + 1)} as ``sol.decision_controls(to_merge=SolutionMerge.NODES)``.
        A 1-D array is taken as a single row.
    parameters : dict | None
        {name: 1-D array} as ``sol.parameters``.
    final_time : float
        Final time of the OCP in s (duration of the profile).
    muscles : list | None
        Muscle names (the suffix of the variable names). None means a single muscle model without muscle name:
        the keys have no suffix and the profile channel is named "muscle".
    amplitude : float | dict | None
        Amplitude in mA (scalar or {muscle: value}) for the models that do not optimize it (Ding2003, Ding2007,
        Marion). Must be None when the solution contains the pulse intensity (it is not overridden silently).
    pulse_width : float | dict | None
        Pulse width in us (scalar or {muscle: value}) for the models that do not optimize it (Ding2003,
        Hmed2018, Marion). Must be None when the solution contains the pulse width.
    start_time : float
        Time of the first shooting node in s (0 for an OCP; the window start for a receding horizon).
    min_pulse_width : float | None
        Pulses whose optimized width (us) is below this value are removed (e.g. ``model.pd0 * 1e6``: in the
        Ding2007 model a pulse at pd0 produces no force, and cocofest uses pd0 as "off").
    metadata : dict | None
        Added to the profile metadata.
    """
    controls = {k: np.atleast_2d(np.asarray(v, dtype=float)) for k, v in (controls or {}).items()}
    parameters = {k: np.asarray(v, dtype=float).ravel() for k, v in (parameters or {}).items()}
    muscle_list = [None] if not muscles else list(muscles)
    final_time = float(final_time)

    channels = []
    kinds = set()
    for muscle in muscle_list:
        name = str(muscle) if muscle else "muscle"
        times = stim_time[muscle if muscle in stim_time else name] if isinstance(stim_time, dict) else stim_time
        times = [float(t) for t in times if t >= start_time - 1e-12]  # previous_stim excluded
        rel_times = [t - start_time for t in times]
        single = len(muscle_list) == 1
        pw_key = _find_key(PULSE_WIDTH_KEY, muscle, single, controls)
        pi_key = _find_key(PULSE_INTENSITY_KEY, muscle, single, parameters, controls)

        veltink_key = _find_key(VELTINK_INTENSITY_KEY, muscle, single, controls)
        if veltink_key in controls and pw_key not in controls and pi_key not in controls and pi_key not in parameters:
            raise NotImplementedError(
                f"Muscle '{name}': the solution has a continuous current control ('I', Veltink models) without "
                f"pulse times; it can not be converted into a pulse train."
            )

        n_cols = None
        for key in (pw_key, pi_key):
            if key in controls:
                n_cols = controls[key].shape[1]
        node_times = None if n_cols is None else np.linspace(start_time, start_time + final_time, n_cols)

        #  Pulse widths
        if pw_key in controls:
            if pulse_width is not None:
                raise ValueError(f"Muscle '{name}': the pulse width is optimized ('{pw_key}'), do not give pulse_width.")
            row = controls[pw_key][0]
            widths = [row[_node_index(node_times, t, name)] * 1e6 for t in times]
            kinds.add("pulse_width")
        else:
            value = _per_muscle(pulse_width, muscle, "pulse_width")
            if value is None:
                raise ValueError(
                    f"Muscle '{name}': the solution does not contain the pulse width ('{pw_key}'): give pulse_width "
                    f"in us."
                )
            widths = [float(value)] * len(times)

        #  Amplitudes
        if pi_key in parameters:
            if amplitude is not None:
                raise ValueError(f"Muscle '{name}': the intensity is optimized ('{pi_key}'), do not give amplitude.")
            values = parameters[pi_key]
            all_times = times  # The parameter has one value per stim_time of the OCP
            if len(values) != len(all_times):
                raise ValueError(
                    f"Muscle '{name}': parameter '{pi_key}' has {len(values)} values for {len(all_times)} pulses."
                )
            amps = [float(v) for v in values]
            kinds.add("pulse_intensity")
        elif pi_key in controls:
            if amplitude is not None:
                raise ValueError(f"Muscle '{name}': the intensity is optimized ('{pi_key}'), do not give amplitude.")
            window = controls[pi_key]
            amps = [float(window[-1, _node_index(node_times, t, name)]) for t in times]
            kinds.add("pulse_intensity")
        else:
            value = _per_muscle(amplitude, muscle, "amplitude")
            if value is None:
                raise ValueError(
                    f"Muscle '{name}': the solution does not contain the pulse intensity ('{pi_key}'): give amplitude "
                    f"in mA."
                )
            amps = [float(value)] * len(times)

        if any(not math.isfinite(v) for v in widths + amps):
            raise ValueError(f"Muscle '{name}': NaN in the optimized values (pulse on the last node?).")
        if min_pulse_width is not None:
            kept = [k for k, w in enumerate(widths) if w >= min_pulse_width]
            rel_times = [rel_times[k] for k in kept]
            widths = [widths[k] for k in kept]
            amps = [amps[k] for k in kept]
        channels.append(ChannelProfile(name, rel_times, widths, amps))

    meta = {
        "source": "cocofest",
        "optimized": sorted(kinds) or ["none (stimulation times fixed by the user)"],
        "cocofest_target_version": COCOFEST_TARGET_VERSION,
    }
    meta.update(metadata or {})
    return StimulationProfile(channels, duration=final_time, metadata=meta)


def _cocofest_muscle_models(model) -> list:
    """Muscle models of a cocofest OCP model: [(muscle_name | None, muscle_model), ...]."""
    if hasattr(model, "muscles_dynamics_model"):  # FesMskModel
        return [(str(m.muscle_name), m) for m in model.muscles_dynamics_model]
    return [(getattr(model, "muscle_name", None) or None, model)]


def from_cocofest_solution(
    sol,
    amplitude: float | dict | None = None,
    pulse_width: float | dict | None = None,
    drop_pd0_pulses: bool = False,
    phase: int = 0,
    metadata: dict | None = None,
) -> StimulationProfile:
    """
    Convert a solved cocofest OCP (a ``bioptim.Solution``) into a StimulationProfile. cocofest / bioptim must be
    installed in the environment where this is called (lazy import).

    Parameters
    ----------
    sol : bioptim.Solution
        Solution of an OCP built with a cocofest model (``ModelMaker.create_model`` / ``FesMskModel``) with
        ``n_shooting = model.get_n_shooting(final_time)``. Single phase OCPs only.
    amplitude : float | dict | None
        Amplitude in mA (scalar or {muscle_name: value}) if the model does not optimize the intensity
        (Ding2003, Ding2007, Marion).
    pulse_width : float | dict | None
        Pulse width in us (scalar or {muscle_name: value}) if the model does not optimize it (Ding2003,
        Hmed2018, Marion).
    drop_pd0_pulses : bool
        Remove the pulses whose optimized width is at the model threshold pd0 (within 0.5 us): they produce no
        force in the Ding2007 model and cocofest uses pd0 as "off". Pulse width models only. Note that a pulse
        at pd0 (about 131 us) does stimulate a real muscle.
    phase : int
        Phase of the OCP to convert.
    metadata : dict | None
        Added to the profile metadata.

    Example (in the cocofest environment)
    -------------------------------------
    >>> sol = ocp.solve()
    >>> profile = from_cocofest_solution(sol, amplitude={"BIClong": 30, "TRIlong": 25})
    >>> profile.to_json("elbow_flexion_profile.json")
    """
    from bioptim import SolutionMerge  # Lazy import: bioptim is only needed in the optimization environment

    ocp = sol.ocp
    if len(ocp.nlp) != 1 and phase == 0:
        raise NotImplementedError("Only single phase cocofest OCPs are supported; convert each phase separately.")
    nlp = ocp.nlp[phase]
    muscle_models = _cocofest_muscle_models(nlp.model)

    controls = sol.decision_controls(to_merge=SolutionMerge.NODES)
    if isinstance(controls, list):  # multi-phase
        controls = controls[phase]
    parameters = sol.parameters
    time = sol.decision_time(to_merge=SolutionMerge.NODES)
    if isinstance(time, list):  # multi-phase
        time = time[phase]
    time = np.asarray(time, dtype=float).ravel()
    start_time, end_time = float(time[0]), float(time[-1])

    stim_time = {name or "muscle": list(m.stim_time) for name, m in muscle_models}
    min_pulse_width = None
    if drop_pd0_pulses:
        pd0 = [getattr(m, "pd0", None) for _, m in muscle_models]
        if any(p is None for p in pd0):
            raise ValueError("drop_pd0_pulses requires pulse width models (Ding2007 / Marion modified).")
        #  0.5 us margin: IPOPT returns values slightly above the bound; the P24 resolution is 1 us anyway
        min_pulse_width = max(pd0) * 1e6 + 0.5

    meta = {"model": sorted({type(m).__name__ for _, m in muscle_models})}
    try:
        import cocofest  # Only for the version, already imported by the user

        meta["cocofest_version"] = getattr(cocofest, "__version__", None)
    except ImportError:
        pass
    meta.update(metadata or {})

    return from_cocofest_data(
        stim_time=stim_time,
        controls=controls,
        parameters=parameters,
        final_time=end_time - start_time,
        muscles=[name for name, _ in muscle_models],
        amplitude=amplitude,
        pulse_width=pulse_width,
        start_time=start_time,
        min_pulse_width=min_pulse_width,
        metadata=meta,
    )


def _guess_muscles(keys) -> list | None:
    muscles = []
    for key in keys:
        for base in (PULSE_WIDTH_KEY, PULSE_INTENSITY_KEY):
            if key == base:
                return None
            if key.startswith(base + "_"):
                muscles.append(key[len(base) + 1:])
    return sorted(set(muscles)) or None


def from_cocofest_file(
    path: str,
    stim_time=None,
    muscles: list | None = None,
    amplitude: float | dict | None = None,
    pulse_width: float | dict | None = None,
    min_pulse_width: float | None = None,
    metadata: dict | None = None,
) -> StimulationProfile:
    """
    Load a cocofest solution saved as a pickle (``.pkl``) or ``.npz`` file and convert it into a
    StimulationProfile. Supported layouts (cocofest 1.1.0):

    * ``cocofest.SolutionToPickle``: {"time", "control": {...}, "parameters": {...}, ...}. The stim times are not
      saved in this file: give them with ``stim_time``.
    * example-style exports (``save_sol_in_pkl`` in cocofest/examples/fes_multibody): {"time", "stim_time",
      "<control name>": ..., "<state name>": ...} in a pickle or an ``.npz``.

    Opening a pickle executes code: only load files you trust. The pickles of ``SolutionToPickle`` contain only
    numpy arrays and can be read without cocofest / bioptim.

    Parameters
    ----------
    stim_time : list | dict | None
        Pulse onsets in s, required if the file does not contain "stim_time".
    muscles : list | None
        Muscle names; guessed from the "last_pulse_width_<muscle>" / "pulse_intensity_<muscle>" keys if None.
        Give them explicitly for Ding2003 solutions (no such key).
    Other parameters: see from_cocofest_data.
    """
    if str(path).endswith(".npz"):
        with np.load(path, allow_pickle=False) as f:
            data = {k: f[k] for k in f.files}
    else:
        with open(path, "rb") as f:
            data = pickle.load(f)
    if not isinstance(data, dict) or "time" not in data:
        raise ValueError(f"{path}: not a cocofest solution export (a dict with a 'time' key is expected).")

    controls = data.get("control")
    if isinstance(controls, dict):
        parameters = data.get("parameters") or {}
    else:  # Flattened layout
        controls = {
            k: v for k, v in data.items() if k.startswith(PULSE_WIDTH_KEY) or k.startswith(PULSE_INTENSITY_KEY)
        }
        parameters = {}
    if stim_time is None:
        if "stim_time" not in data:
            raise ValueError(
                f"{path} does not contain the stimulation times (SolutionToPickle does not save them): give "
                f"stim_time, i.e. the stim_time list given to the cocofest model."
            )
        stim_time = np.asarray(data["stim_time"], dtype=float).ravel().tolist()
    if muscles is None:
        muscles = _guess_muscles(list(controls) + list(parameters))

    time = np.asarray(data["time"], dtype=float).ravel()
    meta = {"file": str(path)}
    meta.update(metadata or {})
    return from_cocofest_data(
        stim_time=stim_time,
        controls=controls,
        parameters=parameters,
        final_time=float(time.max() - time.min()),
        muscles=muscles,
        amplitude=amplitude,
        pulse_width=pulse_width,
        start_time=float(time.min()),
        min_pulse_width=min_pulse_width,
        metadata=meta,
    )
