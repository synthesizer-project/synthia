"""Shared test configuration.

Importing Synthesizer runs ``synth_initialise()``, which creates data
directories and writes ``default_units.yml``. Every Synthesizer
directory is redirected into a temporary tree so running the tests never
mutates the developer's real Synthesizer installation.
"""

import os
from pathlib import Path

import pytest

SYNTHESIZER_DIR_VARS = (
    "SYNTHESIZER_DIR",
    "SYNTHESIZER_DATA_DIR",
    "SYNTHESIZER_GRID_DIR",
    "SYNTHESIZER_TEST_DATA_DIR",
    "SYNTHESIZER_INSTRUMENT_CACHE",
    "SYNTHESIZER_SVO_FILTER_CACHE",
)


def _real_grid_dir():
    """Locate the developer's real grid directory, without importing.

    Grids are only ever read, so keeping the real directory preserves
    the tests that inspect an actual grid while every writable
    directory is still redirected.
    """
    existing = os.environ.get("SYNTHESIZER_GRID_DIR")
    if existing:
        return existing
    try:
        from platformdirs import user_data_dir
    except ImportError:
        return None
    grids = Path(user_data_dir("Synthesizer")) / "grids"
    return str(grids) if grids.is_dir() else None


@pytest.fixture(scope="session", autouse=True)
def _isolate_synthesizer_directories(tmp_path_factory):
    """Point Synthesizer's writable directories at a temporary tree."""
    base = tmp_path_factory.mktemp("synthesizer-home")
    previous = {name: os.environ.get(name) for name in SYNTHESIZER_DIR_VARS}
    grid_dir = _real_grid_dir()
    os.environ["SYNTHESIZER_DIR"] = str(base)
    for name in SYNTHESIZER_DIR_VARS[1:]:
        os.environ.pop(name, None)
    if grid_dir is not None:
        os.environ["SYNTHESIZER_GRID_DIR"] = grid_dir

    yield base

    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
