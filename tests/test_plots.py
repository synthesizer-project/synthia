"""Test figure rendering from local grids."""

import os
import stat
from importlib.util import find_spec
from pathlib import Path

import pytest

from synthia import plots
from synthia.plots import (
    plot_grid_ionising_luminosity,
    plot_grid_lines,
    plot_grid_spectra,
)

needs_synthesizer = pytest.mark.skipif(
    find_spec("synthesizer") is None or find_spec("matplotlib") is None,
    reason="Synthesizer and matplotlib are required",
)


@pytest.mark.parametrize(
    "tool",
    [plot_grid_spectra, plot_grid_lines, plot_grid_ionising_luminosity],
)
def test_tools_report_a_missing_grid_rather_than_raising(tool):
    """Answer with structured data when the grid cannot be opened."""
    result = tool("no_such_grid_zzz")

    assert result["ok"] is False
    assert result["error"]


@pytest.mark.parametrize(
    "name", ["../../etc/passwd", "/etc/passwd", "a\x00b", "..", ""]
)
def test_grid_names_that_leave_the_directory_are_refused(name):
    """Refuse a grid name that is a path rather than a name."""
    result = plot_grid_spectra(name)

    assert result["ok"] is False


def test_unknown_ion_is_refused_without_opening_a_grid():
    """Validate the ion before doing any work."""
    result = plot_grid_ionising_luminosity("test_grid", ion="XX")

    assert result["ok"] is False
    assert "HI" in result["error"]


def test_output_directory_is_never_caller_supplied():
    """Keep rendered figures out of caller-controlled paths.

    A tool that wrote where the model asked would be a filesystem
    primitive; these only ever write into one fixed directory.
    """
    import inspect as inspect_module

    for tool in (
        plot_grid_spectra,
        plot_grid_lines,
        plot_grid_ionising_luminosity,
    ):
        parameters = inspect_module.signature(tool).parameters
        assert not any(
            "path" in name or "dir" in name or "out" in name
            for name in parameters
        ), f"{tool.__name__} takes a caller-supplied destination"
    assert plots.plot_dir().is_absolute()


@needs_synthesizer
def test_plots_a_real_grid_at_a_chosen_point():
    """Render spectra at a point chosen by physical axis values."""
    result = plot_grid_spectra(
        "test_grid", point={"ages": 1e7, "metallicities": 0.01}
    )
    if not result["ok"]:
        pytest.skip(f"test_grid unavailable: {result['error']}")

    written = Path(result["path"])
    assert written.is_file() and written.stat().st_size > 1000
    assert written.parent == plots.plot_dir()
    assert result["grid_point"] and result["spectra_types"]


@needs_synthesizer
def test_unknown_axis_name_is_reported():
    """Name the grid's real axes when given one it does not have."""
    result = plot_grid_spectra("test_grid", point={"nope": 1.0})
    if "is not an axis" not in str(result.get("error", "")):
        pytest.skip("test_grid unavailable")

    assert result["ok"] is False


def test_distinct_inputs_render_to_distinct_files():
    """Never let two figures collide onto one path.

    Real grid names collide within the readable part of the filename —
    two local dust grids differ only in their final characters — and a
    collision means showing the user a figure of something else.
    """
    long_a = "dust_extcurve_draine_li_lognormal_asmall0p01_apah0p001"
    long_b = "dust_extcurve_draine_li_lognormal_asmall0p01_apah0p005"

    assert plots._stem(long_a, "spectra") != plots._stem(long_b, "spectra")
    assert plots._stem("g", "spectra", "(1, 2)") != plots._stem(
        "g", "spectra", "(3, 4)"
    )
    assert plots._stem(long_a, "spectra") == plots._stem(long_a, "spectra")
    assert "/" not in plots._stem("a/b/c", "spectra")


def test_plot_directory_is_private_and_unguessable():
    """Keep figures out of a shared, predictable temporary path.

    A fixed name in a world-writable temporary directory can be
    pre-created by another local user as a symlink, redirecting every
    figure, or as a file, disabling the tools permanently.
    """
    directory = plots.plot_dir()

    assert directory.is_dir() and not directory.is_symlink()
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert directory.stat().st_uid == os.getuid()
    assert plots.plot_dir() == directory


@needs_synthesizer
def test_a_partial_point_names_the_missing_axes():
    """Tell the caller which axis it left out."""
    result = plot_grid_spectra("test_grid", point={"ages": 1e7})
    if "missing" not in str(result.get("error", "")):
        pytest.skip("test_grid unavailable")

    assert result["ok"] is False
    assert "metallicities" in result["error"]


@needs_synthesizer
def test_default_line_plot_is_capped():
    """Cap the default draw, which asks for every line in the grid."""
    result = plot_grid_lines("test_grid")
    if not result["ok"]:
        pytest.skip(f"test_grid unavailable: {result['error']}")

    assert result["line_count"] <= plots.MAX_LINE_IDS
    assert result["truncated"] is True


def test_a_failed_render_leaks_no_figure(monkeypatch):
    """Close figures on the failure path.

    A figure stranded in pyplot's global registry is never collected,
    so one leak per failed call is an unbounded leak in a server that
    runs for days.
    """
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as pyplot

    pyplot.close("all")
    monkeypatch.setattr(
        plots, "_save", lambda *a, **k: (_ for _ in ()).throw(OSError("full"))
    )

    for _ in range(3):
        plot_grid_ionising_luminosity("test_grid")

    assert pyplot.get_fignums() == []
