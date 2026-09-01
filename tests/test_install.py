"""Test the one-time Synthia installer.

Every test redirects ``HOME`` and ``XDG_CONFIG_HOME`` into ``tmp_path``
and stubs the Claude Code CLI, so the real machine is never touched.
"""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from synthia import install


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    """Redirect the home and config trees and stub the Claude CLI."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(install, "claude_available", lambda: False)
    monkeypatch.setattr(install, "run_claude", lambda args: None)
    return home


def seed_claude(entry):
    """Write a user-scope ~/.claude.json carrying the given entry."""
    path = install.claude_config_path(os.environ)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"mcpServers": {"synthia": entry}} if entry else {"mcpServers": {}}
    data["oauthAccount"] = {"unrelated": "preserved"}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def config_path():
    """Return the sandboxed OpenCode config path."""
    return install.opencode_config_path(os.environ)


def seed(data, mode=0o600):
    """Write an OpenCode config with the given contents and mode."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, indent=2)
    path.write_text(text, encoding="utf-8")
    os.chmod(path, mode)
    return path


def snapshot(root):
    """Return a mapping of every path under root to its contents."""
    tree = {}
    for base, _, names in os.walk(root):
        for name in names:
            path = os.path.join(base, name)
            tree[os.path.relpath(path, root)] = open(path, "rb").read()
        tree.setdefault(os.path.relpath(base, root), b"<dir>")
    return tree


def test_dry_run_writes_nothing(tmp_path):
    """Report planned work without touching the filesystem."""
    seed({"mcp": {}})
    before = snapshot(tmp_path)
    assert install.main(["--dry-run"]) == 0
    assert snapshot(tmp_path) == before


def test_fresh_install_writes_skill_and_opencode_entry(sandbox):
    """Create the skill link and the exact OpenCode entry shape."""
    assert install.main([]) == 0
    skill = sandbox / ".claude" / "skills" / "synthia"
    assert skill.is_symlink()
    assert (skill / "SKILL.md").is_file()
    data = json.loads(config_path().read_text())
    assert data["mcp"]["synthia"] == {
        "type": "local",
        "command": [install.SERVER_COMMAND],
        "enabled": True,
    }


def test_second_run_changes_nothing(capsys):
    """Report no change and leave the config byte-identical."""
    assert install.main([]) == 0
    capsys.readouterr()
    first = config_path().read_bytes()
    assert install.main([]) == 0
    assert config_path().read_bytes() == first
    output = capsys.readouterr().out
    assert "already installed" in output
    assert "already configured" in output


def test_unrelated_configuration_survives():
    """Preserve other MCP servers and unrelated top-level keys."""
    seed(
        {
            "mcp": {"other": {"type": "local", "command": ["other"]}},
            "unrelatedKey": {"secret": "k"},
        }
    )
    assert install.main([]) == 0
    data = json.loads(config_path().read_text())
    assert data["mcp"]["other"] == {"type": "local", "command": ["other"]}
    assert data["unrelatedKey"] == {"secret": "k"}
    assert set(data["mcp"]) == {"other", "synthia"}


def test_malformed_json_aborts_without_writing(capsys):
    """Abort on unparsable JSON and leave the file untouched."""
    path = seed('{"mcp": ')
    assert install.main([]) == 1
    assert path.read_text() == '{"mcp": '
    assert "line 1" in capsys.readouterr().out


def test_jsonc_comments_are_refused(capsys):
    """Refuse to round-trip a config carrying comments."""
    path = seed('{\n  // keep me\n  "mcp": {}\n}')
    original = path.read_text()
    assert install.main([]) == 1
    assert path.read_text() == original
    output = capsys.readouterr().out
    assert "a comment" in output
    assert '"synthia"' in output


def test_trailing_comma_is_refused():
    """Refuse a config using a trailing comma."""
    path = seed('{\n  "mcp": {},\n}')
    original = path.read_text()
    assert install.main([]) == 1
    assert path.read_text() == original


