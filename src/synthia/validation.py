"""Statically check a Synthesizer script without ever running it.

Hard security boundary: :func:`validate_script` NEVER executes the
script it is given, and Synthia contains no code executor at all. The
script is parsed into an abstract syntax tree, which evaluates nothing.
The script's own imports are resolved with ``importlib.util.find_spec``
on top-level module names only, which consults the path finders but
loads no module code, so the script's dependencies are never imported
and the script's own modules are never run.

Synthesizer itself is the exception, and it is deliberate: checking
attributes and keyword arguments against the installed package means
importing it, through :mod:`synthia.inspection` and
:mod:`synthia.grids`. That costs a couple of seconds on first use and
creates Synthesizer's data directories as a side effect. The import
surface is bounded by the dotted-name validation in
:mod:`synthia.inspection`, and it only happens for a script that
references Synthesizer.

Nothing else is executed: no process is spawned, no binary object file
is deserialised, and no part of the script's own text ever reaches an
interpreter. Running the script is the agent host's job, through its
own permission-gated shell tool. Where running it would settle a
question, this module returns a suggested command string for the host
to approve and run itself.
"""

import ast
from importlib.util import find_spec

from synthia._safety import MAX_SNIPPET_CHARS, clean_text, truncate
from synthia.inspection import inspect_synthesizer_api

MAX_SOURCE_BYTES = 256 * 1024
MAX_SOURCE_LINES = 5000
MAX_NODES = 50000
MAX_DIAGNOSTICS = 100
MAX_RESOLUTIONS = 50


def _diagnostic(
    severity: str, code: str, message: str, line: int | None = None
) -> dict[str, object]:
    """Build one diagnostic entry.

    Args:
        severity: ``"error"`` or ``"warning"``.
        code: Short machine-readable category.
        message: Human-readable explanation.
        line: Source line the diagnostic refers to, if known.

    Returns:
        The diagnostic mapping, with the message cleaned and capped.
    """
    text, _ = truncate(clean_text(message), MAX_SNIPPET_CHARS)
    return {
        "severity": severity,
        "code": code,
        "line": line,
        "message": text,
    }


def _dotted(node: ast.AST) -> str | None:
    """Rebuild a dotted name from a ``Name``/``Attribute`` chain.

    Args:
        node: The outermost node of the chain.

    Returns:
        The dotted name, or ``None`` if the chain is not purely
        attribute access on a bare name.
    """
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _collect(tree: ast.AST) -> dict[str, object]:
    """Walk the tree iteratively and collect what the checks need.

    Args:
        tree: Parsed module.

    Returns:
        A mapping with imported top-level modules, the Synthesizer alias
        map, the Synthesizer names imported by ``from`` (checked even
        when unused), dotted-name uses, call sites, and whether the node
        cap bit.
    """
    modules: dict[str, int] = {}
    aliases: dict[str, str] = {}
    imported: dict[str, int] = {}
    uses: dict[str, int] = {}
    calls: list[dict[str, object]] = []
    nodes = 0
    capped = False

    for node in ast.walk(tree):
        nodes += 1
        if nodes > MAX_NODES:
            capped = True
            break
        line = getattr(node, "lineno", None)
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                modules.setdefault(top, line)
                if top == "synthesizer":
                    bound = alias.asname or top
                    aliases[bound] = alias.name if alias.asname else top
        elif isinstance(node, ast.ImportFrom):
            if node.level or not node.module:
                continue
            top = node.module.split(".")[0]
            modules.setdefault(top, line)
            if top == "synthesizer":
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    bound = alias.asname or alias.name
                    aliases[bound] = f"{node.module}.{alias.name}"
                    # A wrong import path fails at run time whether or
                    # not the name is later used, and importing from
                    # the wrong module is the most common way a
                    # generated Synthesizer script breaks. Record the
                    # binding itself so it is checked on its own.
                    imported[f"{node.module}.{alias.name}"] = line
        elif isinstance(node, (ast.Name, ast.Attribute)):
            dotted = _dotted(node)
            if dotted:
                uses.setdefault(dotted, line)
        elif isinstance(node, ast.Call):
            dotted = _dotted(node.func)
            if dotted:
                calls.append(
                    {
                        "name": dotted,
                        "line": line,
                        "keywords": [kw.arg for kw in node.keywords if kw.arg],
                        "first_string": next(
                            (
                                arg.value
                                for arg in node.args[:1]
                                if isinstance(arg, ast.Constant)
                                and isinstance(arg.value, str)
                            ),
                            None,
                        ),
                        "string_keywords": {
                            kw.arg: kw.value.value
                            for kw in node.keywords
                            if kw.arg
                            and isinstance(kw.value, ast.Constant)
                            and isinstance(kw.value.value, str)
                        },
                    }
                )
    return {
        "modules": modules,
        "aliases": aliases,
        "imported": imported,
        "uses": uses,
        "calls": calls,
        "capped": capped,
    }


