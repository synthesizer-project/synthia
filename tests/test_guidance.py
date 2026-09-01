"""Test documentation search and canonical example lookup."""

import re
from pathlib import Path

import pytest

from synthia._safety import MAX_SNIPPET_CHARS
from synthia.guidance import SKILL_ROOT, find_example, search_documentation

HOSTILE = ["a" * 100000, "\x00\x1b[31mred", "\x07\x08 grid \x7f", ""]


def _common_word() -> str:
    """Pick a long word that certainly appears in the bundled SKILL.md.

    Returns:
        The most frequent seven-or-more letter word in the skill file.
    """
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    words = re.findall(r"[A-Za-z]{7,}", text)
    return max(set(words), key=words.count)


def test_search_finds_known_skill_text():
    """Find a known word from the bundled SKILL.md."""
    result = search_documentation(_common_word())

    assert result["hits"]
    assert any(hit["path"].endswith("SKILL.md") for hit in result["hits"])
    assert any(
        entry["corpus"] == "bundled_skill"
        for entry in result["corpora_searched"]
    )


def test_search_snippets_are_capped_and_untrusted():
    """Cap snippets and label them as untrusted data."""
    result = search_documentation(_common_word())

    for hit in result["hits"]:
        snippet = hit["snippet"]
        assert snippet["content_is_untrusted"] is True
        assert len(snippet["content"]) <= MAX_SNIPPET_CHARS
        assert isinstance(hit["line"], int)


def test_search_respects_hit_cap():
    """Never return more hits than the documented cap."""
    result = search_documentation(_common_word())

    assert len(result["hits"]) <= 50
    assert result["hit_count"] == len(result["hits"])


def test_search_with_no_match_is_well_formed():
    """Return an empty but complete result when nothing matches."""
    result = search_documentation("qzzxwvyk_not_present_anywhere")

    assert result["hits"] == []
    assert result["hit_count"] == 0
    assert result["truncated"] is False
    assert "corpora_searched" in result


def test_search_reports_missing_checkout_corpus():
    """Say plainly which corpora were not searched."""
    result = search_documentation("grid")

    names = {entry["corpus"] for entry in result["corpora_searched"]}
    assert "bundled_skill" in names

    # Synthesizer's documentation is not installed by pip, so it is
    # searchable only from a source checkout. Whichever is the case, the
    # answer must account for it rather than staying silent.
    searched_checkout = "checkout_docs" in names
    explained = [
        note for note in result["corpora_unavailable"] if note.strip()
    ]
    assert searched_checkout or explained, (
        "the checkout corpus was neither searched nor explained"
    )


def test_find_example_degrades_gracefully():
    """Return a structured result when nothing matches."""
    result = find_example("qzzxwvyk nothing like this exists")

    assert isinstance(result, dict)
    assert result["example"] is None or "path" in result["example"]
    assert isinstance(result["notes"], list)


def test_find_example_returns_capped_source_when_matched():
    """Return the matched example with its path and capped source.

    A bundled example for this task always ships, so an empty result is
    a regression rather than an acceptable outcome.
    """
    result = find_example("parametric stellar sed")

    assert result["example"] is not None, result["notes"]
    assert result["example"]["path"].endswith(".py")
    assert result["example"]["source"]["content_is_untrusted"] is True
    assert result["available_examples"]


def test_emission_model_references_are_routed_from_skill():
    """Keep detailed emission-model references discoverable."""
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    for name in (
        "premade-emission-models.md",
        "custom-emission-models.md",
        "model-parameters.md",
    ):
        assert name in skill
        assert (SKILL_ROOT / "references" / name).is_file()


def test_premade_reference_covers_registered_models():
    """Make registry growth fail until its guidance is documented."""
    emission_models = pytest.importorskip("synthesizer.emission_models")
    documented = (
        SKILL_ROOT / "references" / "premade-emission-models.md"
    ).read_text(encoding="utf-8")
    registered = set(emission_models.PREMADE_MODELS)
    registered.update(emission_models.DUST_GENERATORS)
    missing = sorted(
        name for name in registered if f"`{name}`" not in documented
    )
    assert not missing, f"undocumented emission models: {missing}"


def test_hostile_inputs_return_structured_results():
    """Survive long, null-byte and control-character input."""
    for value in HOSTILE:
        search = search_documentation(value)
        example = find_example(value)

        assert isinstance(search, dict)
        assert "error" not in search
        assert isinstance(example, dict)
        assert "error" not in example


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        ("run many galaxies at once", "pipeline"),
        ("emission line luminosities and BPT", "lines"),
        ("black hole AGN spectrum", "agn"),
        ("make fake particle data with no simulation", "mock-data"),
        ("dust attenuation model", "emission-models"),
        ("plot a spectrum and save it", "plotting"),
        ("images of a galaxy", "imaging"),
        ("photometry in filters", "photometry"),
    ],
)
def test_find_example_routes_to_the_right_example(task, expected):
    """Route a plainly worded task to the example that answers it.

    Returning the wrong example costs the agent a whole file of context
    and teaches it the wrong workflow, so routing accuracy matters more
    than the examples merely existing.
    """
    result = find_example(task)

    assert result["example"] is not None, result["notes"]
    assert Path(result["example"]["path"]).stem == expected