def test_file_mode_is_preserved_and_new_files_are_private():
    """Keep an existing 0600 file private, and create private files."""
    path = seed({"mcp": {}}, mode=0o600)
    assert install.main([]) == 0
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    path.unlink()
    (path.parent / (path.name + install.BACKUP_SUFFIX)).unlink()
    assert install.main([]) == 0
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_backup_is_written_once():
    """Back the config up before the first mutating write only."""
    path = seed({"mcp": {}})
    assert install.main([]) == 0
    saved = path.with_name(path.name + install.BACKUP_SUFFIX)
    assert json.loads(saved.read_text()) == {"mcp": {}}
    assert stat.S_IMODE(saved.stat().st_mode) == 0o600
    install.main([])
    assert json.loads(saved.read_text()) == {"mcp": {}}


def test_foreign_skill_directory_is_refused(sandbox, capsys):
    """Never replace a skill directory Synthia did not create."""
    skill = sandbox / ".claude" / "skills" / "synthia"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: synthia\n---\nmine\n")
    assert install.main([]) == 1
    assert (skill / "SKILL.md").read_text().endswith("mine\n")
    assert "--force" in capsys.readouterr().out
    assert install.main(["--force"]) == 0
    assert skill.is_symlink()


def test_stale_skill_copy_is_refreshed(sandbox):
    """Refresh a marked copy left behind by an earlier release.

    A copy is installed wherever symlinking fails, and by the manual
    instructions. Reporting "already installed" without checking its
    contents would strand that copy at an old version forever.
    """
    skill = sandbox / ".claude" / "skills" / "synthia"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: synthia\nmetadata:\n  package: synthia\n---\nstale\n"
    )
    assert install.skill_state(skill, install.skill_source()) == "ours"

    assert install.main([]) == 0

    assert "stale" not in (skill / "SKILL.md").read_text()
    assert (skill / "references" / "concepts.md").is_file()


def test_different_mcp_entry_needs_force(capsys):
    """Refuse to overwrite a dev-checkout entry without --force."""
    other = {"type": "local", "command": ["/dev/checkout/synthia-mcp"]}
    path = seed({"mcp": {"synthia": other}})
    assert install.main([]) == 1
    assert json.loads(path.read_text())["mcp"]["synthia"] == other
    assert "--force" in capsys.readouterr().out
    assert install.main(["--force"]) == 0
    assert json.loads(path.read_text())["mcp"]["synthia"] == (
        install.OPENCODE_ENTRY
    )


def test_uninstall_removes_only_synthia(sandbox):
    """Remove Synthia's skill and entry, leaving everything else."""
    seed({"mcp": {"other": {"type": "local", "command": ["o"]}}, "a": 1})
    assert install.main([]) == 0
    assert install.main(["--uninstall"]) == 0
    data = json.loads(config_path().read_text())
    assert "synthia" not in data["mcp"]
    assert data["mcp"]["other"] == {"type": "local", "command": ["o"]}
    assert data["a"] == 1
    assert not (sandbox / ".claude" / "skills" / "synthia").exists()


def test_uninstall_when_absent_is_a_noop(tmp_path):
    """Exit 0 and write nothing when there is nothing to remove."""
    before = snapshot(tmp_path)
    assert install.main(["--uninstall"]) == 0
    assert snapshot(tmp_path) == before


def test_uninstall_leaves_modified_entry_alone(capsys):
    """Warn instead of removing an entry the user has since edited."""
    other = {"type": "local", "command": ["mine"]}
    path = seed({"mcp": {"synthia": other}})
    assert install.main(["--uninstall"]) == 0
    assert json.loads(path.read_text())["mcp"]["synthia"] == other
    assert "modified" in capsys.readouterr().out


