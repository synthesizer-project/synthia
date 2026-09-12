"""Test the Syndex catalogue tools against a stubbed transport.

No test here touches the network: ``urlopen`` is replaced in every one,
so a regression that bypasses the stub fails rather than quietly
reaching the live service.
"""

import json
import urllib.error

import pytest

from synthia import catalogue
from synthia.catalogue import (
    API_BASES,
    _dataset_name,
    describe_catalogue_dataset,
    list_catalogue_releases,
    search_catalogue,
)


class _Response:
    """The subset of an ``http.client`` response ``_fetch`` uses."""

    def __init__(self, body):
        self._body = body

    def read(self, amount):
        return self._body[:amount]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _stub(monkeypatch, payload, *, body=None, error=None):
    """Replace ``urlopen`` and record the urls that were requested."""
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append(request.full_url)
        if error is not None:
            raise error
        raw = body
        if raw is None:
            raw = json.dumps(payload).encode("utf-8")
        return _Response(raw)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return calls


DATASETS = {
    "datasets": [
        {
            "name": "bpass-2-2-1-cloudy-sps",
            "display_name": "BPASS 2.2.1 Cloudy SPS grid",
            "description": "Production photoionised BPASS grid.",
            "data_type": "grid",
            "is_test": False,
            "is_ci": False,
            "is_recommended": True,
            "release_id": 9,
            "size_bytes": 203126664,
            "has_spectra": True,
            "has_lines": True,
        },
        {
            "name": "draine-li-dust-emission-mw-3p1",
            "display_name": "Draine & Li (2007) MW 3.1 dust emission grid",
            "description": "Production dust emission grid.",
            "data_type": "dust_grid",
            "is_test": False,
            "is_recommended": False,
            "release_id": 5,
            "size_bytes": 139567192,
            "has_spectra": True,
            "has_lines": False,
        },
    ],
    "cursor": None,
}

RELEASE = {
    "release_id": 9,
    "published_at": "2026-09-06T12:00:00Z",
    "deprecated_at": None,
    "known_bug": True,
    "known_bug_description": "Superseded: star fraction data was absent.",
    "synthesizer_min_version": None,
    "synthesizer_max_version": None,
    "file": {
        "filename": "bpass-2.2.1-bin_chabrier03.hdf5",
        "format": "hdf5",
        "size_bytes": 203126664,
        "sha256": "e47f0076370da3a5",
    },
    "download_url": "https://data.synthesizer-project.org/v1/releases/9/download",
    "grid": {
        "grid_type": "sps",
        "emission_type": "photoionised",
        "model_name": "BPASS",
        "model_version": "2.2.1",
        "model_parameters": {"imf_type": "chabrier03"},
        "photoionisation_code": "Cloudy",
        "photoionisation_code_version": "23.01",
        "available_spectra": ["incident", "nebular", "transmitted"],
        "available_lines": [f"O {index} 1031.91A" for index in range(400)],
        "wavelength_min": 0.0001,
        "wavelength_max": 2.9e11,
        "wavelength_units": "Å",
        "incident_release_id": 3,
        "axes": [
            {
                "axis_index": 0,
                "name": "ages",
                "units": "yr",
                "scale": "log",
                "count": 51,
                "minimum": 1e6,
                "maximum": 1e11,
                "values": list(range(51)),
            }
        ],
    },
    "instrument": None,
    "citations": [
        {
            "bibcode": "2017PASA...34...58E",
            "doi": "10.1017/pasa.2017.51",
            "authors": "Eldridge, J. J.; Stanway, E. R.",
            "title": "Binary Population and Spectral Synthesis",
            "year": 2017,
            "journal": "PASA",
            "bibtex": "@ARTICLE{...}" * 500,
        }
    ],
}

DATASET = {
    "name": "bpass-2-2-1-cloudy-sps",
    "display_name": "BPASS 2.2.1 Cloudy SPS grid",
    "description": "Production photoionised BPASS grid.",
    "data_type": "grid",
    "is_test": False,
    "is_recommended": True,
    "licence": None,
    "current_release": RELEASE,
}


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        "../../etc/passwd",
        "/etc/passwd",
        "a\x00b",
        "name with spaces",
        "name?query=1",
        "a" * 300,
    ],
)
def test_names_that_are_not_catalogue_names_are_refused(monkeypatch, name):
    """Refuse a name before it can reach a url.

    Names are interpolated into an API path, so anything outside the
    catalogue's own character set is rejected rather than escaped.
    """
    calls = _stub(monkeypatch, DATASET)

    for tool in (describe_catalogue_dataset, list_catalogue_releases):
        result = tool(name)
        assert result["ok"] is False
        assert result["error"]
    assert calls == [], "a rejected name still reached the network"
    with pytest.raises(ValueError):
        _dataset_name(name)


