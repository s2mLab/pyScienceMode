# pyScienceMode
Functional electrical stimulation (FES) research would benefit of an open, flexible control method for customizable
stimulation patterns. `pyScienceMode` provides a unified Python API for both Rehastim2 and P24 devices, enabling real-time
adjustment of frequency, intensity, pulse width, train duration and sensor-triggered control. It supports rapid
prototyping of personalized, real-time FES protocols, making novel rehabilitation strategies reproducible, adaptable and
easily extensible as new hardware emerges. Please have a look to the documentation for more information about
[pyScienceMode](https://pysciencemode.readthedocs.io/en/latest/index.html).

## How to install
pyScienceMode controls both the Rehastim2 and the P24. The low-level `sciencemode` module needed by the P24
(cffi bindings to HASOMED's [ScienceMode4 C library](https://github.com/ScienceMode/ScienceMode4_c_library))
is now built and shipped with pyScienceMode: no additional wheel is needed.

### Installing from PyPI
```bash
pip install pysciencemode
```
Prebuilt wheels are provided for CPython 3.10+ on Windows (x86_64), Linux (manylinux x86_64 and aarch64)
and macOS (Intel and Apple Silicon). The `p24` extra (`pip install "pysciencemode[p24]"`) is still accepted
for backward compatibility.

### Installing from Anaconda
```bash
conda install -c conda-forge pysciencemode
```

### Installing from source
Clone the repository with its submodule, then install (a C compiler is required):
```bash
git clone --recursive https://github.com/s2mLab/pyScienceMode.git
cd pyScienceMode
pip install .
```
Please refer to the [documentation](https://pysciencemode.readthedocs.io/en/latest/install.html) for more details.

If you previously installed the `sciencemode_cffi-1.0.0-cp310-cp310-win_amd64.whl` wheel, uninstall it first
(`pip uninstall sciencemode_cffi`): it provides the same `sciencemode` package.

## How to use

<p align="center">
  <a href="https://youtu.be/3PyUr6YnI94" target="_blank">
    <img
      src="docs/how_to_use_pysciencemode.png"
      alt="▶ How to use pysciencemode"
      width="480"
    />
  </a>
</p>

A set of example is provided in the `examples` folder to show how to control the Rehastim2 and the P24:
Please take a look at the [documentation example page](https://pysciencemode.readthedocs.io/en/latest/examples.html) for description of each example.

## Instruction for use

<strong>User manual Rehastim2:</strong> https://github.com/ScienceMode/ScienceMode2/tree/main/01_User%20Manual

<strong>User manual P24:</strong> https://github.com/ScienceMode/ScienceMode4_P24/tree/main/01_IFU_and_Protocol

The P24 Science/P24 Module is a device that can be controlled by a computer system via a specified interface to generate and output electrical
pulses. The P24 Science/P24 Module is intended for research applications only and is not intended to be used for medical purposes on
human beings according to Regulation (EU) 2017/745.

## Main differences between the Rehastim2 and the P24
They are some differences between the Rehastim2 and the P24.
Please take a look at the [documentation main differences page](https://pysciencemode.readthedocs.io/en/latest/main_differences.html) for more information.

## How to contribute
You are welcome to contribute to this project by following the steps describes in the 
[how to contribute](https://pysciencemode.readthedocs.io/en/latest/contributing.html) page.

## How to cite
[![status](https://joss.theoj.org/papers/39ed869b636795151756cc57c7e625ad/status.svg)](https://joss.theoj.org/papers/39ed869b636795151756cc57c7e625ad)</br>

Co et al., (2025). pyScienceMode: an Open-Source Python Package to control electro-stimulator through the Hasomed’s
science mode protocol. Journal of Open Source Software, 10(111), 8259, https://doi.org/10.21105/joss.08259

## Acknowledgements
The software development was supported by Ingénierie de technologies interactives en réadaptation [INTER #160 OptiStim](https://regroupementinter.com/fr/mandat/160-optistim/).
