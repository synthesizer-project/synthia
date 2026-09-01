"""One-time installer for Synthia's Agent Skill and MCP server.

Registers the bundled skill at ``~/.claude/skills/synthia`` (read by both
Claude Code and OpenCode) and the ``synthia-mcp`` server with each client
that is present. This is a setup command only: it is never exposed as an
MCP tool, so a steered model cannot rewrite the agent's own configuration.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from importlib.resources import files
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Callable, Mapping


def server_command() -> str:
    """Return the ``synthia-mcp`` to register with the agent hosts.

    Synthia inspects Synthesizer with a plain import in its own process,
    so the interpreter that runs the server decides which Synthesizer
    the user sees. Agent hosts start the server from their own login
    environment, not from an activated virtual environment, so a bare
    ``synthia-mcp`` would bind to whichever one happens to be first on
    that ``PATH``. Registering the absolute path next to the running
    interpreter pins the environment the user installed into.

    Returns:
        An absolute path where one can be found, otherwise the bare
        command name.
    """
    directory = Path(sys.executable).parent
    for name in ("synthia-mcp", "synthia-mcp.exe"):
        candidate = directory / name
        if candidate.is_file():
            return str(candidate)
    return shutil.which("synthia-mcp") or "synthia-mcp"


SERVER_COMMAND = server_command()
CLAUDE_ENTRY: dict[str, Any] = {
    "type": "stdio",
    "command": SERVER_COMMAND,
    "args": [],
}
OPENCODE_ENTRY: dict[str, Any] = {
    "type": "local",
    "command": [SERVER_COMMAND],
    "enabled": True,
}
OPENCODE_SCHEMA = "https://opencode.ai/config.json"
BACKUP_SUFFIX = ".synthia.bak"
SKILL_MARKER = "package: synthia"
CLAUDE_ADD_COMMAND = (
    "claude mcp add-json --scope user synthia "
    f"'{json.dumps(CLAUDE_ENTRY, separators=(',', ':'))}'"
)
CLAUDE_REMOVE_COMMAND = "claude mcp remove synthia --scope user"


# --- Paths -----------------------------------------------------------------


def skill_source() -> Path:
    """Return the skill directory bundled inside the installed package."""
    return Path(str(files("synthia").joinpath("skill")))


def home_dir(env: Mapping[str, str]) -> Path:
    """Return the user's home directory."""
    return Path(env.get("HOME") or os.path.expanduser("~"))


def skill_target(env: Mapping[str, str]) -> Path:
    """Return the personal skill directory shared by both clients."""
    return home_dir(env) / ".claude" / "skills" / "synthia"


def claude_config_path(env: Mapping[str, str]) -> Path:
    """Return ``~/.claude.json``, which holds user-scope MCP servers."""
    return home_dir(env) / ".claude.json"


def opencode_config_path(env: Mapping[str, str]) -> Path:
    """Return the OpenCode config file to read and write.

    OpenCode merges ``config.json``, ``opencode.json`` and
    ``opencode.jsonc`` in that order with later files winning, so an
    existing ``.jsonc`` is preferred and a second file is never created.
    """
    base = env.get("XDG_CONFIG_HOME")
    root = Path(base) if base else home_dir(env) / ".config"
    directory = root.expanduser() / "opencode"
    for name in ("opencode.jsonc", "opencode.json"):
        if (directory / name).is_file():
            return directory / name
    return directory / "opencode.json"


# --- Pure helpers ----------------------------------------------------------


def jsonc_reason(text: str) -> str | None:
    """Return why text cannot survive a JSON round-trip, else ``None``.

    OpenCode accepts comments and trailing commas, so such a file is
    valid for the user even though ``json.dumps`` would silently discard
    the comments. That is a different fault from broken JSON, and the
    message the user gets has to say so.

    Args:
        text: Raw config file contents.

    Returns:
        A short description of the JSONC-only syntax found, or ``None``
        when the text is plain JSON.
    """
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "/" and text[index + 1 : index + 2] in ("/", "*"):
            return "a comment"
        elif char == "," and text[index + 1 :].lstrip()[:1] in ("}", "]"):
            return "a trailing comma"
    return None