def _resolve(dotted: str, aliases: dict[str, str]) -> str | None:
    """Map a used dotted name onto its Synthesizer dotted name.

    Args:
        dotted: Name as written in the script.
        aliases: Binding name to Synthesizer dotted name.

    Returns:
        The Synthesizer dotted name, or ``None`` if the name is not
        bound to Synthesizer.
    """
    head, _, rest = dotted.partition(".")
    target = aliases.get(head)
    if target is None:
        return None
    return f"{target}.{rest}" if rest else target


def _parameter_names(info: dict[str, object]) -> set[str] | None:
    """Extract accepted parameter names from an inspection result.

    Args:
        info: Result of ``inspect_synthesizer_api``.

    Returns:
        The accepted keyword names, or ``None`` when the signature is
        unknown or accepts arbitrary keywords.
    """
    signature = info.get("signature")
    if not isinstance(signature, str):
        return None
    try:
        parsed = ast.parse(f"def _signature{signature}: pass")
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return None
    function = parsed.body[0]
    if not isinstance(function, ast.FunctionDef) or function.args.kwarg:
        return None
    arguments = function.args
    names = {
        argument.arg
        for argument in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        )
    }
    names.discard("self")
    return names or None


def _check_api(
    collected: dict[str, object], diagnostics: list[dict[str, object]]
) -> str | None:
    """Check referenced Synthesizer names against the installed package.

    Args:
        collected: Output of :func:`_collect`.
        diagnostics: List appended to in place.

    Returns:
        A note explaining why the check was skipped, or ``None``.
    """
    aliases: dict[str, str] = collected["aliases"]
    if not aliases:
        return None
    try:
        probe = inspect_synthesizer_api("synthesizer")
    except Exception as error:
        return f"Synthesizer API inspection failed: {type(error).__name__}"
    if not isinstance(probe, dict) or probe.get("error"):
        return (
            "Synthesizer API inspection returned an error, so "
            "referenced Synthesizer names were not checked."
        )
    resolved: dict[str, dict[str, object]] = {}

    names = {
        resolved_name: line
        for dotted, line in collected["uses"].items()
        if (resolved_name := _resolve(dotted, aliases))
    }
    # Imported-but-unused names still have to exist.
    for name, line in collected["imported"].items():
        names.setdefault(name, line)
    keep = [
        name
        for name in names
        if not any(
            other != name and other.startswith(f"{name}.") for other in names
        )
    ]
    for name in keep[:MAX_RESOLUTIONS]:
        try:
            info = inspect_synthesizer_api(name)
        except Exception as error:
            diagnostics.append(
                _diagnostic(
                    "warning",
                    "inspection-failed",
                    f"Could not inspect {name}: {type(error).__name__}",
                    names[name],
                )
            )
            continue
        if not isinstance(info, dict):
            continue
        if info.get("error"):
            diagnostics.append(
                _diagnostic(
                    "error",
                    "unknown-attribute",
                    f"{name} could not be resolved in the installed "
                    f"Synthesizer: {info['error']}",
                    names[name],
                )
            )
        else:
            resolved[name] = info

    for call in collected["calls"]:
        name = _resolve(call["name"], aliases)
        info = resolved.get(name) if name else None
        if info is None:
            continue
        accepted = _parameter_names(info)
        if accepted is None:
            continue
        for keyword in call["keywords"]:
            if keyword not in accepted:
                diagnostics.append(
                    _diagnostic(
                        "error",
                        "unknown-keyword",
                        f"{name} does not accept keyword argument "
                        f"{keyword!r}.",
                        call["line"],
                    )
                )
    return None


def _check_grids(
    collected: dict[str, object], diagnostics: list[dict[str, object]]
) -> dict[str, object] | None:
    """Check ``Grid(...)`` names against the locally available grids.

    Args:
        collected: Output of :func:`_collect`.
        diagnostics: List appended to in place.

    Returns:
        A mapping of the requested grid names and the local ones, or
        ``None`` when grid listing is unavailable or unused.
    """
    aliases: dict[str, str] = collected["aliases"]
    requested: dict[str, int] = {}
    for call in collected["calls"]:
        resolved = _resolve(call["name"], aliases)
        if resolved is None or resolved.rsplit(".", 1)[-1] != "Grid":
            continue
        name = call["first_string"] or call["string_keywords"].get("grid_name")
        if isinstance(name, str):
            requested.setdefault(name, call["line"])
    if not requested:
        return None
    try:
        from synthia.grids import list_local_grids

        listing = list_local_grids()
    except Exception:
        return None
    if not listing.get("ok"):
        return None

    local = {entry["name"] for entry in listing["grids"]}
    for name, line in requested.items():
        # Mirror Synthesizer, which strips only ".hdf5". Any other
        # extension is appended to rather than replaced, so
        # Grid("x.h5") looks for "x.h5.hdf5" and fails at run time.
        # Normalising it away here would declare the trap safe.
        stem = name.removesuffix(".hdf5")
        if stem != name.removesuffix(".hdf5").removesuffix(".h5"):
            diagnostics.append(
                _diagnostic(
                    "error",
                    "grid-extension",
                    (
                        f"Grid {name!r} keeps its suffix: Synthesizer "
                        f'strips only ".hdf5", so this opens '
                        f"{name}.hdf5. Pass {stem.removesuffix('.h5')!r}."
                    ),
                    line,
                )
            )
            continue
        if stem not in local:
            diagnostics.append(
                _diagnostic(
                    "warning",
                    "missing-grid",
                    f"Grid {name!r} is not among the local grids.",
                    line,
                )
            )
    return {"requested": sorted(requested), "local": sorted(local)}


