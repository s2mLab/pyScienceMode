# pyScienceMode Installation
`pyScienceMode` is a Python interface to control the Rehastim2 and the P24. 

## How to install
To install the program run the following command in the main directory 

```bash
python setup.py install
```
To use the `P24` you need to install the [sciencemode library](.\sciencemode_cffi-1.0.0-cp310-cp310-win_amd64.whl)


You will need to create a new conda environment with Python 3.10 (important).
Then, navigate to the folder where the file `sciencemode_cffi-1.0.0-cp310-cp310-win_amd64.whl` is located 
and run the following command :
```bash
pip install sciencemode_cffi-1.0.0-cp310-cp310-win_amd64.whl
```
Now you can use the sciencemode library for the P24.

## Dependencies
There are some dependencies. You can install them by running the following command :

- [crccheck](https://pypi.org/project/crccheck/), [colorama](https://pypi.org/project/colorama/), [pyserial](https://pypi.org/project/pyserial/) and [typing](https://pypi.org/project/typing/)
```bash
pip install crccheck colorama pyserial typing
```
- [numpy](https://anaconda.org/conda-forge/numpy)
```bash
conda install -c conda-forge numpy
```

## How to contribute
You are welcome to contribute to this project by following the steps describes in the 
[how to contribute](contributing.rst) page.


## How to cite
If you use pyScienceMode, we would be grateful if you could cite the follow github repository : https://github.com/s2mLab/pyScienceMode

