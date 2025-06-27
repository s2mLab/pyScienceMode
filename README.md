# pyScienceMode
Functional electrical stimulation (FES) research would benefit of an open, flexible control method for customizable
stimulation patterns. `pyScienceMode` provides a unified Python API for both Rehastim2 and P24 devices, enabling real-time
adjustment of frequency, intensity, pulse width, train duration and sensor-triggered control. It supports rapid
prototyping of personalized, real-time FES protocols, making novel rehabilitation strategies reproducible, adaptable and
easily extensible as new hardware emerges. Please have a look to the documentation for more information about
[pyScienceMode](https://pysciencemode.readthedocs.io/en/latest/index.html).

## How to install
These are the different ways to install pyScienceMode for the Rehastim2 control.
To control the P24, please follow the given steps in `Installing from source` as it requires an additional wheel compilation.

### Installing from PyPI
```bash
pip install pysciencemode
```

### Installing from Anaconda
```bash
conda install -c conda-forge pysciencemode
```

### Installing from source
Please refer to the [documentation](https://pysciencemode.readthedocs.io/en/latest/install.html) to install pyScienceMode. 

### Additional installation step for the P24 stimulator
pysciencemode is not compatible with macOS and Linux for the control of the stimulator P24.
As soon as the P24 wrapper will be compatible with macOS and Linux, we will update the documentation.

<strong>For Python 3.10 only:</strong> navigate to the folder where the file sciencemode_cffi-1.0.0-cp310-cp310-win_amd64.whl is located and run the following command
```bash
pip install sciencemode_cffi-1.0.0-cp310-cp310-win_amd64.whl
```
<strong>For other Python version:</strong> build your own wheel from https://github.com/ScienceMode/ScienceMode4_python_wrapper and pip install it in your environment.

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
Please refer to the [documentation cite page](https://pysciencemode.readthedocs.io/en/latest/cite.html) to cite pyScienceMode.

## Acknowledgements
The software development was supported by Ingénierie de technologies interactives en réadaptation [INTER #160 OptiStim](https://regroupementinter.com/fr/mandat/160-optistim/).
