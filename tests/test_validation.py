"""Test static script validation, above all that it runs nothing."""

import ast
import sys
from importlib.util import find_spec
from pathlib import Path

import pytest

from synthia import guidance, validation
from synthia.validation import (
    MAX_SOURCE_BYTES,
    MAX_SOURCE_LINES,
    validate_script,
)

SYNTHESIZER_INSTALLED = find_spec("synthesizer") is not None


def test_validate_script_never_executes(tmp_path):
    """Refuse to run the script, whatever side effects it would have."""
    first = tmp_path / "marker_open.txt"
    second = tmp_path / "marker_pathlib.txt"
    source = (
        "import pathlib\n"
        f"handle = open({str(first)!r}, 'w')\n"
        "handle.write('ran')\n"
        "handle.close()\n"
        f"pathlib.Path({str(second)!r}).write_text('ran')\n"
    )

    result = validate_script(source)

    assert isinstance(result, dict)
    assert result["script_was_run"] is False
    assert not first.exists()
    assert not second.exists()


#: Callables that would turn Synthia into a code executor.
EXECUTION_PRIMITIVES = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "os.system",
    "os.popen",
    "os.execv",
    "os.spawnv",
    "runpy.run_path",
    "runpy.run_module",
    "subprocess.run",
    "subprocess.call",
    "subprocess.Popen",
    "pickle.load",
    "pickle.loads",
}

#: Modules whose import implies the ability to run something.
EXECUTION_MODULES = {"runpy", "pickle"}


def _called_name(node):
    """Return the dotted name a call node invokes, if it has one."""
    parts = []
    current = node.func
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def _synthia_modules():
    """Yield every Synthia module path except the installer."""
    package = Path(validation.__file__).parent
    return sorted(
        path
        for path in package.glob("*.py")
        # install.py legitimately runs the Claude Code CLI. It is a
        # console script and is never registered as an MCP tool.
        if path.name != "install.py"
    )


@pytest.mark.parametrize(
    "path", _synthia_modules(), ids=lambda path: path.name
)
def test_no_module_can_execute_code(path):
    """Keep execution primitives out of every tool-reachable module.

    Checked on the parsed syntax tree rather than the raw text, so
    documentation may name these primitives plainly while genuine calls
    and imports are still caught.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _called_name(node)
            assert name not in EXECUTION_PRIMITIVES, (
                f"{path.name} calls {name}"
            )
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root not in EXECUTION_MODULES, (
                    f"{path.name} imports {alias.name}"
                )
        if isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            assert root not in EXECUTION_MODULES, (
                f"{path.name} imports from {node.module}"
            )


def test_deeply_nested_source_is_structured_error():
    """Survive input designed to blow the parser stack."""
    result = validate_script("(" * 100000)

    assert isinstance(result, dict)
    assert result["ok"] is False
    assert result["diagnostics"]


def test_oversized_source_is_rejected_before_parsing():
    """Reject source over the byte cap."""
    result = validate_script("# " + "a" * (MAX_SOURCE_BYTES + 10))

    assert result["ok"] is False
    codes = {item["code"] for item in result["diagnostics"]}
    assert "source-too-large" in codes


def test_overlong_source_is_rejected_before_parsing():
    """Reject source over the line cap."""
    result = validate_script("pass\n" * (MAX_SOURCE_LINES + 1))

    assert result["ok"] is False
    codes = {item["code"] for item in result["diagnostics"]}
    assert "source-too-long" in codes


def test_missing_import_is_reported():
    """Report an unimportable module without importing anything."""
    module = "definitely_not_a_real_module_xyz"
    result = validate_script(f"import {module}\n")

    assert module in result["imports"]["missing"]
    assert module not in sys.modules


def test_valid_script_passes():
    """Accept a script whose imports all resolve."""
    result = validate_script("import json\n\nprint(json.dumps({}))\n")

    assert result["ok"] is True
    assert "json" in result["imports"]["found"]
    assert result["suggested_commands"]


def test_syntax_error_is_reported():
    """Report a syntax error with its line."""
    result = validate_script("def broken(:\n    pass\n")

    assert result["ok"] is False
    assert result["diagnostics"][0]["code"] == "syntax-error"


@pytest.mark.skipif(
    not SYNTHESIZER_INSTALLED, reason="Synthesizer is not installed"
)
def test_bogus_synthesizer_attribute_is_reported():
    """Flag an attribute the installed Synthesizer does not have."""
    result = validate_script(
        "import synthesizer\n\nsynthesizer.definitely_not_here()\n"
    )

    codes = {item["code"] for item in result["diagnostics"]}
    if result["notes"]:
        pytest.skip("API inspection unavailable")
    assert "unknown-attribute" in codes


@pytest.mark.skipif(
    find_spec("synthesizer") is None, reason="Synthesizer is not installed"
)
@pytest.mark.parametrize(
    "example",
    sorted((Path(guidance.__file__).parent / "skill/examples").glob("*.py")),
    ids=lambda path: path.name,
)
def test_bundled_examples_validate(example):
    """Keep the shipped examples valid against installed Synthesizer.

    The examples are product behaviour, not decoration, so a Synthesizer
    release that renames something they use must fail the suite.
    """
    result = validate_script(example.read_text(encoding="utf-8"))

    errors = [
        diagnostic
        for diagnostic in result["diagnostics"]
        if diagnostic["severity"] == "error"
    ]
    assert not errors, f"{example.name}: {errors}"


@pytest.mark.skipif(
    find_spec("synthesizer") is None, reason="Synthesizer is not installed"
)
def test_wrong_import_path_is_caught_even_when_unused():
    """Check imported names on their own, not only where they are used.

    ``from synthesizer import Pipeline`` fails at run time whether or
    not the name is later used, and importing from the wrong module is
    the most common way a generated Synthesizer script breaks.
    """
    result = validate_script("from synthesizer import Grid, Pipeline\n")

    codes = {d["code"] for d in result["diagnostics"]}
    assert "unknown-attribute" in codes, result["diagnostics"]
    assert result["ok"] is False

    correct = validate_script(
        "from synthesizer.pipeline import Pipeline\n"
        "from synthesizer import Grid\n"
    )
    assert correct["ok"] is True, correct["diagnostics"]
