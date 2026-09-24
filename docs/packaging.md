# Packaging and releases (maintainers)

pyScienceMode ships a small C extension, `sciencemode._sciencemode`: cffi bindings (API mode) to
HASOMED's [ScienceMode4 C library](https://github.com/ScienceMode/ScienceMode4_c_library)
(MPL-2.0 OR LGPL-3.0-or-later), vendored as the git submodule `extern/ScienceMode4_c_library`
and compiled statically with CMake through [scikit-build-core](https://scikit-build-core.readthedocs.io).
The wheels are therefore platform-specific, but use the CPython stable ABI (`cp310-abi3`):
one wheel per platform serves every CPython >= 3.10.

## Wheels (GitHub Actions)
`.github/workflows/wheels.yml` runs [cibuildwheel](https://cibuildwheel.pypa.io) (configured in
`[tool.cibuildwheel]` of `pyproject.toml`) on every push to `main` and every pull request:

| Platform | Runner | Wheel tag |
|---|---|---|
| Windows x86_64 | `windows-latest` | `win_amd64` |
| Linux x86_64 | `ubuntu-latest` | `manylinux_2_28_x86_64` |
| Linux aarch64 | `ubuntu-24.04-arm` (native) | `manylinux_2_28_aarch64` |
| macOS Intel | `macos-15-intel` | `macosx_*_x86_64` |
| macOS Apple Silicon | `macos-14` | `macosx_*_arm64` |

Each wheel is tested on CPython 3.10 to 3.13 (import of `sciencemode` and `pysciencemode`). An sdist
(containing the submodule sources) is also built and test-installed.

## Publishing to PyPI
Pushing a tag `v*` (e.g. `v1.2.0`, matching `version` in `pyproject.toml`) runs the `publish` job,
which uploads the wheels and the sdist with [trusted publishing](https://docs.pypi.org/trusted-publishers/)
(no API token stored in GitHub). One-time setup:

1. On <https://pypi.org/manage/project/pysciencemode/settings/publishing/> (project owner account),
   add a GitHub trusted publisher: owner `s2mLab`, repository `pyScienceMode`, workflow `wheels.yml`,
   environment `pypi`.
2. On GitHub, *Settings > Environments*, create the environment `pypi` (optionally with required
   reviewers and a tag rule `v*`).

## conda-forge
The `pysciencemode` feedstock currently packages a pure-Python (`noarch: python`) build. With the
compiled extension, the recipe (`recipe/meta.yaml`, or `recipe.yaml` for rattler-build) must change:

* **source**: use the PyPI sdist (it contains the submodule sources). A GitHub tag archive does
  *not* contain the submodule; if used, add a second source entry for `ScienceMode4_c_library`
  at the pinned commit with `folder: extern/ScienceMode4_c_library`.
* **build**: drop `noarch: python`; script
  `{{ PYTHON }} -m pip install . -vv --no-deps --no-build-isolation`; bump the build number.
* **requirements**:
  * `build`: `{{ compiler('c') }}`, `{{ stdlib('c') }}`, `cmake >=3.26`, `ninja`
  * `host`: `python`, `pip`, `scikit-build-core >=0.11`, `cffi >=1.17`
  * `run`: `python`, `numpy`, `crccheck`, `pyserial`, `cffi >=1.17`
* **test**: `imports: [pysciencemode, sciencemode.sciencemode]`.
* **about**: `license: MIT AND (MPL-2.0 OR LGPL-3.0-or-later)` and list the license files
  (`LICENSE`, `extern/ScienceMode4_c_library/LICENSE`, `extern/ScienceMode4_c_library/LICENSE_LGPL_3_0`).

The feedstock builds one package per Python version (conda-forge does not use the abi3 wheel);
this is handled automatically once `noarch` is removed.

## Updating the ScienceMode4 C library
Bump the submodule, then regenerate the committed cffi declarations (see
[the installation page](install.md)):
```bash
git -C extern/ScienceMode4_c_library fetch && git -C extern/ScienceMode4_c_library checkout <commit>
pip install cffi pycparser ziglang
python tools/cffi/generate_cdef.py
```
