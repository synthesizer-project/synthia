"""Render standard Synthesizer figures from a local grid.

These tools exist so an agent can show a user a figure without writing
and running a plotting script. Every figure is built by Synthia itself
from declarative arguments naming a local grid and a point in it, so no
model-supplied code is ever executed and no model-supplied path is ever
written to. Figures are written to one directory under the system
temporary directory and the tools return the path.

Synthesizer's own plotting helpers do the drawing, so the figures match
what the package produces natively rather than a reimplementation.
"""

import tempfile
from hashlib import sha256
from math import isfinite
from pathlib import Path

from synthia._safety import clean_text, describe
from synthia.grids import _grid_dir, _grid_path, _grid_stem

#: Created on first use. A fixed name in a shared temporary directory
#: could be pre-created by another local user as a symlink (redirecting
#: every figure), as a file or unwritable directory (disabling the tools
#: permanently), or simply read. ``mkdtemp`` refuses an existing name and
#: creates mode 0700, which closes all four.
_plot_dir: Path | None = None


def plot_dir() -> Path:
    """Return this process's private figure directory, creating it once.

    Returns:
        An absolute path, owned by this user and not world-readable.
    """
    global _plot_dir
    if _plot_dir is None:
        _plot_dir = Path(tempfile.mkdtemp(prefix="synthia-plots-"))
    return _plot_dir


#: Ions accepted by the ionising-luminosity surface plot.
IONS = ("HI", "HeII")

MAX_GRID_BYTES = 2 * 1024**3
MAX_SPECTRA_TYPES = 6
MAX_LINE_IDS = 40


def _pyplot():
    """Import pyplot with a non-interactive backend.

    Returns:
        The ``matplotlib.pyplot`` module.

    Raises:
        ImportError: If matplotlib is unavailable.
    """
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as pyplot

    return pyplot


def _save(figure, name: str) -> str:
    """Write a figure into the plot directory and close it.

    Args:
        figure: A matplotlib figure.
        name: Stem for the file, already sanitised.

    Returns:
        The absolute path written.
    """
    path = plot_dir() / f"{name}.png"
    figure.savefig(path, dpi=150, bbox_inches="tight")
    _pyplot().close(figure)
    return str(path)


def _stem(grid_name: str, suffix: str, key: str = "") -> str:
    """Build a safe, collision-free file stem.

    The readable part is truncated, and real grid names do collide
    within that limit: two dust grids differing only in their final
    characters would otherwise render over one another. Everything that
    changes the figure is therefore folded into a short digest, so
    distinct inputs get distinct files while repeating a call reuses
    the same path.

    Args:
        grid_name: Grid name as supplied by the caller.
        suffix: Short label for the kind of figure.
        key: Any further arguments that change the figure.

    Returns:
        A file stem containing no path separators.
    """
    cleaned = clean_text(grid_name)
    safe = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in cleaned
    )
    digest = sha256(f"{cleaned}\x00{suffix}\x00{key}".encode()).hexdigest()
    return f"{safe[:48]}-{suffix}-{digest[:8]}"


def _load_grid(grid_name: str, **kwargs):
    """Open a local grid by name, containment-checked.

    Args:
        grid_name: Grid name, with or without a suffix.
        **kwargs: Passed to ``Grid``.

    Returns:
        A ``(grid, error)`` pair; exactly one is ``None``.
    """
    directory, _, failure = _grid_dir()
    if failure is not None:
        return None, failure
    try:
        path = _grid_path(directory, _grid_stem(grid_name))
    except (ValueError, OSError) as error:
        return None, {"ok": False, "error": describe(error)}
    if not path.is_file():
        return None, {"ok": False, "error": f"no grid named {path.stem!r}"}
    size = path.stat().st_size
    if size > MAX_GRID_BYTES:
        return None, {
            "ok": False,
            "error": (
                f"grid is too large to plot ({size} bytes, limit "
                f"{MAX_GRID_BYTES}); inspect_local_grid reads no arrays"
            ),
        }
    from synthesizer.grid import Grid

    return Grid(path.stem, grid_dir=str(directory), **kwargs), None


