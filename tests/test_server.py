"""Test Synthia's MCP server and bundled skill."""

import asyncio
import json
from importlib.resources import files

import pytest
from mcp import Client

from synthia.server import _scrub_working_directory, mcp

EXPECTED_TOOLS = {
    "inspect_environment",
    "inspect_synthesizer_api",
    "list_local_grids",
    "inspect_local_grid",
    "search_documentation",
    "find_example",
    "validate_script",
    "plot_grid_spectra",
    "plot_grid_lines",
    "plot_grid_ionising_luminosity",
}

READ_ONLY_CALLS = {
    "inspect_environment": {},
    "inspect_synthesizer_api": {"dotted_name": "synthesizer.grid.Grid"},
    "list_local_grids": {},
    "inspect_local_grid": {"grid_name": "no_such_grid"},
    "search_documentation": {"query": "emission model"},
    "find_example": {"task": "parametric sed"},
    "validate_script": {"source": "import synthesizer\n"},
    "plot_grid_spectra": {"grid_name": "no_such_grid_zzz"},
    "plot_grid_lines": {"grid_name": "no_such_grid_zzz"},
    "plot_grid_ionising_luminosity": {"grid_name": "no_such_grid_zzz"},
}

# Arguments a steered model might supply. Every one must come back as
# structured data rather than an error through the MCP boundary.
HOSTILE_CALLS = {
    "inspect_synthesizer_api": {"dotted_name": "os.system"},
    "inspect_local_grid": {"grid_name": "../../etc/passwd"},
    "search_documentation": {"query": "\x00" + "x" * 5000},
    "find_example": {"task": ""},
    "validate_script": {"source": "(" * 50000},
}

# A key each tool always returns, in every environment.
STABLE_KEYS = {
    "inspect_environment": {"python_version"},
    "inspect_synthesizer_api": {"dotted_name", "error"},
    "list_local_grids": {"ok"},
    "inspect_local_grid": {"ok"},
    "search_documentation": {"query", "error"},
    "find_example": {"task", "error"},
    "validate_script": {"script_was_run", "error"},
    "plot_grid_spectra": {"ok"},
    "plot_grid_lines": {"ok"},
    "plot_grid_ionising_luminosity": {"ok"},
}


def _run(coroutine_factory):
    """Run one in-process client session against the server."""

    async def session():
        async with Client(mcp) as client:
            return await coroutine_factory(client)

    return asyncio.run(session())


def test_server_exposes_the_documented_tool_surface():
    """Expose exactly the implemented tools and nothing more."""
    tools = _run(lambda client: client.list_tools())

    assert {tool.name for tool in tools.tools} == EXPECTED_TOOLS


def test_server_never_exposes_the_installer():
    """Keep configuration changes out of reach of a steered model.

    ``synthia-install`` edits the agent host's own configuration, so it
    stays a console script rather than a callable tool.
    """
    tools = _run(lambda client: client.list_tools())
    names = {tool.name for tool in tools.tools}

    assert not any("install" in name for name in names)


def test_every_tool_has_a_description():
    """Give the model a description for each tool."""
    tools = _run(lambda client: client.list_tools())

    for tool in tools.tools:
        assert tool.description, f"{tool.name} has no description"


@pytest.mark.parametrize(
    ("name", "arguments"),
    sorted((name, args) for name, args in READ_ONLY_CALLS.items()),
)
def test_read_only_tools_return_structured_results(name, arguments):
    """Answer every read-only call with structured data, never an error.

    Synthesizer is not required: each tool reports its own unavailability
    rather than raising through the MCP boundary.
    """
    result = _run(lambda client: client.call_tool(name, arguments))

    assert result.is_error is False
    payload = json.loads(result.content[0].text)
    assert isinstance(payload, dict)
    assert STABLE_KEYS[name] & set(payload), (
        f"{name} returned none of {STABLE_KEYS[name]}: {sorted(payload)}"
    )


@pytest.mark.parametrize(
    ("name", "arguments"),
    sorted((name, args) for name, args in HOSTILE_CALLS.items()),
)
def test_hostile_arguments_never_raise_through_the_boundary(name, arguments):
    """Answer a steered model with data, not a protocol error."""
    result = _run(lambda client: client.call_tool(name, arguments))

    assert result.is_error is False
    assert isinstance(json.loads(result.content[0].text), dict)


def test_tool_responses_stay_within_a_usable_size():
    """Keep any single response small enough for an agent context.

    The MCP SDK emits a dict return on both the text and structured
    channels, so a tool's real cost to the agent is roughly twice its
    serialised size.
    """
    for name, arguments in {**READ_ONLY_CALLS, **HOSTILE_CALLS}.items():
        result = _run(lambda client: client.call_tool(name, arguments))
        size = len(result.content[0].text)
        assert size <= 24 * 1024, f"{name} returned {size} bytes"


def test_scrub_working_directory_removes_the_project_directory(
    monkeypatch, tmp_path
):
    """Stop a project file from shadowing the installed Synthesizer."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.path", ["", ".", str(tmp_path), "/usr/lib"])

    _scrub_working_directory()

    import sys

    assert sys.path == ["/usr/lib"]


def test_skill_is_packaged():
    """Include the Agent Skill in installed package resources."""
    skill = files("synthia").joinpath("skill")

    assert skill.joinpath("SKILL.md").is_file()
    assert skill.joinpath("references/concepts.md").is_file()
