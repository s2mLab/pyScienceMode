"""
Tests of the stimulation profiles, the cocofest bridge and the profile player, without hardware (fake sciencemode
library) and without cocofest / bioptim (the solution objects are duck-typed fakes built from the cocofest 1.1.0
data layout).
"""

import json
import pickle
import sys
import time
import types

import numpy as np
import pytest

from pysciencemode import (
    P24,
    ChannelProfile,
    Modes,
    P24_LIMITS,
    PlaybackReport,
    ProfilePlayer,
    ProfileValidationError,
    StimulationLimits,
    StimulationProfile,
    from_cocofest_file,
    from_cocofest_solution,
)
from pysciencemode.cocofest_bridge import from_cocofest_data
from pysciencemode.profiles import merge_segment_events
from tests.fake_sciencemode import install_fake_sciencemode

#  Loose timing tolerance: CI machines (and Windows timers) are jittery
TIMING_TOLERANCE = 0.03


#  Profiles
def two_muscle_profile():
    return StimulationProfile(
        [
            ChannelProfile("BIClong", [0.0, 0.025, 0.05, 0.075], [300, 300, 350, 350], 20),
            ChannelProfile("TRIlong", [0.1, 0.12], 250, [15, 18]),
        ],
        duration=0.2,
        metadata={"model": "DingModelPulseWidthFrequency", "source": "test"},
    )


def test_json_round_trip(tmp_path):
    profile = two_muscle_profile()
    path = tmp_path / "profile.json"
    text = profile.to_json(str(path))
    data = json.loads(text)
    assert data["format"] == "pysciencemode.stimulation_profile"
    assert data["channels"][0]["pulse_widths_us"] == [300, 300, 350, 350]
    assert data["channels"][1]["amplitudes_mA"] == [15, 18]

    for loaded in (StimulationProfile.from_json(str(path)), StimulationProfile.from_json(text)):
        assert loaded.to_dict() == profile.to_dict()
        assert loaded.metadata["model"] == "DingModelPulseWidthFrequency"
        assert loaded["TRIlong"].pulse_times == [0.1, 0.12]


def test_json_numpy_metadata_and_segment_input():
    profile = StimulationProfile(
        [ChannelProfile.from_dict({"name": "m", "segments": [
            {"start": 0, "duration": 0.1, "frequency": 50, "pulse_width": 200, "amplitude": 10}]})],
        metadata={"cost": np.float64(1.5), "weights": np.arange(3)},
    )
    assert profile["m"].pulse_times == pytest.approx([0, 0.02, 0.04, 0.06, 0.08])
    loaded = StimulationProfile.from_json(profile.to_json())
    assert loaded.metadata == {"cost": 1.5, "weights": [0, 1, 2]}


def test_invalid_profiles():
    with pytest.raises(ValueError, match="strictly increasing"):
        ChannelProfile("m", [0.0, 0.0], 200, 10)
    with pytest.raises(ValueError, match="3 values for 2 pulses"):
        ChannelProfile("m", [0.0, 0.1], [200, 200, 200], 10)
    with pytest.raises(ValueError, match="unique"):
        StimulationProfile([ChannelProfile("m", [0], 200, 10), ChannelProfile("m", [0], 200, 10)])
    with pytest.raises(ValueError, match="after the end"):
        StimulationProfile([ChannelProfile("m", [0, 0.3], 200, 10)], duration=0.2)
    with pytest.raises(ValueError, match="version"):
        StimulationProfile.from_dict({"version": 99, "channels": []})