def _grid_point(grid, point: dict[str, float] | None):
    """Map axis values onto the nearest grid point.

    Args:
        grid: An open ``Grid``.
        point: Axis name to value, in that axis's own units. Unknown
            axis names are rejected. ``None`` selects the grid centre.

    Returns:
        A tuple of integer indices.

    Raises:
        ValueError: If an axis name is not one of the grid's axes.
    """
    if not point:
        return tuple(length // 2 for length in grid.shape[: grid.naxes])
    # Name a wrong axis before reporting missing ones: a typo would
    # otherwise be reported only as "every axis is missing".
    unknown = [axis for axis in point if axis not in grid.axes]
    if unknown:
        raise ValueError(
            f"{unknown[0]!r} is not an axis of this grid; axes are "
            f"{', '.join(grid.axes)}"
        )
    missing = [axis for axis in grid.axes if axis not in point]
    if missing:
        raise ValueError(
            "point must give a value for every axis; missing "
            f"{', '.join(missing)}"
        )
    selection = {}
    for axis, value in point.items():
        if not isfinite(float(value)):
            raise ValueError(f"{axis} value must be a finite number")
        values = getattr(grid, axis)
        units = getattr(values, "units", None)
        selection[axis] = float(value) * units if units else float(value)
    return tuple(int(index) for index in grid.get_grid_point(**selection))


def _luminous_range(seds) -> tuple[float, float]:
    """Bound the wavelengths carrying essentially all the luminosity.

    Grid wavelength axes can span many decades, so drawing the full
    range squashes the interesting part into a sliver. This trims to the
    central 99.8% of the summed luminosity.

    Args:
        seds: Mapping of label to ``Sed``.

    Returns:
        A ``(low, high)`` pair in the Sed's own wavelength units.
    """
    import numpy

    first = next(iter(seds.values()))
    lam = numpy.asarray(first._lam, dtype=float)
    total = numpy.zeros_like(lam)
    for sed in seds.values():
        total += numpy.nan_to_num(numpy.asarray(sed._lnu, dtype=float))
    # Bolometric luminosity is the integral of L_nu over frequency, so
    # weight by L_nu / lam**2 * dlam. Summing L_nu directly over a
    # log-spaced axis over-weights the long-wavelength tail and the
    # range comes back almost as wide as the axis itself.
    with numpy.errstate(divide="ignore", invalid="ignore"):
        density = numpy.nan_to_num(
            total / numpy.square(lam) * numpy.gradient(lam)
        )
    weight = numpy.cumsum(numpy.clip(density, 0.0, None))
    if weight[-1] <= 0:
        return float(lam[0]), float(lam[-1])
    weight /= weight[-1]
    low, high = numpy.searchsorted(weight, (0.001, 0.999))
    low = min(low, len(lam) - 2)
    high = min(max(high, low + 1), len(lam) - 1)
    return float(lam[low]), float(lam[high])


def plot_grid_spectra(
    grid_name: str,
    spectra_types: list[str] | None = None,
    point: dict[str, float] | None = None,
    wavelength_range: list[float] | None = None,
) -> dict[str, object]:
    """Plot a local grid's spectra at one grid point.

    Renders the spectra a grid holds at a chosen point, so the shape of
    the grid's output can be seen without writing a script. Loading
    spectra reads the full arrays, so this is slower than
    ``inspect_local_grid``, and importing Synthesizer creates its data
    directories on first use.

    Args:
        grid_name: Grid name, with or without a file suffix.
        spectra_types: Spectra to draw, defaulting to every spectrum the
            grid provides, capped at six.
        point: Axis name to value, each in that axis's own units, for
            example ``{"ages": 1e7, "metallicities": 0.01}``. Every axis
            must be given. Defaults to the centre of the grid.
        wavelength_range: ``[low, high]`` in the grid's wavelength
            units. Defaults to the range carrying essentially all the
            luminosity, because a grid's full axis spans many decades
            and drawing all of it hides the interesting part.

    Returns:
        A mapping with ``ok``, the written ``path``, the ``grid_point``
        indices used, the ``spectra_types`` drawn, the
        ``wavelength_range`` shown, and the ``axes`` values at that
        point. On failure ``ok`` is ``False`` and
        ``error`` explains why.
    """
    requested = list(spectra_types or [])[:MAX_SPECTRA_TYPES]
    # Reading only the requested spectra would be cheaper, but
    # Synthesizer derives nebular_continuum from nebular and linecont
    # unconditionally, so a subset excluding either raises inside
    # Grid.__init__. The size guard in _load_grid is the real budget.
    grid, failure = _load_grid(grid_name, ignore_lines=True)
    if failure is not None:
        return failure
    try:
        _pyplot()
        from synthesizer.emissions import plot_spectra

        available = list(grid.available_spectra)
        wanted = [
            name for name in (requested or available) if name in available
        ][:MAX_SPECTRA_TYPES]
        if not wanted:
            return {
                "ok": False,
                "error": "none of the requested spectra are in this grid",
                "available_spectra": available,
            }
        indices = _grid_point(grid, point)
        seds = {
            name: grid.get_sed_at_grid_point(indices, spectra_type=name)
            for name in wanted
        }
        limits = (
            tuple(float(value) for value in wavelength_range[:2])
            if wavelength_range
            else _luminous_range(seds)
        )
        figure, _ = plot_spectra(seds, show=False, xlimits=limits)
        path = _save(
            figure,
            _stem(grid_name, "spectra", f"{indices}{wanted}"),
        )
    except Exception as error:  # noqa: BLE001 - reported, never raised
        _pyplot().close("all")
        return {"ok": False, "error": describe(error)}
    return {
        "ok": True,
        "path": path,
        "grid_point": list(indices),
        "spectra_types": wanted,
        "wavelength_range": list(limits),
        "axes": {
            axis: float(getattr(grid, axis)[index])
            for axis, index in zip(grid.axes, indices)
        },
    }


def plot_grid_lines(
    grid_name: str,
    point: dict[str, float] | None = None,
    line_ids: list[str] | None = None,
) -> dict[str, object]:
    """Plot the emission lines a local grid holds at one grid point.

    Args:
        grid_name: Grid name, with or without a file suffix.
        point: Axis name to value in that axis's own units, defaulting
            to the centre of the grid.
        line_ids: Lines to draw, for example ``["H 1 4861.32A"]``,
            capped at forty. Defaults to every line in the grid.

    Returns:
        A mapping with ``ok``, the written ``path``, the ``grid_point``
        used and the number of lines drawn, or ``ok`` false with an
        ``error``.
    """
    grid, failure = _load_grid(grid_name, ignore_spectra=True)
    if failure is not None:
        return failure
    try:
        _pyplot()
        if not grid.has_lines:
            return {"ok": False, "error": "this grid holds no lines"}
        indices = _grid_point(grid, point)
        lines = grid.get_lines(grid_point=indices)
        if line_ids:
            wanted = [name for name in line_ids if name in lines.line_ids]
            if not wanted:
                return {
                    "ok": False,
                    "error": "none of the requested lines are in this grid",
                }
        else:
            wanted = list(lines.line_ids)
        truncated = len(wanted) > MAX_LINE_IDS
        lines = lines[wanted[:MAX_LINE_IDS]]
        # A line at the axis limit is clipped to invisibility, so a
        # two-line request can render an empty-looking figure while the
        # tool reports success. Pad the axis around the drawn lines.
        drawn = sorted(float(value) for value in lines._lam)
        pad = max((drawn[-1] - drawn[0]) * 0.05, drawn[0] * 0.05, 1.0)
        figure, _ = lines.plot_lines(
            show=False, xlimits=(drawn[0] - pad, drawn[-1] + pad)
        )
        path = _save(
            figure,
            _stem(grid_name, "lines", f"{indices}{line_ids}"),
        )
    except Exception as error:  # noqa: BLE001 - reported, never raised
        _pyplot().close("all")
        return {"ok": False, "error": describe(error)}
    return {
        "ok": True,
        "path": path,
        "grid_point": list(indices),
        "line_count": len(lines.line_ids),
        "truncated": truncated,
    }


def plot_grid_ionising_luminosity(
    grid_name: str, ion: str = "HI"
) -> dict[str, object]:
    """Plot a grid's specific ionising luminosity over its axes.

    This is the standard diagnostic for whether a grid covers the
    ionising output a study needs.

    Args:
        grid_name: Grid name, with or without a file suffix.
        ion: Ion to plot, one of ``HI`` or ``HeII``.

    Returns:
        A mapping with ``ok``, the written ``path`` and the ``ion``
        plotted, or ``ok`` false with an ``error``.
    """
    if ion not in IONS:
        return {
            "ok": False,
            "error": f"ion must be one of {', '.join(IONS)}",
        }
    grid, failure = _load_grid(grid_name, ignore_spectra=True)
    if failure is not None:
        return failure
    try:
        _pyplot()
        # The helper indexes age and metallicity directly, so a grid
        # built on other axes (a dust extinction grid, say) would fail
        # deep inside matplotlib with an unhelpful AttributeError.
        required = {"ages", "metallicities"}
        if not required.issubset(set(grid.axes)):
            return {
                "ok": False,
                "error": (
                    "this plot needs age and metallicity axes; this "
                    f"grid has {', '.join(grid.axes)}"
                ),
            }
        figure = grid.plot_specific_ionising_lum(ion=ion)[0]
        path = _save(figure, _stem(grid_name, f"ionising-{ion}"))
    except Exception as error:  # noqa: BLE001 - reported, never raised
        _pyplot().close("all")
        return {"ok": False, "error": describe(error)}
    return {"ok": True, "path": path, "ion": ion}
