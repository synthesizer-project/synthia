"""Run one benchmark case in one arm and record what it cost.

Both arms run the same agent against the same Synthesizer environment in a
fresh temporary directory. They differ only in whether Synthia's skill and
MCP server are present:

* ``baseline`` gets an empty MCP config, so no server at all.
* ``synthia`` gets a project-scoped copy of the bundled skill and the
  ``synthia-mcp`` server from the Synthesizer environment.

``--strict-mcp-config`` is passed in both arms, and both get a throwaway
``HOME``, so servers, settings, hooks and plugins configured on the
developer's own machine cannot leak into either one.
"""

import json
import shutil
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "src" / "synthia" / "skill"

#: Tools the agent may use. The baseline needs the file-reading tools to
#: explore Synthesizer's source; that exploration is the cost being measured.
ALLOWED = [
    "Read",
    "Grep",
    "Glob",
    "Bash",
    "Write",
    "Edit",
    "TodoWrite",
    "mcp__synthia",
]

ARMS = ("baseline", "synthia")


def _ignore_non_source(directory: str, names: list[str]) -> list[str]:
    """Skip caches, compiled assets and data when copying readable source."""
    ignored = []
    for name in names:
        path = Path(directory) / name
        if path.is_dir():
            if name == "__pycache__":
                ignored.append(name)
        elif path.suffix not in {".py", ".yml", ".yaml"}:
            ignored.append(name)
    return ignored