def validate_script(source: str) -> dict[str, object]:
    """Statically validate a Synthesizer script.

    The script is parsed, never run. Checks run least invasive first:
    syntax, import availability by specification lookup only, referenced
    Synthesizer attributes and keyword arguments, and locally available
    grids.

    Args:
        source: Python source text.

    Returns:
        A mapping with ``ok`` (no error-level diagnostics),
        ``script_was_run`` (always ``False``), a ``summary`` sentence,
        ``diagnostics`` (a list of ``{severity, code, line, message}``
        capped at 100) with ``diagnostics_truncated`` recording whether
        that cap bit, ``imports`` as ``{found, missing}`` lists of
        top-level module names, ``notes`` explaining any check that was
        skipped, and ``suggested_commands`` the host may choose to run
        itself. ``grids`` with ``{requested, local}`` grid names is
        present only when the script builds a Grid and the local grid
        listing is available, and ``error`` is present only when
        validation itself failed.
    """
    result: dict[str, object] = {
        "ok": False,
        "script_was_run": False,
        "summary": "",
        "diagnostics": [],
        "diagnostics_truncated": False,
        "imports": {"found": [], "missing": []},
        "notes": [],
        "suggested_commands": [],
    }
    diagnostics: list[dict[str, object]] = result["diagnostics"]
    notes: list[str] = result["notes"]
    try:
        if not isinstance(source, str):
            source = str(source)
        size = len(source.encode("utf-8", "replace"))
        if size > MAX_SOURCE_BYTES:
            diagnostics.append(
                _diagnostic(
                    "error",
                    "source-too-large",
                    f"Source is {size} bytes, over the "
                    f"{MAX_SOURCE_BYTES} byte limit; it was not parsed.",
                )
            )
            result["summary"] = "Source too large to validate."
            return result
        line_count = source.count("\n") + 1
        if line_count > MAX_SOURCE_LINES:
            diagnostics.append(
                _diagnostic(
                    "error",
                    "source-too-long",
                    f"Source has {line_count} lines, over the "
                    f"{MAX_SOURCE_LINES} line limit; it was not parsed.",
                )
            )
            result["summary"] = "Source too long to validate."
            return result

        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError, MemoryError, RecursionError) as err:
            line = getattr(err, "lineno", None)
            diagnostics.append(
                _diagnostic(
                    "error",
                    "syntax-error",
                    f"{type(err).__name__}: {err}",
                    line if isinstance(line, int) else None,
                )
            )
            result["summary"] = "Script does not parse."
            return result

        collected = _collect(tree)
        if collected["capped"]:
            diagnostics.append(
                _diagnostic(
                    "warning",
                    "tree-too-large",
                    f"Stopped after {MAX_NODES} syntax nodes; later parts "
                    "of the script were not checked.",
                )
            )

        found: list[str] = []
        missing: list[str] = []
        for module, line in collected["modules"].items():
            try:
                spec = find_spec(module)
            except (ImportError, ValueError, AttributeError):
                spec = None
            if spec is None:
                missing.append(module)
                diagnostics.append(
                    _diagnostic(
                        "error",
                        "missing-import",
                        f"Module {module!r} is not importable in this "
                        "environment.",
                        line,
                    )
                )
            else:
                found.append(module)
        result["imports"] = {
            "found": sorted(found),
            "missing": sorted(missing),
        }
        if missing:
            result["suggested_commands"].append(
                "python -m pip install "
                + " ".join(sorted(missing))
                + "  # distribution names may differ from module names"
            )

        note = _check_api(collected, diagnostics)
        if note:
            notes.append(note)
        grids = _check_grids(collected, diagnostics)
        if grids is not None:
            result["grids"] = grids

        errors = [item for item in diagnostics if item["severity"] == "error"]
        result["ok"] = not errors
        result["summary"] = (
            f"{len(errors)} error(s) and "
            f"{len(diagnostics) - len(errors)} warning(s); "
            "the script was not run."
        )
        result["suggested_commands"].append(
            "python your_script.py  # run this yourself, Synthia will not"
        )
    except Exception as error:  # never raise at the MCP boundary
        result["error"] = f"{type(error).__name__}: {error}"
        result["summary"] = "Validation failed."
    if len(diagnostics) > MAX_DIAGNOSTICS:
        result["diagnostics"] = diagnostics[:MAX_DIAGNOSTICS]
        result["diagnostics_truncated"] = True
    return result