def test_validation_and_clamping():
    profile = StimulationProfile(
        [ChannelProfile("m", [0.0, 0.005, 0.02, 0.04], [300, 600, 300, 300], [20, 20, 60, 20])]
    )
    assert profile.violations() == []  # Within the P24 limits
    profile.validate(P24_LIMITS)

    limits = StimulationLimits(max_amplitude=40, max_pulse_width=500, max_frequency=100)
    messages = profile.violations(limits)
    assert len(messages) == 3  # pulse width 600, amplitude 60, 200 Hz interval
    with pytest.raises(ProfileValidationError) as info:
        profile.validate(limits)
    assert len(info.value.violations) == 3

    clamped, changes = profile.clamped(limits)
    assert clamped.violations(limits) == []
    assert clamped["m"].pulse_times == [0.0, 0.02, 0.04]  # the 200 Hz pulse is dropped
    assert clamped["m"].amplitudes == [20, 40, 20]
    assert clamped.metadata["clamped"] is True
    assert len(changes) == 2
    #  The original is not modified
    assert profile["m"].amplitudes == [20, 20, 60, 20]

    charge = StimulationLimits(max_charge=6000)
    clamped, _ = StimulationProfile([ChannelProfile("m", [0.0], 300, 30)]).clamped(charge)
    assert clamped["m"].amplitudes == [20]

    tight = P24_LIMITS.tighten(limits)
    assert (tight.max_amplitude, tight.max_pulse_width, tight.max_frequency) == (40, 500, 100)


def test_segments():
    channel = ChannelProfile("m", [0.0, 0.02, 0.04, 0.06, 0.1, 0.15, 0.2], 300, [10, 10, 10, 20, 20, 20, 20])
    segments = channel.to_segments(end_time=1.0)
    assert [(s.start, s.n_pulses) for s in segments] == [(0.0, 3), (0.06, 1), (0.1, 3)]
    assert segments[0].frequency == pytest.approx(50)
    assert segments[0].end == pytest.approx(0.06)
    assert segments[1].frequency == pytest.approx(25)  # IPI 0.04 s to the next pulse
    assert segments[2].frequency == pytest.approx(20)
    assert segments[2].end == pytest.approx(0.25)  # last pulse gets the previous interval

    #  Slightly jittered intervals (optimizer output) are still grouped
    jittered = ChannelProfile("m", [0.0, 0.02001, 0.03999, 0.06], 300, 10)
    assert len(jittered.to_segments(interval_tolerance=1e-4)) == 1

    #  An interval longer than the longest P24 period is played as pulse + gap
    sparse = ChannelProfile("m", [0.0, 30.0], 300, 10)
    segs = sparse.to_segments(max_interval=16.383)
    assert [s.n_pulses for s in segs] == [1, 1]
    assert segs[0].end == pytest.approx(16.383)


def test_merge_segment_events():
    profile = two_muscle_profile()
    segments = profile.segments()
    states = merge_segment_events(segments, profile.end_time)
    times = [t for t, _ in states]
    assert times == pytest.approx([0.0, 0.05, 0.1, 0.12, 0.14, 0.2])
    t, state = states[0]
    assert state["BIClong"].pulse_width == 300 and state["TRIlong"] is None
    assert states[2][1]["BIClong"] is None and states[2][1]["TRIlong"].amplitude == 15
    assert all(s is None for s in states[-1][1].values())


#  cocofest bridge (duck-typed solutions, no cocofest install)
class FakeSolution:
    """Mimics the parts of a bioptim 3.4 Solution of a cocofest 1.1.0 OCP read by from_cocofest_solution."""

    def __init__(self, model, controls, parameters, final_time, n_shooting):
        self.ocp = types.SimpleNamespace(nlp=[types.SimpleNamespace(model=model)])
        self._controls = controls
        self.parameters = parameters
        self._time = np.linspace(0, final_time, n_shooting + 1).reshape(-1, 1)

    def decision_controls(self, to_merge=None):
        return self._controls

    def decision_time(self, to_merge=None):
        return self._time


@pytest.fixture
def fake_bioptim(monkeypatch):
    module = types.ModuleType("bioptim")
    module.SolutionMerge = types.SimpleNamespace(NODES="nodes", PHASES="phases")
    monkeypatch.setitem(sys.modules, "bioptim", module)


class DingModelPulseWidthFrequency:  # Same class name as in cocofest, for the metadata
    def __init__(self, stim_time, muscle_name=None):
        self.stim_time = stim_time
        self.muscle_name = muscle_name
        self.pd0 = 0.000131405