def test_search_returns_compact_rows_with_a_download_command(monkeypatch):
    """Return the fields needed to choose a dataset, and nothing more."""
    _stub(monkeypatch, DATASETS)

    result = search_catalogue()

    assert result["ok"] is True
    assert result["matched"] == 2
    assert result["truncated"] is False
    first = result["datasets"][0]
    assert first["name"] == "bpass-2-2-1-cloudy-sps"
    assert first["has_lines"] is True
    assert first["download_command"] == (
        "synthesizer-download --dataset bpass-2-2-1-cloudy-sps"
    )
    assert result["content_is_untrusted"] is True


def test_search_filters_on_every_query_term(monkeypatch):
    """Match a dataset only when all of the query's terms appear."""
    _stub(monkeypatch, DATASETS)

    assert search_catalogue(query="dust emission")["matched"] == 1
    assert search_catalogue(query="bpass cloudy")["matched"] == 1
    assert search_catalogue(query="bpass dust")["matched"] == 0
    assert search_catalogue(query="GRID")["matched"] == 2


def test_search_pushes_filters_to_the_service(monkeypatch):
    """Send the filters the API implements rather than fetching all rows."""
    calls = _stub(monkeypatch, DATASETS)

    search_catalogue(data_type="grid", has_lines=True, is_test=False)

    assert "data_type=grid" in calls[0]
    assert "has_lines=true" in calls[0]
    assert "is_test=false" in calls[0]


def test_search_caps_how_many_datasets_it_returns(monkeypatch):
    """Cap the response and say that it was capped."""
    _stub(monkeypatch, DATASETS)

    result = search_catalogue(limit=1)

    assert len(result["datasets"]) == 1
    assert result["matched"] == 2
    assert result["truncated"] is True


def test_describe_compacts_a_grid_release(monkeypatch):
    """Report a grid's extent, contents and citation, not its values."""
    _stub(monkeypatch, DATASET)

    result = describe_catalogue_dataset("bpass-2-2-1-cloudy-sps")

    release = result["current_release"]
    grid = release["grid"]
    assert result["ok"] is True
    assert grid["axes"] == [
        {
            "name": "ages",
            "units": "yr",
            "scale": "log",
            "count": 51,
            "minimum": 1e6,
            "maximum": 1e11,
        }
    ]
    assert grid["lines"]["count"] == 400
    assert grid["lines"]["truncated"] is True
    assert len(grid["lines"]["ids"]) == catalogue.MAX_LINE_IDS
    assert grid["spectra"] == ["incident", "nebular", "transmitted"]
    assert release["file"]["sha256"] == "e47f0076370da3a5"
    assert release["known_bug_description"].startswith("Superseded")
    assert release["download_command"] == (
        "synthesizer-download --dataset bpass-2-2-1-cloudy-sps --release 9"
    )
    assert release["citations"][0]["bibcode"] == "2017PASA...34...58E"


def test_describe_response_stays_small(monkeypatch):
    """Keep a full production grid's metadata affordable for an agent.

    The raw release carries every axis value and a BibTeX body per
    citation; neither is worth an agent's context.
    """
    _stub(monkeypatch, DATASET)

    result = describe_catalogue_dataset("bpass-2-2-1-cloudy-sps")

    assert len(json.dumps(result)) < 24 * 1024


def test_describe_handles_a_dataset_with_no_release(monkeypatch):
    """Report a dataset that has nothing published as a success."""
    _stub(monkeypatch, {**DATASET, "current_release": None})

    result = describe_catalogue_dataset("bpass-2-2-1-cloudy-sps")

    assert result["ok"] is True
    assert result["current_release"] is None


def test_releases_are_listed_with_a_pinned_command(monkeypatch):
    """Name each release's version bounds, bug flag and download."""
    _stub(
        monkeypatch,
        {
            "dataset": "bpass-2-2-1-cloudy-sps",
            "data_type": "grid",
            "releases": [{**RELEASE, "is_current": True}, "not a release"],
        },
    )

    result = list_catalogue_releases("bpass-2-2-1-cloudy-sps")

    assert result["ok"] is True
    assert len(result["releases"]) == 1
    assert result["releases"][0]["is_current"] is True
    assert result["releases"][0]["download_command"].endswith("--release 9")


def test_only_a_grid_gets_a_bare_dataset_download(monkeypatch):
    """Refuse to hand over a command that files data in the wrong place.

    ``synthesizer-download --dataset`` always installs into the grid
    directory. That is right for a grid and wrong for the instruments,
    caches and simulation data the catalogue also holds, so those get a
    note instead of a command a user would paste unchanged.
    """
    _stub(monkeypatch, {**DATASET, "data_type": "instrument"})
    release = describe_catalogue_dataset("euclid-nisp")["current_release"]
    assert release["download_command"] is None
    assert "--instruments" in release["download_note"]
    assert "grid directory" in release["download_note"]

    _stub(monkeypatch, {**DATASET, "data_type": "simulation_data"})
    release = describe_catalogue_dataset("camels-snapshot")["current_release"]
    assert "--destination" in release["download_command"]
    assert "simulation_data" in release["download_note"]

    _stub(monkeypatch, DATASET)
    release = describe_catalogue_dataset("bpass")["current_release"]
    assert release["download_command"].endswith("--release 9")
    assert "download_note" not in release


