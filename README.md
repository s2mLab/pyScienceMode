# pyScienceMode2
`pyScienceMode2` is  Python interface to control the Rehastim2 and the RehastimP24. Please have a look to the documentation for more information about [pyScienceMode2]

## How to install
To install the program run the following command in the main directory 

```bash
python setup.py install
```
To use the `RehastimP24` you need to install the `sciencemode` library.

You will need to create a new environment with Python 3.10 (important)
Navigate to the folder where the file `sciencemode_cffi-1.0.0-cp310-cp310-win_amd64.whl` is located 
and run the following command :
```bash
pip install sciencemode_cffi-1.0.0-cp310-cp310-win_amd64.whl
```
Now you can use the sciencemode library for the RehastimP24.

## Dependencies
There are some dependencies. You can install them by running the following command :

- crccheck, colorama, pyserial and typing
```bash
pip install crccheck colorama pyserial typing
```
- [numpy](https://anaconda.org/conda-forge/numpy)


## How to use
A set of example is provided in the `examples` to show how to control the Rehastim2 and the RehastimP24 :

[rehastim2_example.py](examples/rehastim2_example.py) 
[rehastimp24_example.py](examples/rehastimp24_example.py) 

## Main differences between the Rehastim2 and the RehastimP24

|                     |Rehastim2                                                   |RehastimP24                                                                                      |
|---------------------|------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| Pulse width         | [0, 500] **μs**                                            | [10, 65520] **μs**                                                                              |
| Frequency           | [1, 50] **Hz** for 8 channels                              | [0.5, 2000] **Hz** customizable                                                                 | 
| Pulse form          | Biphasic rectangular impulses with balanced electric charge | Balanced biphasic square pulses or variable (adjustable using 16 discrete characteristic points) |
| Communication speed | [20, 100] **ms**                                           | [5,15] **ms**                                                                                       | 
| Interpulse interval | 8 ms per stimulation module                                | 5ms (can be modified)                                                                           | 
| Serial port         | USB with galvanic isolation                                | USB Type-C                                                                                      |

## How to contribute
You are welcome to contribute to this project by following the steps describes in the 
[how to contribute] "nom de la page" page.

## How to cite
If you are using the biosig live library please cite us by following the guidelines available [here]"nom de la page".