def test_from_cocofest_solution_pulse_width_single_muscle(fake_bioptim):
    stim_time = [0.0, 0.1, 0.2, 0.3]
    n_shooting = 4  # model.get_n_shooting(0.4) with a 10 Hz train
    pw = np.array([[0.0003, 0.0004, 0.0005, 0.000131405, np.nan]])
    sol = FakeSolution(DingModelPulseWidthFrequency(stim_time), {"last_pulse_width": pw}, {}, 0.4, n_shooting)

    profile = from_cocofest_solution(sol, amplitude=30)
    assert profile.names == ["muscle"]
    assert profile.duration == pytest.approx(0.4)
    assert profile["muscle"].pulse_times == stim_time
    assert profile["muscle"].pulse_widths == pytest.approx([300, 400, 500, 131.405])
    assert profile["muscle"].amplitudes == [30] * 4
    assert profile.metadata["model"] == ["DingModelPulseWidthFrequency"]
    assert profile.metadata["optimized"] == ["pulse_width"]

    dropped = from_cocofest_solution(sol, amplitude=30, drop_pd0_pulses=True)
    assert dropped["muscle"].pulse_times == [0.0, 0.1, 0.2]

    #  Single muscle model with a muscle_name: cocofest keeps the control unsuffixed
    named = FakeSolution(
        DingModelPulseWidthFrequency(stim_time, "BIClong"), {"last_pulse_width": pw}, {}, 0.4, n_shooting
    )
    assert from_cocofest_solution(named, amplitude=30)["BIClong"].pulse_widths == pytest.approx(
        [300, 400, 500, 131.405]
    )

    with pytest.raises(ValueError, match="give amplitude"):
        from_cocofest_solution(sol)
    with pytest.raises(ValueError, match="do not give pulse_width"):
        from_cocofest_solution(sol, amplitude=30, pulse_width=300)


def test_from_cocofest_solution_musculoskeletal_uneven_stim(fake_bioptim):
    #  Uneven stim times: n_shooting is the LCM of the denominators (10 nodes over 0.5 s, dt = 0.05 s)
    stim_time = [0.0, 0.15, 0.2, 0.35]
    muscles = [DingModelPulseWidthFrequency(stim_time, "BIClong"), DingModelPulseWidthFrequency(stim_time, "TRIlong")]
    model = types.SimpleNamespace(muscles_dynamics_model=muscles)
    nodes = np.linspace(0, 0.5, 11)
    controls = {
        "last_pulse_width_BIClong": np.array([[1e-4 * (1 + k) for k in range(10)] + [np.nan]]),
        "last_pulse_width_TRIlong": np.array([[2e-4] * 10 + [np.nan]]),
        "q": np.zeros((2, 11)),
    }
    sol = FakeSolution(model, controls, {}, 0.5, 10)
    profile = from_cocofest_solution(sol, amplitude={"BIClong": 30, "TRIlong": 25})
    assert profile.names == ["BIClong", "TRIlong"]
    idx = [int(round(t / 0.05)) for t in stim_time]
    assert profile["BIClong"].pulse_widths == pytest.approx([100 * (1 + k) for k in idx])
    assert profile["TRIlong"].pulse_widths == pytest.approx([200] * 4)
    assert profile["TRIlong"].amplitudes == [25] * 4
    assert nodes[idx] == pytest.approx(stim_time)


def test_from_cocofest_intensity_parameter_and_window_control():
    stim_time = [0.0, 0.1, 0.2]
    controls = {"pulse_intensity_BIClong": np.array([[0, 0, 40, 0], [0, 30, 40, 50]])}  # truncation 2
    #  Parameter present: it is used (one value per pulse, mA)
    profile = from_cocofest_data(
        stim_time, controls, {"pulse_intensity_BIClong": np.array([31.0, 41.0, 51.0])}, 0.3, ["BIClong"],
        pulse_width=250,
    )
    assert profile["BIClong"].amplitudes == [31, 41, 51]
    assert profile["BIClong"].pulse_widths == [250] * 3
    #  Parameter absent: last row of the sliding window control at the pulse node
    profile = from_cocofest_data(stim_time, controls, {}, 0.3, ["BIClong"], pulse_width=250)
    assert profile["BIClong"].amplitudes == [0, 30, 40]
    with pytest.raises(ValueError, match="give pulse_width"):
        from_cocofest_data(stim_time, controls, {}, 0.3, ["BIClong"])