def test_a_listing_row_routes_by_its_own_type(monkeypatch):
    """Give each row the download route its own data type needs."""
    _stub(
        monkeypatch,
        {
            "datasets": [
                DATASETS["datasets"][0],
                {
                    "name": "euclid-nisp-instrument",
                    "display_name": "Euclid NISP",
                    "data_type": "instrument",
                    "is_test": False,
                    "is_recommended": False,
                    "release_id": 1,
                    "size_bytes": 75288,
                },
            ]
        },
    )

    rows = {row["name"]: row for row in search_catalogue()["datasets"]}

    assert rows["bpass-2-2-1-cloudy-sps"]["download_command"]
    assert rows["euclid-nisp-instrument"]["download_command"] is None
    assert "--instruments" in rows["euclid-nisp-instrument"]["download_note"]


def test_catalogue_text_is_cleaned_and_capped(monkeypatch):
    """Treat catalogue strings as untrusted data, as grid strings are.

    The catalogue publishes what depositors wrote, so an escape sequence
    or an oversized description must not reach the transcript intact.
    """
    _stub(
        monkeypatch,
        {
            **DATASET,
            "display_name": "\x1b[2Jhidden\x00",
            "description": "x" * 50000,
        },
    )

    result = describe_catalogue_dataset("bpass-2-2-1-cloudy-sps")

    assert result["display_name"] == "hidden"
    assert len(result["description"]) <= catalogue.MAX_DESCRIPTION_CHARS + 3


def test_a_rejected_request_is_not_retried_on_the_fallback(monkeypatch):
    """Report a 404 as an answer rather than trying the other host."""
    calls = _stub(
        monkeypatch,
        None,
        error=urllib.error.HTTPError(
            "https://example.invalid", 404, "Not Found", {}, None
        ),
    )

    result = describe_catalogue_dataset("no-such-dataset")

    assert result["ok"] is False
    assert result["status"] == 404
    assert len(calls) == 1


def test_every_host_is_tried_before_giving_up(monkeypatch):
    """Fall back to the second hostname, then report it is unreachable.

    Security products routinely block recently registered domains, which
    is why the service answers on two.
    """
    calls = _stub(monkeypatch, None, error=OSError("blocked"))

    result = search_catalogue()

    assert result["ok"] is False
    assert len(calls) == len(API_BASES)
    assert "could not reach" in result["error"]
    assert "list_local_grids" in result["hint"]


def test_an_oversized_response_is_refused(monkeypatch):
    """Refuse a response too large to be a catalogue answer."""
    _stub(
        monkeypatch,
        None,
        body=b"[" + b" " * (catalogue.MAX_RESPONSE_BYTES + 10),
    )

    result = search_catalogue()

    assert result["ok"] is False
    assert "could not reach" in result["error"]


def test_a_response_that_is_not_an_object_is_refused(monkeypatch):
    """Refuse a payload that is not the mapping the API documents."""
    _stub(monkeypatch, None, body=b'["not", "an", "object"]')

    result = search_catalogue()

    assert result["ok"] is False


def test_absent_fields_stay_absent_rather_than_becoming_text(monkeypatch):
    """Keep a null licence or version bound null.

    Rendering every field as text turns an unset bound into the string
    ``"None"``, which reads as a real value and is worse than a gap.
    """
    _stub(
        monkeypatch,
        {
            **DATASET,
            "licence": None,
            "current_release": {
                **RELEASE,
                "deprecated_at": None,
                "synthesizer_max_version": None,
                "grid": {
                    **RELEASE["grid"],
                    "model_parameters": {"alpha": False, "count": 13},
                },
            },
        },
    )

    result = describe_catalogue_dataset("bpass-2-2-1-cloudy-sps")
    release = result["current_release"]

    assert result["licence"] is None
    assert release["deprecated_at"] is None
    assert release["synthesizer_max_version"] is None
    assert release["grid"]["model_parameters"] == {"alpha": False, "count": 13}


def test_a_tls_failure_is_named_as_one(monkeypatch):
    """Point at TLS interception rather than at a network outage.

    A proxy or antivirus rewriting certificates is the common cause and
    needs a different fix from "the service is down".
    """
    import ssl
    import urllib.error

    _stub(
        monkeypatch,
        None,
        error=urllib.error.URLError(
            ssl.SSLCertVerificationError("self-signed certificate in chain")
        ),
    )

    result = search_catalogue()

    assert result["ok"] is False
    assert "TLS-intercepting proxy" in result["hint"]
