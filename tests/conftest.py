"""
Shared pytest configuration.

Tests that need a real stimulator are marked ``@pytest.mark.hardware`` (usually via a module-level
``pytestmark``) and are skipped unless a serial port is given, either on the command line or through
the ``PYSCIENCEMODE_PORT`` environment variable::

    pytest                                              # hardware tests skipped
    pytest tests/test_update_parameter_p24.py --port COM4
    PYSCIENCEMODE_PORT=/dev/ttyUSB0 pytest -m "hardware and rehastim2"

Tests marked ``@pytest.mark.interactive`` additionally need an operator (e.g. unplugging an
electrode during the test); they only run with ``--run-interactive``.
"""

import os

import pytest

PORT_ENV_VAR = "PYSCIENCEMODE_PORT"


def pytest_addoption(parser):
    group = parser.getgroup("pysciencemode")
    group.addoption(
        "--port",
        action="store",
        default=None,
        help=f"Serial port of the connected stimulator (e.g. COM4, /dev/ttyUSB0). "
        f"Can also be set with the {PORT_ENV_VAR} environment variable. "
        f"Hardware tests are skipped when no port is given.",
    )
    group.addoption(
        "--run-interactive",
        action="store_true",
        default=False,
        help="Also run hardware tests that require manual actions (e.g. removing an electrode).",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "hardware: test requires a stimulator connected on --port"
    )
    config.addinivalue_line(
        "markers",
        "interactive: hardware test requiring manual actions (enable with --run-interactive)",
    )
    config.addinivalue_line("markers", "p24: test targets the P24 stimulator")
    config.addinivalue_line("markers", "rehastim2: test targets the Rehastim2 stimulator")


def _get_port(config):
    return config.getoption("--port") or os.environ.get(PORT_ENV_VAR) or None


def pytest_collection_modifyitems(config, items):
    port = _get_port(config)
    run_interactive = config.getoption("--run-interactive")
    skip_hardware = pytest.mark.skip(
        reason=f"hardware test: pass --port or set {PORT_ENV_VAR} to run it"
    )
    skip_interactive = pytest.mark.skip(
        reason="interactive hardware test: pass --run-interactive to run it"
    )
    for item in items:
        if "hardware" in item.keywords and not port:
            item.add_marker(skip_hardware)
        elif "interactive" in item.keywords and not run_interactive:
            item.add_marker(skip_interactive)


@pytest.fixture(scope="session")
def port(pytestconfig):
    """Serial port of the connected stimulator (from --port or PYSCIENCEMODE_PORT)."""
    value = _get_port(pytestconfig)
    if not value:
        pytest.skip(f"no stimulator port: pass --port or set {PORT_ENV_VAR}")
    return value
