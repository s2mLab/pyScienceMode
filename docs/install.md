# pyScienceMode Installation
`pyScienceMode` is a Python interface to control the Rehastim2 and the P24. 

## How to install
To install the package from source, run the following command in the main directory
(add `-e` for an editable/development install):

```bash
pip install .
```
The runtime dependencies ([numpy](https://pypi.org/project/numpy/), [crccheck](https://pypi.org/project/crccheck/)
and [pyserial](https://pypi.org/project/pyserial/)) are declared in `pyproject.toml` and installed automatically.
With conda, you can alternatively create the environment from `environment.yml`:
```bash
conda env create -f environment.yml
```

## Additional step for the P24
To use the `P24`, install the `p24` extra, which pulls the `cffi` dependency:
```bash
pip install ".[p24]"
```
You also need the `sciencemode` library, which is not distributed on PyPI. A prebuilt wheel,
[sciencemode_cffi-1.0.0-cp310-cp310-win_amd64.whl](../sciencemode_cffi-1.0.0-cp310-cp310-win_amd64.whl),
is currently available for **Windows and Python 3.10 only**.
Create an environment with Python 3.10, navigate to the folder where the wheel is located and run:
```bash
pip install sciencemode_cffi-1.0.0-cp310-cp310-win_amd64.whl
```
For other platforms or Python versions, build your own wheel from
https://github.com/ScienceMode/ScienceMode4_python_wrapper and install it in your environment.

## How to contribute
You are welcome to contribute to this project by following the steps describes in the 
[how to contribute](contributing.rst) page.


## How to cite
If you use pyScienceMode, we would be grateful if you could cite the follow github repository : https://github.com/s2mLab/pyScienceMode

