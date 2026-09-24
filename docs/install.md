# pyScienceMode Installation
`pyScienceMode` is a Python interface to control the Rehastim2 and the P24. 

## How to install
To install the package from source, clone the repository **with its submodule** (the
[ScienceMode4 C library](https://github.com/ScienceMode/ScienceMode4_c_library) used by the P24)
and run the following command in the main directory (add `-e` for an editable/development install):

```bash
git clone --recursive https://github.com/s2mLab/pyScienceMode.git
# or, in an existing clone: git submodule update --init --recursive
pip install .
```
The runtime dependencies ([numpy](https://pypi.org/project/numpy/), [crccheck](https://pypi.org/project/crccheck/),
[pyserial](https://pypi.org/project/pyserial/) and [cffi](https://pypi.org/project/cffi/)) are declared in
`pyproject.toml` and installed automatically.
With conda, you can alternatively create the environment from `environment.yml`:
```bash
conda env create -f environment.yml
```

Building from source compiles a small C extension, so it needs a C compiler
(MSVC "Build Tools for Visual Studio" on Windows, `gcc`/`clang` on Linux, the Xcode command line
tools on macOS). CMake and Ninja are fetched automatically by the build backend
([scikit-build-core](https://scikit-build-core.readthedocs.io)) if they are not installed.

## P24 support
The low-level `sciencemode` module used by the `P24` is now compiled from the ScienceMode4 C library
and installed together with pyScienceMode: no separate wheel is needed any more, and it works on
Windows, Linux and macOS. It is still importable as before:
```python
from sciencemode import sciencemode
sciencemode.lib, sciencemode.ffi
```
The `p24` extra (`pip install ".[p24]"`) is kept for backward compatibility.

If you previously installed the prebuilt `sciencemode_cffi` wheel, uninstall it first, since it
provides the same `sciencemode` package:
```bash
pip uninstall sciencemode_cffi
```

### Regenerating the cffi declarations (maintainers)
The cffi `cdef` (`tools/cffi/smpt_cdef.h`) is generated from the C headers and committed, so the
build does not need a C preprocessor. Regenerate it only after bumping the
`extern/ScienceMode4_c_library` submodule:
```bash
pip install cffi pycparser ziglang   # ziglang provides a portable C preprocessor
python tools/cffi/generate_cdef.py
```
Any C preprocessor works (`$CPP`, `cpp`, `gcc -E`, `clang -E` are tried first). Review the diff of
`smpt_cdef.h` before committing.

## How to contribute
You are welcome to contribute to this project by following the steps describes in the 
[how to contribute](contributing.rst) page.


## How to cite
If you use pyScienceMode, we would be grateful if you could cite the follow github repository : https://github.com/s2mLab/pyScienceMode

