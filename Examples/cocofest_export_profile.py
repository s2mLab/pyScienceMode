"""
Step 1 of the cocofest -> P24 workflow: optimize a stimulation with cocofest and export it as a pyScienceMode
StimulationProfile (JSON). Run this in the cocofest conda environment (cocofest 1.1.0 / bioptim 3.4.0), where
pyScienceMode is also installed (``pip install -e <pyScienceMode>``: it does not need the stimulator library to
export a profile).

The OCP is the cocofest example examples/getting_started/optimization/pulse_width_optimization.py: 10 pulses at
50 Hz, the pulse widths are optimized with the Ding2007 model to reach 200 N at the end. The stimulation times are
fixed (cocofest does not optimize them) and the amplitude is not a variable of Ding2007: give the amplitude used
when the model was identified on the participant.

Step 2: play the file on the P24 with Examples/p24_play_profile.py.
"""

import numpy as np
from bioptim import ControlType, Node, ObjectiveFcn, ObjectiveList, OdeSolver, OptimalControlProgram, Solver
from cocofest import ModelMaker, OcpFes

from pysciencemode import StimulationLimits, from_cocofest_solution


def prepare_ocp(model, final_time, pw_max):
    n_shooting = model.get_n_shooting(final_time=final_time)  # Every pulse must fall on a shooting node
    numerical_data_time_series, _ = model.get_numerical_data_time_series(n_shooting, final_time)
    dynamics_options = OcpFes.declare_dynamics_options(
        numerical_time_series=numerical_data_time_series, ode_solver=OdeSolver.RK4(n_integration_steps=10)
    )
    objective_functions = ObjectiveList()
    objective_functions.add(ObjectiveFcn.Lagrange.MINIMIZE_STATE, key="F", weight=1, quadratic=True)
    objective_functions.add(
        ObjectiveFcn.Mayer.MINIMIZE_STATE, key="F", node=Node.END, target=200, weight=1e5, quadratic=True
    )
    return OptimalControlProgram(
        bio_model=[model],
        dynamics=dynamics_options,
        n_shooting=n_shooting,
        phase_time=final_time,
        objective_functions=objective_functions,
        x_init=OcpFes.set_x_init(model),
        x_bounds=OcpFes.set_x_bounds(model),
        u_bounds=OcpFes.set_u_bounds(model, max_bound=pw_max),
        u_init=OcpFes.set_u_init(model),
        control_type=ControlType.CONSTANT,
        use_sx=True,
    )


def main():
    final_time = 0.2
    model = ModelMaker.create_model(
        "ding2007",
        muscle_name="BIClong",
        sum_stim_truncation=10,
        stim_time=list(np.linspace(0, final_time, 11)[:-1]),
    )
    ocp = prepare_ocp(model, final_time=final_time, pw_max=0.0006)
    sol = ocp.solve(Solver.IPOPT())

    #  Pulse widths come from the solution (control "last_pulse_width_BIClong", s -> us), the pulse times from
    #  model.stim_time. Ding2007 does not optimize the intensity: give it (mA).
    profile = from_cocofest_solution(
        sol,
        amplitude=30,
        drop_pd0_pulses=True,  # pulses left at pd0 produce no force in the model: do not stimulate them
        metadata={"participant": "P01", "objective": "200 N at t_f"},
    )

    #  Optional: check the profile against the limits of the participant before exporting it
    limits = StimulationLimits(max_amplitude=40, max_pulse_width=600, max_frequency=100)
    profile.validate(limits)

    profile.to_json("cocofest_profile.json")
    for channel in profile.channels:
        print(channel.name, [round(t, 3) for t in channel.pulse_times], [round(w) for w in channel.pulse_widths])


if __name__ == "__main__":
    main()
