# pyScienceMode
`pyScienceMode` is a Python interface to control the Rehastim2 and the RehastimP24. 
Please have a look to the documentation for more information about [pyScienceMode
## How to install
To install the program run the following command in the main directory 

```bash
python setup.py install
```
To use the `RehastimP24` you need to install the [sciencemode library](.\sciencemode_cffi-1.0.0-cp310-cp310-win_amd64.whl)


You will need to create a new conda environment with Python 3.10 (important).
Then, navigate to the folder where the file `sciencemode_cffi-1.0.0-cp310-cp310-win_amd64.whl` is located 
and run the following command :
```bash
pip install sciencemode_cffi-1.0.0-cp310-cp310-win_amd64.whl
```
Now you can use the sciencemode library for the RehastimP24.

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


## How to use
A set of example is provided in the `examples` folder to show how to control the Rehastim2 and the RehastimP24 :

[rehastim2_example.py](https://github.com/s2mLab/pyScienceMode/blob/a98becb49be6120482d7a6936d8f03b6574e5eae/examples/rehastim2_example.py) 

[rehastimp24_example.py](https://github.com/s2mLab/pyScienceMode/blob/a98becb49be6120482d7a6936d8f03b6574e5eae/examples/rehastimp24_example.py) 

## Main differences between the Rehastim2 and the RehastimP24

|                                                                      | Rehastim2                                                                                              | RehastimP24                                                                                      |
|----------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| Pulse width                                                          | [0, 500] **μs**                                                                                        | [10, 65520] **μs**                                                                               |
| Frequency                                                            | [1, 50] **Hz** for 8 channels                                                                          | [0.5, 2000] **Hz** customizable                                                                  | 
| Pulse form                                                           | Biphasic rectangular impulses with balanced electric charge                                            | Balanced biphasic square pulses or variable (adjustable using 16 discrete characteristic points) |
| Communication speed                                                  | [20, 100] **ms**                                                                                       | [5,15] **ms**                                                                                    | 
| Interpulse interval                                                  | 8 ms per stimulation module                                                                            | 5ms (can be modified)                                                                            | 
| Serial port                                                          | USB with galvanic isolation                                                                            | USB Type-C                                                                                       |
| Behavior when several channels are activated with too high frequency | The stimulator will stimulate at the maximum frequency to satisfy the offset between several channels. | Stimulation will not be active and the Rehastimp24 LED will be green.                            |

## How to contribute
You are welcome to contribute to this project by following the steps describes in the 
[how to contribute](docs/contributing.rst) page.

## License
pyScienceMode is distributed under the MIT licence. For more information, please consult the [LICENSE](./LICENSE) file in our repository.

## How to cite
If you use pyScienceMode, we would be grateful if you could cite the follow github repository : https://github.com/s2mLab/pyScienceMode