def test_from_cocofest_ding2003_and_veltink():
    profile = from_cocofest_data([0.0, 0.5], {}, {}, 1.0, None, amplitude=20, pulse_width=300)
    assert profile["muscle"].amplitudes == [20, 20]
    assert "none" in profile.metadata["optimized"][0]
    with pytest.raises(NotImplementedError):
        from_cocofest_data([], {"I": np.zeros((1, 5))}, {}, 1.0, None, amplitude=1, pulse_width=1)
    with pytest.raises(ValueError, match="shooting node"):
        from_cocofest_data([0.0, 0.13], {"last_pulse_width": np.zeros((1, 5))}, {}, 0.4, None, amplitude=10)


def test_from_cocofest_files(tmp_path):
    #  cocofest.SolutionToPickle layout: no stim_time in the file
    pw = np.array([[0.0003, 0.0004, 0.0005, 0.0006, np.nan]])
    data = {
        "time": np.linspace(0, 0.4, 5),
        "states": {"F": np.zeros(5)},
        "control": {"last_pulse_width": pw},
        "parameters": {},
        "parameters_bounds": {},
        "time_to_optimize": 1.0,
        "bio_model_path": None,
    }
    path = tmp_path / "sol.pkl"
    with open(path, "wb") as f:
        pickle.dump(data, f)
    with pytest.raises(ValueError, match="stim_time"):
        from_cocofest_file(str(path), amplitude=20)
    profile = from_cocofest_file(str(path), stim_time=[0, 0.1, 0.2, 0.3], amplitude=20)
    assert profile["muscle"].pulse_widths == pytest.approx([300, 400, 500, 600])

    #  Example-style export (save_sol_in_pkl), npz with flattened keys and stim_time
    npz = tmp_path / "sol.npz"
    np.savez_compressed(
        npz,
        time=np.linspace(0, 0.4, 5),
        stim_time=np.array([0, 0.1, 0.2, 0.3]),
        last_pulse_width_Biceps=pw,
        last_pulse_width_Triceps=pw * 0.5,
        F_Biceps=np.zeros((1, 5)),
    )
    profile = from_cocofest_file(str(npz), amplitude={"Biceps": 20, "Triceps": 15})
    assert profile.names == ["Biceps", "Triceps"]
    assert profile["Triceps"].pulse_widths == pytest.approx([150, 200, 250, 300])


#  Player (fake P24)
@pytest.fixture
def fake(monkeypatch):
    return install_fake_sciencemode(monkeypatch)


@pytest.fixture
def stimulator(fake):
    stim = P24(port="COM_FAKE")
    yield stim
    stim._stop_continuous(pause=False, raise_error=False)


def update_states(fake):
    """[(t, {channel_number: (frequency, pulse_width, amplitude)})] of every ml_update sent."""
    out = []
    for call in fake.of("smpt_send_ml_update"):
        out.append(
            (
                call.t,
                {i + 1: (round(1000.0 / period, 6), points[0][0], points[0][1]) for i, (period, _, points) in call.data.items()},
            )
        )
    return out


def test_player_channel_map_validation(stimulator):
    profile = two_muscle_profile()
    with pytest.raises(ValueError, match="not in channel_map"):
        ProfilePlayer(stimulator, profile, {"BIClong": 1})
    with pytest.raises(ValueError, match="not in the profile"):
        ProfilePlayer(stimulator, profile, {"BIClong": 1, "TRIlong": 2, "DELT": 3})
    with pytest.raises(ValueError, match="same P24 channel"):
        ProfilePlayer(stimulator, profile, {"BIClong": 1, "TRIlong": 1})
    with pytest.raises(ValueError, match=r"\[1, 8\]"):
        ProfilePlayer(stimulator, profile, {"BIClong": 1, "TRIlong": 9})
    with pytest.raises(ProfileValidationError):
        ProfilePlayer(stimulator, profile, {"BIClong": 1, "TRIlong": 2}, limits=StimulationLimits(max_amplitude=10))


