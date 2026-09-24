import importlib

import pytest

from pysciencemode import P24, Device

sciencemode_module = importlib.import_module("pysciencemode.sciencemode")
p24_module = importlib.import_module("pysciencemode.p24_interface")


@pytest.fixture
def no_sciencemode(monkeypatch):
    # Simulate an environment where sciencemode_cffi is not installed.
    monkeypatch.setattr(sciencemode_module, "sciencemode", None)
    monkeypatch.setattr(p24_module, "sciencemode", None)


def test_p24_raises_explicit_import_error_without_sciencemode(no_sciencemode):
    with pytest.raises(ImportError, match="sciencemode_cffi"):
        P24(port="COM_TEST")


def test_generic_p24_path_raises_explicit_import_error_without_sciencemode(no_sciencemode):
    with pytest.raises(ImportError, match="sciencemode_cffi"):
        sciencemode_module.RehastimGeneric(port="COM_TEST", device_type=Device.P24.value)
