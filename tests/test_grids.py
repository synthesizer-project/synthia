"""Test local grid discovery and inspection."""

import json
import sys
from importlib.util import find_spec

import pytest

from synthia.grids import (
    _axis,
    _grid_path,
    _grid_stem,
    _structure,
    inspect_local_grid,
    list_local_grids,
)

HAS_SYNTHESIZER = find_spec("synthesizer") is not None

needs_synthesizer = pytest.mark.skipif(
    not HAS_SYNTHESIZER, reason="Synthesizer is not installed"
)
without_synthesizer = pytest.mark.skipif(
    HAS_SYNTHESIZER, reason="Synthesizer is installed"
)


@without_synthesizer
def test_tools_report_missing_synthesizer_without_raising():
    """Return a structured error when Synthesizer is unavailable."""
    for result in (list_local_grids(), inspect_local_grid("test_grid")):
        assert result["ok"] is False
        assert result["missing"] == "cosmos-synthesizer"
        assert result["error"]


def test_broken_synthesizer_import_is_reported(tmp_path, monkeypatch):
    """Report an installed but unusable Synthesizer as a plain error."""
    package = tmp_path / "synthesizer"
    package.mkdir()
    (package / "__init__.py").write_text("raise RuntimeError('broken')\n")
    for name in list(sys.modules):
        if name == "synthesizer" or name.startswith("synthesizer."):
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.syspath_prepend(str(tmp_path))

    result = list_local_grids()

    assert result["ok"] is False
    assert "broken" in result["error"]
    assert "missing" not in result


@pytest.mark.parametrize(
    "name",
    [
        "../../etc/passwd",
        "/etc/passwd",
        "a\x00b",
        "..",
        ".",
        "a/../..",
        "",
        ".hdf5",
        "x" * 300,
    ],
)
def test_grid_names_that_leave_the_directory_are_refused(tmp_path, name):
    """Refuse grid names that are paths rather than names.

    Resolution goes through ``_grid_stem`` then ``_grid_path``; both must
    be exercised, because the stem rules and the containment check catch
    different inputs.
    """
    with pytest.raises(ValueError):
        _grid_path(tmp_path, _grid_stem(name))


def test_grid_path_rejects_a_symlinked_grid(tmp_path):
    """Refuse a grid file that is a symbolic link, as listing does."""
    grid_dir = tmp_path / "grids"
    grid_dir.mkdir()
    outside = tmp_path / "private.hdf5"
    outside.write_text('{"api_key": "sk-SECRET-OUTSIDE-GRID-DIR"}')
    (grid_dir / "escape.hdf5").symlink_to(outside)

    with pytest.raises(ValueError):
        _grid_path(grid_dir, "escape")


def test_grid_path_never_leaves_the_grid_directory(tmp_path):
    """Keep every candidate inside the grid directory."""
    grid_dir = tmp_path / "grids"
    grid_dir.mkdir()
    sibling = tmp_path / "grids.hdf5"
    sibling.write_text("sibling")

    for name in [".", "./.", " . ", "x"]:
        resolved = _grid_path(grid_dir, name.strip())
        assert resolved != sibling.resolve()
        assert resolved.is_relative_to(grid_dir.resolve())


@pytest.mark.parametrize("name", ["", "  ", ".hdf5", ".h5", "a" * 300])
def test_grid_stem_rejects_unusable_names(name):
    """Refuse names that are empty or too long to be a filename."""
    with pytest.raises(ValueError):
        _grid_stem(name)


def test_grid_stem_strips_suffixes():
    """Strip an HDF5 suffix so the stem can be passed to ``Grid``."""
    assert _grid_stem("test_grid.hdf5") == "test_grid"
    assert _grid_stem("test_grid.h5") == "test_grid"
    assert _grid_stem("test_grid") == "test_grid"


@pytest.mark.parametrize(
    "name", ["../../etc/passwd", "/etc/passwd", "", "a" * 300, "."]
)
def test_inspect_local_grid_rejects_bad_names(name):
    """Return an error, not an exception, for a hostile grid name."""
    result = inspect_local_grid(name)

    assert result["ok"] is False
    assert result["error"]


def test_axis_drops_values_that_are_not_finite():
    """Report NaN and infinite axis bounds as null, not invalid JSON."""
    axis = _axis("ages", "yr", [float("nan"), float("inf")])

    assert axis["min"] is None
    assert axis["max"] is None
    assert json.dumps(axis, allow_nan=False)


def _walk(path):
    """Describe a fixture file the way ``inspect_local_grid`` does.

    Args:
        path: Path of the HDF5 file to walk.

    Returns:
        The structure mapping and its JSON rendering.
    """
    h5py = pytest.importorskip("h5py")
    with h5py.File(path, "r", locking=False) as handle:
        structure = _structure(handle, h5py)
    return structure, json.dumps(structure, allow_nan=False)


def test_external_link_is_reported_but_not_followed(tmp_path):
    """Report an external link without leaking the file it points at."""
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "linked.hdf5"
    with h5py.File(path, "w") as handle:
        handle["leak"] = h5py.ExternalLink("/etc/passwd", "/")
        handle["soft"] = h5py.SoftLink("/missing")

    structure, dumped = _walk(path)
    kinds = {entry["path"]: entry["kind"] for entry in structure["entries"]}

    assert kinds["/leak"] == "external_link"
    assert kinds["/soft"] == "soft_link"
    assert all(
        entry.get("followed") is False
        for entry in structure["entries"]
        if entry["kind"].endswith("_link")
    )
    assert "root:" not in dumped
    assert "/bin/" not in dumped