def _write_mcp_config(
    directory: Path, arm: str, server: Path, backend: str
) -> Path:
    """Write the MCP configuration for one arm.

    Args:
        directory: Run directory.
        arm: ``baseline`` or ``synthia``.
        server: Path to the ``synthia-mcp`` executable.
        backend: Agent CLI being configured.

    Returns:
        Path to the configuration file.
    """
    if backend == "opencode":
        servers = {}
        if arm == "synthia":
            servers["synthia"] = {
                "type": "local",
                "command": [
                    "env",
                    f"PYTHONPATH={REPO / 'src'}",
                    str(server),
                    "-m",
                    "synthia.server",
                ],
                "enabled": True,
            }
        path = directory / "opencode.json"
        path.write_text(
            json.dumps(
                {
                    "mcp": servers,
                    "permission": {
                        "external_directory": {
                            "*": "deny",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        return path
    servers = {}
    if arm == "synthia":
        servers["synthia"] = {
            "type": "stdio",
            "command": "env",
            "args": [
                f"PYTHONPATH={REPO / 'src'}",
                str(server),
                "-m",
                "synthia.server",
            ],
        }
    path = directory / "mcp.json"
    path.write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")
    return path


def prepare(
    directory: Path, arm: str, server: Path, backend: str = "claude"
) -> Path:
    """Set a run directory up for one arm.

    Args:
        directory: An empty directory.
        arm: ``baseline`` or ``synthia``.
        server: Path to the ``synthia-mcp`` executable.
        backend: Agent CLI being configured.

    Returns:
        Path to the MCP configuration file.
    """
    if arm == "synthia":
        skills = directory / ".claude" / "skills"
        skills.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SKILL, skills / "synthia")
    checkout = REPO.parent / "synthesizer"
    local_source = directory / "synthesizer-source"
    shutil.copytree(
        checkout / "src" / "synthesizer",
        local_source / "synthesizer",
        ignore=_ignore_non_source,
    )
    shutil.copytree(
        checkout / "examples",
        local_source / "examples",
        ignore=_ignore_non_source,
    )
    (directory / "AGENTS.md").write_text(
        "Synthesizer source for this benchmark is in ./synthesizer-source.\n"
        "Do not search or read paths outside the current workspace.\n",
        encoding="utf-8",
    )
    return _write_mcp_config(directory, arm, server, backend)


def _trace_input(value: object) -> object:
    """Keep tool targets and queries without copying edited file contents."""
    if not isinstance(value, dict):
        return value
    omitted = {"content", "oldString", "newString", "patchText"}
    return {key: item for key, item in value.items() if key not in omitted}


def _category(name: str, tool_input: object, workdir: Path) -> str:
    """Classify a tool call from its target rather than only its name."""
    lowered = name.lower()
    if lowered.startswith(("synthia_", "mcp__synthia")):
        return "synthia"
    if lowered in {"write", "edit", "apply_patch"}:
        return "artifact"
    if lowered in {"read", "grep", "glob"} and isinstance(tool_input, dict):
        target = (
            tool_input.get("file_path")
            or tool_input.get("filePath")
            or tool_input.get("path")
        )
        if target:
            # Claude reports relative paths, so resolve against the run
            # directory rather than the harness's own cwd.
            full = (workdir / target).resolve()
            if full.is_dir():
                return "environment_exploration"
            try:
                relative = full.relative_to(workdir.resolve())
                if (
                    relative.parts
                    and relative.parts[0] == "synthesizer-source"
                ):
                    return "source_exploration"
            except ValueError:
                return "source_exploration"
        return "workspace_inspection"
    if lowered == "bash" and isinstance(tool_input, dict):
        command = str(tool_input.get("command", ""))
        if "answer.py" in command:
            return "execution"
        checkout = str(REPO.parent / "synthesizer")
        source_markers = (
            str(workdir / "synthesizer-source"),
            "synthesizer-source/",
            f"{checkout}/src/",
            f"{checkout}/examples/",
            f"{checkout}/tests/",
            "site-packages/synthesizer/",
        )
        if any(marker in command for marker in source_markers):
            return "source_exploration"
        environment_markers = ("find /", "pip show", "sys.path")
        if any(marker in command for marker in environment_markers):
            return "environment_exploration"
        return "shell"
    return "other"


def _record_tool(
    trace: list[dict],
    name: str,
    tool_input: object,
    output: object,
    workdir: Path,
) -> str:
    """Append a compact tool trace entry and return its category."""
    category = _category(name, tool_input, workdir)
    rendered = str(output).lower()
    trace.append(
        {
            "tool": name,
            "category": category,
            "input": _trace_input(tool_input),
            "output_bytes": len(json.dumps(output)),
            "denied": any(
                marker in rendered
                for marker in ("permission denied", "not allowed", "denied")
            ),
        }
    )
    return category


def _accumulate_opencode(
    event: dict,
    totals: dict,
    replies: list[str],
    errors: list[str],
    trace: list[dict],
    workdir: Path,
) -> None:
    """Fold one OpenCode JSON event into benchmark totals."""
    kind = event.get("type")
    part = event.get("part", {})
    if kind == "tool_use":
        name = str(part.get("tool", ""))
        state = part.get("state", {})
        tool_input = state.get("input", {})
        output = state.get("output", "")
        size = len(json.dumps(output))
        category = _record_tool(trace, name, tool_input, output, workdir)
        if category == "synthia":
            totals["synthia_tool_calls"] += 1
            totals["synthia_tool_bytes"] += size
        elif category == "source_exploration":
            totals["exploration_calls"] += 1
            totals["exploration_bytes"] += size
    elif kind == "text":
        replies.append(str(part.get("text", "")))
    elif kind == "step_finish":
        tokens = part.get("tokens", {})
        totals["input_tokens"] += tokens.get("input", 0) or 0
        totals["output_tokens"] += tokens.get("output", 0) or 0
        totals["cache_read_input_tokens"] += (
            tokens.get("cache", {}).get("read", 0) or 0
        )
        totals["cost_usd"] += part.get("cost", 0.0) or 0.0
        totals["turns"] += 1
    elif kind == "error":
        error = event.get("error", {})
        errors.append(str(error.get("data", {}).get("message") or error))


def _accumulate(
    event: dict,
    seen: dict,
    totals: dict,
    trace: list[dict],
    workdir: Path,
) -> None:
    """Fold one stream event into the running totals.

    Args:
        event: A decoded stream-json event.
        seen: Maps tool-use id to tool name, filled as calls appear.
        totals: Mutated in place.
        trace: Compact per-tool records, mutated in place.
        workdir: Run directory used to distinguish local from external reads.
    """
    kind = event.get("type")
    content = event.get("message", {}).get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict):
            continue
        if kind == "assistant" and block.get("type") == "tool_use":
            name = str(block.get("name", ""))
            seen[block.get("id")] = (name, block.get("input", {}))
        elif kind == "user" and block.get("type") == "tool_result":
            name, tool_input = seen.get(
                block.get("tool_use_id"), ("", {})
            )
            output = block.get("content", "")
            size = len(json.dumps(output))
            category = _record_tool(
                trace, name, tool_input, output, workdir
            )
            if category == "synthia":
                totals["synthia_tool_calls"] += 1
                totals["synthia_tool_bytes"] += size
            elif category == "source_exploration":
                totals["exploration_calls"] += 1
                totals["exploration_bytes"] += size


def run_case(
    case: dict,
    arm: str,
    repeat: int,
    server: Path,
    workdir: Path,
    model: str,
    timeout: int = 900,
    env: dict | None = None,
    backend: str = "claude",
) -> dict:
    """Run every turn of one case in one arm.

    Args:
        case: One entry from ``cases.CASES``.
        arm: ``baseline`` or ``synthia``.
        repeat: Repeat index, recorded for grouping.
        server: Path to the ``synthia-mcp`` executable.
        workdir: Empty directory to run in.
        model: Model identifier passed to the agent.
        timeout: Seconds allowed for a single turn.
        env: Environment for the agent. Both arms get the same one, with
            the Synthesizer environment first on ``PATH`` so ``python``
            means the interpreter that has Synthesizer installed.
        backend: Agent CLI to run.

    Returns:
        One result record.
    """
    from cases import prompts

    config = prepare(workdir, arm, server, backend)
    totals = {
        "exploration_calls": 0,
        "exploration_bytes": 0,
        "synthia_tool_calls": 0,
        "synthia_tool_bytes": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cost_usd": 0.0,
        "turns": 0,
    }
    seen: dict = {}
    started = time.monotonic()
    session: str | None = None
    errors: list[str] = []
    # Cases 8, 9 and 10 are diagnostic: the prose is the answer and there
    # may be no script at all, so the final text is graded too.
    replies: list[str] = []
    tool_trace: list[dict] = []

    for index, prompt in enumerate(prompts(case)):
        if backend == "opencode":
            command = [
                "opencode",
                "run",
                "--pure",
                "--auto",
                "--format",
                "json",
                "--model",
                model,
                "--dir",
                str(workdir),
                prompt,
            ]
            if session:
                command += ["--session", session]
        else:
            command = [
                "claude",
                "-p",
                prompt,
                "--output-format",
                "stream-json",
                "--verbose",
                "--model",
                model,
                "--mcp-config",
                str(config),
                "--strict-mcp-config",
                "--permission-mode",
                "bypassPermissions",
                "--allowedTools",
                *ALLOWED,
            ]
            if session:
                command += ["--resume", session]
        # Both backends get a throwaway HOME. Without it the agent reads the
        # developer's own ~/.claude: a global CLAUDE.md, a settings model
        # override, prompt hooks, and enabled plugins all leak into every run
        # and change how the agent explores. Credentials live in the OS
        # keychain, so authentication survives the swap.
        run_env = dict(env or {})
        home = workdir / "home"
        config_home = workdir / "config"
        home.mkdir(exist_ok=True)
        config_home.mkdir(exist_ok=True)
        run_env.update(
            {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(config_home),
                "PWD": str(workdir),
                "INIT_CWD": str(workdir),
            }
        )
        try:
            done = subprocess.run(
                command,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=run_env,
            )
        except subprocess.TimeoutExpired:
            errors.append(f"turn {index} timed out after {timeout}s")
            break
        for line in done.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if backend == "opencode":
                _accumulate_opencode(
                    event,
                    totals,
                    replies,
                    errors,
                    tool_trace,
                    workdir,
                )
                session = event.get("sessionID") or session
                continue
            _accumulate(event, seen, totals, tool_trace, workdir)
            if event.get("type") == "result":
                usage = event.get("usage", {}) or {}
                for key in (
                    "input_tokens",
                    "output_tokens",
                    "cache_read_input_tokens",
                ):
                    totals[key] += usage.get(key, 0) or 0
                totals["cost_usd"] += event.get("total_cost_usd", 0.0) or 0.0
                totals["turns"] += event.get("num_turns", 0) or 0
                session = event.get("session_id") or session
                replies.append(str(event.get("result", "")))
                if event.get("is_error"):
                    errors.append(
                        f"turn {index}: {event.get('subtype')}: "
                        f"{event.get('result', '')}"
                    )
        if done.returncode and not errors:
            errors.append(
                done.stderr.strip() or f"agent exited {done.returncode}"
            )
        if errors:
            break

    answer = workdir / "answer.py"
    return {
        "case_id": case["id"],
        "case": case["name"],
        "axis": case["axis"],
        "arm": arm,
        "repeat": repeat,
        "model": model,
        "backend": backend,
        "wall_seconds": round(time.monotonic() - started, 1),
        "answer_written": answer.is_file(),
        "answer": answer.read_text(encoding="utf-8", errors="replace")
        if answer.is_file()
        else "",
        "replies": replies,
        "workdir": str(workdir),
        "errors": errors,
        "tool_trace": tool_trace,
        **totals,
    }