def test_xdg_config_home_is_honoured(tmp_path, monkeypatch):
    """Write under XDG_CONFIG_HOME when it is set."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert install.main([]) == 0
    assert (tmp_path / "xdg" / "opencode" / "opencode.json").is_file()


def test_existing_jsonc_file_is_preferred(tmp_path):
    """Target opencode.jsonc when it exists, never creating a rival."""
    directory = tmp_path / "config" / "opencode"
    directory.mkdir(parents=True)
    (directory / "opencode.jsonc").write_text("{}")
    (directory / "opencode.json").write_text("{}")
    assert install.opencode_config_path(os.environ).name == "opencode.jsonc"


def test_claude_cli_missing_is_skipped_with_instructions(capsys):
    """Never hand-edit ~/.claude.json when the CLI is unavailable."""
    assert install.main([]) == 0
    assert "mcp add-json --scope user synthia" in capsys.readouterr().out


def test_claude_conflicting_entry_needs_force(monkeypatch):
    """Refuse a foreign Claude Code entry, then replace it with --force."""
    seed_claude({"type": "stdio", "command": "/dev/checkout/other-mcp"})
    calls = []
    monkeypatch.setattr(install, "claude_available", lambda: True)
    monkeypatch.setattr(
        install, "run_claude", lambda args: calls.append(args) or (0, "")
    )

    assert install.main([]) == 1
    assert all(call[:2] != ["mcp", "add-json"] for call in calls)

    calls.clear()
    assert install.main(["--force"]) == 0
    assert ["mcp", "remove", "synthia", "--scope", "user"] in calls
    added = [call for call in calls if call[:2] == ["mcp", "add-json"]]
    assert json.loads(added[0][-1]) == install.CLAUDE_ENTRY


def test_claude_registration_is_idempotent(monkeypatch, capsys):
    """Skip the CLI add when the user-scope server already matches."""
    seed_claude(install.CLAUDE_ENTRY)
    monkeypatch.setattr(install, "claude_available", lambda: True)
    monkeypatch.setattr(
        install,
        "run_claude",
        lambda args: pytest.fail(f"unexpected CLI call: {args}"),
    )

    assert install.main([]) == 0
    assert "claude: already registered" in capsys.readouterr().out


def test_claude_local_scope_entry_does_not_block_user_scope(monkeypatch):
    """Register at user scope despite a local-scope entry of the same name.

    ``claude mcp get`` searches every scope, so a local entry would
    otherwise masquerade as a user-scope one and the install would
    silently no-op while reporting success.
    """
    path = install.claude_config_path(os.environ)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "projects": {
                    "/some/project": {
                        "mcpServers": {
                            "synthia": {
                                "type": "stdio",
                                "command": "synthia-mcp",
                            }
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setattr(install, "claude_available", lambda: True)
    monkeypatch.setattr(
        install, "run_claude", lambda args: calls.append(args) or (0, "")
    )

    assert install.main([]) == 0
    assert any(call[:2] == ["mcp", "add-json"] for call in calls)


def test_claude_config_is_never_written(monkeypatch):
    """Leave ~/.claude.json to the Claude Code CLI."""
    path = seed_claude(None)
    before = path.read_bytes()
    monkeypatch.setattr(install, "claude_available", lambda: True)
    monkeypatch.setattr(install, "run_claude", lambda args: (0, ""))

    assert install.main([]) == 0
    assert path.read_bytes() == before


def test_root_is_refused(monkeypatch, capsys):
    """Refuse to install as root."""
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    assert install.main([]) == 1
    assert "root" in capsys.readouterr().err


def test_one_client_refusal_writes_nothing_anywhere(tmp_path, capsys):
    """Abort the whole install when any client refuses.

    The clients are configured in sequence, so without a planning pass
    first, a refusal from a later client would leave an earlier one
    half-configured.
    """
    seed("{ this is not json")
    before = snapshot(tmp_path)

    assert install.main([]) == 1

    assert snapshot(tmp_path) == before
    assert "aborted: nothing was written" in capsys.readouterr().out


def test_server_command_pins_the_installing_environment():
    """Register an absolute path, not a name resolved against PATH.

    Synthia imports Synthesizer in the process running the server, so
    the registered command decides which Synthesizer the user sees.
    Agent hosts start it from their own login environment, where a bare
    name could resolve to an unrelated installation.
    """
    command = install.server_command()

    assert Path(command).is_absolute(), command
    assert Path(command).parent == Path(sys.executable).parent
    assert install.CLAUDE_ENTRY["command"] == command
    assert install.OPENCODE_ENTRY["command"] == [command]


def test_install_warns_when_synthesizer_is_absent(capsys, monkeypatch):
    """Say so when the chosen environment has no Synthesizer."""
    monkeypatch.setattr(install, "find_spec", lambda name: None)

    assert install.main(["--dry-run"]) == 0

    output = capsys.readouterr().out
    assert "cosmos-synthesizer is not importable" in output