def test_oversized_attribute_is_omitted(tmp_path):
    """Omit a huge attribute and keep the response small."""
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "attrs.hdf5"
    with h5py.File(path, "w") as handle:
        handle.attrs["huge"] = "x" * (5 * 1024 * 1024)
        handle.attrs["small"] = "keep me"

    structure, dumped = _walk(path)
    root = structure["entries"][0]

    assert "huge" in structure["omitted_attributes"]
    assert root["attributes"]["small"] == "keep me"
    assert "huge" not in root["attributes"]
    assert len(dumped) < 8192


def test_many_attributes_cannot_flood_the_response(tmp_path):
    """Cap both the reported and the omitted attribute names."""
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "flood.hdf5"
    with h5py.File(path, "w") as handle:
        for index in range(400):
            handle.attrs[f"attribute_number_{index:04d}"] = "y" * 200

    structure, dumped = _walk(path)

    assert len(structure["entries"][0]["attributes"]) <= 64
    assert len(structure["omitted_attributes"]) <= 64
    assert structure["omitted_attribute_count"] >= 336
    assert len(dumped) < 32768


def test_dataset_values_are_never_read(tmp_path):
    """Report dataset shape and dtype but none of its values."""
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "big.hdf5"
    with h5py.File(path, "w") as handle:
        group = handle.create_group("spectra")
        group.create_dataset("wavelength", data=[123456.789] * 10000)

    structure, dumped = _walk(path)
    dataset = next(
        entry
        for entry in structure["entries"]
        if entry["path"] == "/spectra/wavelength"
    )

    assert dataset["kind"] == "dataset"
    assert dataset["shape"] == [10000]
    assert dataset["size"] == 10000
    assert dataset["dtype"]
    assert "values" not in dataset
    assert "123456.789" not in dumped
    assert len(dumped) < 8192


def test_committed_datatype_does_not_break_the_walk(tmp_path):
    """Describe a node that is neither a group nor a dataset."""
    h5py = pytest.importorskip("h5py")
    numpy = pytest.importorskip("numpy")
    path = tmp_path / "datatype.hdf5"
    with h5py.File(path, "w") as handle:
        handle["committed"] = numpy.dtype("i8")

    structure, _ = _walk(path)
    entry = next(
        item for item in structure["entries"] if item["path"] == "/committed"
    )

    assert entry["kind"] == "datatype"
    assert "shape" not in entry


def test_line_identifiers_are_reported(tmp_path):
    """Name a grid's emission lines so an agent can search for one."""
    h5py = pytest.importorskip("h5py")
    numpy = pytest.importorskip("numpy")
    path = tmp_path / "lines.hdf5"
    with h5py.File(path, "w") as handle:
        lines = handle.create_group("lines")
        lines.create_dataset(
            "id",
            data=numpy.array(["H 1 4861.32A", "O 3 5006.84A"], dtype=object),
            dtype=h5py.string_dtype(),
        )
        lines.create_dataset("luminosity", data=[[1.0, 2.0]] * 4)

    structure, dumped = _walk(path)
    ids = next(
        item for item in structure["entries"] if item["path"] == "/lines/id"
    )

    assert ids["values"] == ["H 1 4861.32A", "O 3 5006.84A"]
    assert ids["values_truncated"] is False
    assert "b'" not in dumped
    luminosity = next(
        item
        for item in structure["entries"]
        if item["path"] == "/lines/luminosity"
    )
    assert "values" not in luminosity


def test_oversized_identifier_dataset_is_not_read(tmp_path):
    """Refuse to read an identifier dataset that is suspiciously large."""
    h5py = pytest.importorskip("h5py")
    numpy = pytest.importorskip("numpy")
    path = tmp_path / "huge_ids.hdf5"
    with h5py.File(path, "w") as handle:
        lines = handle.create_group("lines")
        lines.create_dataset(
            "id",
            data=numpy.array(["smuggled"] * 5000, dtype=object),
            dtype=h5py.string_dtype(),
        )

    structure, dumped = _walk(path)

    assert "smuggled" not in dumped
    assert all("values" not in entry for entry in structure["entries"])


@needs_synthesizer
def test_list_local_grids_reports_the_grid_directory():
    """Report the resolved grid directory and any grids in it."""
    result = list_local_grids()

    assert result["ok"] is True
    assert result["grid_dir"]
    assert isinstance(result["grids"], list)
    assert isinstance(result["truncated"], bool)
    for grid in result["grids"]:
        assert grid["name"] and grid["filename"]
        assert grid["size_bytes"] >= 0


@needs_synthesizer
def test_inspect_local_grid_describes_a_real_grid():
    """Describe an installed grid's axes and contents."""
    listed = list_local_grids()
    if not listed["grids"]:
        pytest.skip("no grids are installed")

    result = inspect_local_grid(listed["grids"][0]["name"])

    assert result["ok"] is True
    assert result["synthesizer_version"]
    assert result["size_bytes"] > 0
    assert "metadata_error" not in result
    assert result["axes"]
    for axis in result["axes"]:
        assert axis["name"]
        assert "units" in axis
        assert axis["size"] > 0
    assert "structure_error" not in result
    assert result["structure"]["entries"]
    assert json.dumps(result, allow_nan=False)