def load_opencode(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Parse an OpenCode config, refusing anything unsafe to rewrite.

    Args:
        path: Config file location; a missing file yields a fresh dict.

    Returns:
        A ``(data, error)`` pair where exactly one element is ``None``.
    """
    if not path.exists():
        return {"$schema": OPENCODE_SCHEMA}, None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"{path} could not be read ({exc})"
    reason = jsonc_reason(text)
    if reason is not None:
        return None, f"{path} contains {reason}, which a rewrite destroys"
    if not text.strip():
        return {"$schema": OPENCODE_SCHEMA}, None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, (
            f"{path} is not valid JSON: {exc.msg} "
            f"(line {exc.lineno}, column {exc.colno})"
        )
    if not isinstance(data, dict):
        return None, f"{path} is not a JSON object"
    if "mcp" in data and not isinstance(data["mcp"], dict):
        return None, f'{path} has a non-object "mcp" key'
    return data, None


def existing_mcp_entry(data: Mapping[str, Any]) -> Any:
    """Return the current ``mcp.synthia`` entry, or ``None``."""
    section = data.get("mcp")
    return section.get("synthia") if isinstance(section, dict) else None


def skill_state(target: Path, source: Path) -> str:
    """Classify what occupies the skill path: absent, ours or foreign.

    A symlink named ``synthia`` pointing at any directory called
    ``skill`` is ours: the packaged path moves whenever the environment
    is rebuilt, so comparing it to the current source would make the
    installer refuse to refresh its own stale link.

    Args:
        target: Installed skill path, never followed as a symlink.
        source: Packaged skill directory Synthia would link to.

    Returns:
        ``"absent"``, ``"ours"`` or ``"foreign"``.
    """
    del source
    try:
        info = target.lstat()
    except (FileNotFoundError, NotADirectoryError):
        return "absent"
    if stat.S_ISLNK(info.st_mode):
        link = Path(os.readlink(target).rstrip("/\\"))
        return "ours" if link.name == "skill" else "foreign"
    if not stat.S_ISDIR(info.st_mode):
        return "foreign"
    manifest = target / "SKILL.md"
    if not manifest.is_file():
        return "foreign"
    text = manifest.read_text(encoding="utf-8", errors="replace")
    parts = text.split("---", 2)
    frontmatter = parts[1] if text.startswith("---") and len(parts) > 2 else ""
    return "ours" if SKILL_MARKER in frontmatter else "foreign"


def claude_user_entry(
    env: Mapping[str, str],
) -> tuple[Any, str | None]:
    """Return the user-scope ``synthia`` MCP entry, or ``None``.

    User scope is the top-level ``mcpServers`` key of ``~/.claude.json``.
    ``claude mcp get`` searches every scope, so a local or project entry
    would masquerade as a user-scope one; this reads user scope only, and
    never writes the file, which the Claude Code CLI owns.

    Args:
        env: Environment mapping used to locate the home directory.

    Returns:
        A ``(entry, error)`` pair; the entry is ``None`` when unset.
    """
    path = claude_config_path(env)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, None
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{path} could not be read ({exc})"
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    entry = servers.get("synthia") if isinstance(servers, dict) else None
    return entry, None


# --- I/O helpers -----------------------------------------------------------


def make_dir(path: Path) -> None:
    """Create a directory tree, forcing 0o700 on the leaf we create."""
    created = not path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if created:
        os.chmod(path, 0o700)


def backup_path(path: Path) -> Path:
    """Return the one-time backup location beside the real file."""
    real = Path(os.path.realpath(path))
    return real.with_name(real.name + BACKUP_SUFFIX)


def atomic_write(path: Path, text: str) -> None:
    """Replace a file atomically, keeping its mode and any symlink.

    Symlinked configs (dotfile managers) are followed, so the real file
    is rewritten instead of the link being replaced by a plain file.
    """
    real = Path(os.path.realpath(path))
    mode = real.stat().st_mode & 0o777 if real.exists() else 0o600
    handle, temporary = tempfile.mkstemp(dir=str(real.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, real)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def backup(path: Path) -> Path | None:
    """Back a file up once, beside the real file, before any write."""
    real = Path(os.path.realpath(path))
    destination = backup_path(path)
    if os.path.lexists(destination) or not real.is_file():
        return None
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    handle = os.open(destination, flags, 0o600)
    with os.fdopen(handle, "wb") as stream:
        stream.write(real.read_bytes())
    os.chmod(destination, 0o600)
    return destination


def remove_skill(target: Path) -> None:
    """Remove a skill path already proven to be Synthia's or forced."""
    if target.is_symlink() or not target.is_dir():
        target.unlink()
    else:
        shutil.rmtree(target)


def claude_available() -> bool:
    """Report whether the Claude Code CLI is on the path."""
    return shutil.which("claude") is not None


def run_claude(args: list[str]) -> tuple[int, str] | None:
    """Run the Claude Code CLI, or return ``None`` if it is unusable."""
    executable = shutil.which("claude")
    if executable is None:
        return None
    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.returncode, result.stdout + result.stderr


# --- Clients ---------------------------------------------------------------

Say = Callable[[str], None]


def install_skill(
    env: Mapping[str, str], force: bool, dry_run: bool, say: Say
) -> int:
    """Link (or copy) the packaged skill into ``~/.claude/skills``."""
    source = skill_source()
    target = skill_target(env)
    state = skill_state(target, source)
    if state == "foreign" and not force:
        say(
            f"skill: {target} exists and was not created by Synthia; "
            "refusing to touch it. Re-run with --force to replace it."
        )
        return 1
    linked = target.is_symlink()
    current = os.path.realpath(target) == os.path.realpath(source)
    if state == "ours" and linked and current:
        say(f"skill: already installed at {target}")
        return 0
    if dry_run:
        verb = "replace" if state == "foreign" else "refresh"
        verb = "link" if state == "absent" else verb
        say(f"skill: would {verb} {target} -> {source}")
        return 0
    if state != "absent":
        remove_skill(target)
    make_dir(target.parent)
    try:
        target.symlink_to(source, target_is_directory=True)
        say(f"skill: linked {target} -> {source}")
    except OSError:
        shutil.copytree(source, target)
        os.chmod(target, 0o700)
        say(f"skill: copied {source} -> {target}")
    return 0


def uninstall_skill(env: Mapping[str, str], dry_run: bool, say: Say) -> int:
    """Remove the skill, but only when Synthia owns it."""
    target = skill_target(env)
    state = skill_state(target, skill_source())
    if state == "absent":
        say(f"skill: nothing installed at {target}")
        return 0
    if state == "foreign":
        say(f"skill: {target} is not Synthia's; leaving it alone")
        return 0
    if dry_run:
        say(f"skill: would remove {target}")
        return 0
    remove_skill(target)
    say(f"skill: removed {target}")
    return 0


def manual_opencode(path: Path) -> str:
    """Return the snippet to paste when automatic editing is refused."""
    entry = json.dumps({"synthia": OPENCODE_ENTRY}, indent=2)
    body = "\n".join("    " + line for line in entry.splitlines())
    return f'  Add this by hand to "mcp" in {path}:\n{body}'


def write_opencode(path: Path, data: dict[str, Any], say: Say) -> int:
    """Back the config up once, then rewrite it atomically."""
    try:
        make_dir(path.parent)
        saved = backup(path)
        if saved is not None:
            say(
                f"opencode: backed up {path} to {saved} "
                "(it may hold credentials)"
            )
        atomic_write(path, json.dumps(data, indent=2) + "\n")
    except OSError as exc:
        say(f"opencode: cannot write {path} ({exc})")
        say(manual_opencode(path))
        return 1
    return 0


def install_opencode(path: Path, force: bool, dry_run: bool, say: Say) -> int:
    """Add ``mcp.synthia`` to OpenCode's config, preserving everything."""
    data, error = load_opencode(path)
    if data is None:
        say(f"opencode: {error}")
        say(manual_opencode(path))
        return 1
    existing = existing_mcp_entry(data)
    if existing == OPENCODE_ENTRY:
        say(f"opencode: already configured in {path}")
        return 0
    if existing is not None and not force:
        say(
            f"opencode: a different 'synthia' entry exists in {path}; "
            "refusing without --force"
        )
        say("    existing: " + json.dumps(existing, sort_keys=True))
        say("    synthia:  " + json.dumps(OPENCODE_ENTRY, sort_keys=True))
        return 1
    if dry_run:
        verb = "replace" if existing is not None else "add"
        say(f"opencode: would {verb} mcp.synthia in {path}")
        return 0
    data.setdefault("mcp", {})["synthia"] = dict(OPENCODE_ENTRY)
    status = write_opencode(path, data, say)
    if status == 0:
        say(f"opencode: wrote mcp.synthia to {path}")
    return status


def uninstall_opencode(path: Path, dry_run: bool, say: Say) -> int:
    """Drop ``mcp.synthia`` from OpenCode's config if it is untouched."""
    data, error = load_opencode(path)
    if data is None:
        say(f"opencode: {error}")
        return 1
    existing = existing_mcp_entry(data)
    if existing is None:
        say(f"opencode: no 'synthia' entry in {path}")
        return 0
    if existing != OPENCODE_ENTRY:
        say(
            f"opencode: the 'synthia' entry in {path} was modified; "
            "leaving it alone"
        )
        return 0
    if dry_run:
        say(f"opencode: would remove mcp.synthia from {path}")
        return 0
    del data["mcp"]["synthia"]
    status = write_opencode(path, data, say)
    if status != 0:
        return status
    say(f"opencode: removed mcp.synthia from {path}")
    saved = backup_path(path)
    if saved.is_file() and not saved.is_symlink():
        saved.unlink()
        say(f"opencode: deleted {saved}, which may hold credentials")
    return 0


def install_claude(
    env: Mapping[str, str], force: bool, dry_run: bool, say: Say
) -> int:
    """Register the MCP server at user scope through the Claude CLI."""
    entry, error = claude_user_entry(env)
    if error is not None:
        say(f"claude: {error}; register it yourself with:")
        say("    " + CLAUDE_ADD_COMMAND)
        return 1
    if entry == CLAUDE_ENTRY:
        say("claude: already registered at user scope")
        return 0
    if entry is not None and not force:
        say(
            "claude: a different user-scope 'synthia' server is "
            "registered; refusing without --force"
        )
        say("    existing: " + json.dumps(entry, sort_keys=True))
        say("    synthia:  " + json.dumps(CLAUDE_ENTRY, sort_keys=True))
        return 1
    if not claude_available():
        say("claude: CLI not found; skipping. Register it yourself with:")
        say("    " + CLAUDE_ADD_COMMAND)
        return 0
    if dry_run:
        verb = "replace" if entry is not None else "add"
        say(f"claude: would {verb} the user-scope 'synthia' MCP server")
        return 0
    if entry is not None:
        run_claude(["mcp", "remove", "synthia", "--scope", "user"])
    result = run_claude(
        [
            "mcp",
            "add-json",
            "--scope",
            "user",
            "synthia",
            json.dumps(CLAUDE_ENTRY),
        ]
    )
    if result is None or result[0] != 0:
        say("claude: the CLI failed; register it yourself with:")
        say("    " + CLAUDE_ADD_COMMAND)
        return 1
    say("claude: registered 'synthia' at user scope")
    return 0


def uninstall_claude(env: Mapping[str, str], dry_run: bool, say: Say) -> int:
    """Remove the user-scope MCP entry through the Claude Code CLI."""
    entry, error = claude_user_entry(env)
    if error is not None:
        say(f"claude: {error}; remove it yourself with:")
        say("    " + CLAUDE_REMOVE_COMMAND)
        return 1
    if entry is None:
        say("claude: no user-scope 'synthia' server registered")
        return 0
    if entry != CLAUDE_ENTRY:
        say("claude: the 'synthia' server was modified; leaving it alone")
        return 0
    if not claude_available():
        say("claude: CLI not found; remove it yourself with:")
        say("    " + CLAUDE_REMOVE_COMMAND)
        return 1
    if dry_run:
        say("claude: would remove the user-scope 'synthia' MCP server")
        return 0
    result = run_claude(["mcp", "remove", "synthia", "--scope", "user"])
    if result is None or result[0] != 0:
        say("claude: the CLI failed; remove it yourself with:")
        say("    " + CLAUDE_REMOVE_COMMAND)
        return 1
    say("claude: removed 'synthia' from user scope")
    return 0


# --- Entry point -----------------------------------------------------------


def run_all(
    env: Mapping[str, str],
    uninstall: bool,
    force: bool,
    dry_run: bool,
    say: Say,
) -> int:
    """Run every client action, returning the worst status.

    Args:
        env: Environment mapping locating the home and config trees.
        uninstall: Remove rather than install.
        force: Replace an unrecognised skill directory or MCP entry.
        dry_run: Report the work without performing it.
        say: Sink for the per-client report lines.

    Returns:
        The highest status any client returned.
    """
    config = opencode_config_path(env)
    if uninstall:
        return max(
            uninstall_skill(env, dry_run, say),
            uninstall_opencode(config, dry_run, say),
            uninstall_claude(env, dry_run, say),
        )
    return max(
        install_skill(env, force, dry_run, say),
        install_opencode(config, force, dry_run, say),
        install_claude(env, force, dry_run, say),
    )


def main(argv: list[str] | None = None) -> int:
    """Install or remove Synthia's skill and MCP registrations.

    Args:
        argv: Command line arguments, defaulting to ``sys.argv[1:]``.

    Returns:
        ``0`` when every client succeeded or needed no change.
    """
    parser = argparse.ArgumentParser(
        prog="synthia-install",
        description=(
            "One-time setup: install Synthia's Agent Skill and register "
            "the synthia-mcp server with Claude Code and OpenCode."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would change and write nothing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace an existing skill directory or MCP entry",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="remove the skill and both MCP entries",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress all output and report through the exit status only",
    )
    args = parser.parse_args(argv)

    if getattr(os, "geteuid", lambda: 1)() == 0:
        print(
            "synthia-install: refusing to run as root; a root install "
            "leaves root-owned files in your home directory.",
            file=sys.stderr,
        )
        return 1

    def say(message: str) -> None:
        if not args.quiet:
            print(message)

    env = os.environ
    say(f"environment: {sys.prefix}")
    say(f"server: {SERVER_COMMAND}")
    if find_spec("synthesizer") is None:
        say(
            "warning: cosmos-synthesizer is not importable in this "
            "environment. Synthia inspects Synthesizer in the process "
            "that runs the server, so its Synthesizer-specific tools "
            "will report that nothing is installed. Install Synthia "
            "into the same environment as your Synthesizer."
        )
    # Check every client before touching anything, so one client's
    # refusal cannot leave another half-configured.
    planned: list[str] = []
    status = run_all(env, args.uninstall, args.force, True, planned.append)
    if status != 0 or args.dry_run:
        for message in planned:
            say(message)
        if status != 0 and not args.dry_run:
            say("aborted: nothing was written")
        return status

    status = run_all(env, args.uninstall, args.force, False, say)
    say(
        "restart: MCP changes need a client restart (or /mcp in Claude "
        "Code). Skills load without one, unless ~/.claude/skills was "
        "created just now."
    )
    if args.uninstall:
        say(
            "note: removing the synthia package before running "
            "--uninstall orphans the skill symlink, which then has to "
            "be deleted by hand."
        )
    return status


if __name__ == "__main__":
    raise SystemExit(main())