def test_player_schedule_and_channel_mapping(fake, stimulator):
    profile = two_muscle_profile()
    player = ProfilePlayer(stimulator, profile, {"BIClong": 3, "TRIlong": 5}, keep_alive_period=0.05)
    assert [u.t for u in player.schedule] == pytest.approx([0.0, 0.05, 0.1, 0.12, 0.14, 0.2])
    assert player.schedule[0].state == {3: (pytest.approx(40), 300, 20), 5: (pytest.approx(50), 250, 0)}

    report = player.play()
    assert isinstance(report, PlaybackReport)
    assert report.completed and report.error is None
    assert not stimulator.is_stimulating

    sent = update_states(fake)
    #  One update per planned state, then the zero-amplitude update of stop_stimulation
    assert len(sent) == len(player.schedule) + 1
    t_first = sent[0][0]
    for (t, state), planned in zip(sent, player.schedule):
        assert set(state) == {3, 5}  # mapped channels only
        for number, (frequency, pulse_width, amplitude) in planned.state.items():
            assert state[number][0] == pytest.approx(frequency, rel=1e-6)
            assert state[number][1] == int(round(pulse_width))
            assert state[number][2] == amplitude
        assert t - t_first == pytest.approx(planned.t, abs=TIMING_TOLERANCE)
    assert all(amplitude == 0 for _, _, amplitude in sent[-1][1].values())

    summary = report.summary()
    assert summary["n_played"] == len(player.schedule) and summary["n_skipped"] == 0
    assert summary["max_abs_error_ms"] < 1000 * TIMING_TOLERANCE
    assert "completed" in str(report)
    assert fake.count("smpt_send_ml_init") == 1


def test_player_absolute_deadlines_no_drift(fake, stimulator):
    #  50 updates, one every 10 ms (a different IPI each pulse): the error must not accumulate
    times = np.cumsum([0.0] + [0.008 + 0.0005 * (k % 5) for k in range(49)])
    profile = StimulationProfile([ChannelProfile("m", times.tolist(), 300, 20)])
    player = ProfilePlayer(stimulator, profile, {"m": 1}, keep_alive_period=0.2)
    assert len(player.schedule) > 40
    report = player.play()
    errors = report.errors()
    assert errors and abs(statistics_mean(errors[-10:])) < TIMING_TOLERANCE
    assert max(abs(e) for e in errors) < 2 * TIMING_TOLERANCE


def statistics_mean(values):
    return sum(values) / len(values)


def test_player_stop_and_callback(fake, stimulator):
    events = []
    profile = StimulationProfile.constant(["m"], frequency=20, duration=2.0, pulse_width=300, amplitude=20)
    player = ProfilePlayer(stimulator, profile, {"m": 2}, mode=Modes.DOUBLET, callback=events.append,
                           keep_alive_period=0.05)
    assert len(player.schedule) == 2  # constant profile: start + final off
    player.start()
    assert player.is_playing and stimulator.is_stimulating
    time.sleep(0.2)
    player.stop()
    assert not player.is_playing and not stimulator.is_stimulating
    assert not player.report.completed
    assert update_states(fake)[-1][1][2][2] == 0  # paused
    assert any(e.kind == "keep_alive" for e in events)
    #  Doublet: 7 points per channel
    assert len(fake.of("smpt_send_ml_update")[0].data[1][2]) == 7
    with pytest.raises(RuntimeError, match="already been played"):
        player.start()


def test_player_error_propagates_and_pauses(fake, stimulator):
    profile = StimulationProfile.constant(["m"], frequency=20, duration=1.0, pulse_width=300, amplitude=20)
    player = ProfilePlayer(stimulator, profile, {"m": 1}, keep_alive_period=0.05)
    player.start()
    fake.channel_states = [fake.lib.Smpt_Ml_Channel_State_Electrode_Error] + [0] * 7
    with pytest.raises(RuntimeError, match="Electrode error"):
        player.wait(timeout=3)
    assert isinstance(player.report.error, RuntimeError)
    assert fake.ml_update_amplitudes()[-1] == 0  # best-effort pause of the stimulation thread
