# Synthia

Synthia is an agent companion for working with [Synthesizer](https://github.com/synthesizer-project/synthesizer). It is not designed as a replacement for a human user but aims to make learning and using Synthesizer easier.

Synthia bundles an Agent Skill with a local MCP server so Claude Code, OpenCode, and other MCP-capable agents can answer Synthesizer questions from the user's actual installation rather than inflating context and relying on incomplete local memory.

**Pre-alpha. Interfaces may change.**

## Installation

```bash
# Install into the SAME environment as cosmos-synthesizer.
# Synthia imports Synthesizer in its own process, so the interpreter
# running synthia-mcp is the one whose Synthesizer you get.
python -m pip install cosmos-synthia
synthia-install
```

`synthia-install` links the bundled skill at `~/.claude/skills/synthia` (which
OpenCode also loads, so one copy serves both clients), registers `synthia-mcp`
with Claude Code when the `claude` CLI is available, and adds it to
OpenCode's `~/.config/opencode/opencode.json`. `--dry-run` shows what it would
change, `--uninstall` reverses it. Restart your client afterwards: skills load
per session, but MCP servers only load at client start.

The installer is never required. The docs carry full manual instructions with
the exact paths and JSON for both clients.

## Usage

Synthia has no interface of its own. Once installed, ask your agent about
Synthesizer in plain language: the skill triggers on the subject matter, and
the agent calls the MCP tools when it needs an exact local fact.

### Claude Code

```bash
cd ~/my-analysis
claude
```

```text
> Compare the spectra of a parametric stellar population with little and with
> heavy dust attenuation, and plot them.
```

The agent loads the skill, calls `list_local_grids` and `inspect_local_grid`
to find a grid and confirm what it contains, `find_example` for the closest
canonical script, `inspect_synthesizer_api` for the exact signatures of the
emission model it plans to use, and `validate_script` before handing back the
result.

Check the wiring at any time:

```text
> Which Synthesizer is Synthia inspecting?
```

That calls `inspect_environment`, which reports the interpreter, the
environment and the installed Synthesizer version. If it says Synthesizer is
absent, Synthia was installed into a different environment from your
Synthesizer — see Installation.

### OpenCode

```bash
cd ~/my-analysis
opencode
```

OpenCode loads the same skill from `~/.claude/skills/synthia` and the same MCP
server, so the prompts are identical:

```text
> I have a SWIFT snapshot of star particles. Which Synthesizer workflow do I
> need, and why?
```

### Prompts that play to Synthia's strengths

- *"Does my local grid cover the metallicity range I need, and does it contain
  H-beta?"* — answered from the actual grid file, not from memory.
- *"Why is `spectra['total']` a KeyError after I built a TotalEmission model
  with fesc=0?"* — a documented Synthesizer trap.
- *"Show me what the grid's spectra look like at 10 Myr and Z=0.01."* —
  renders a figure and returns its path.
- *"Adapt this script to the Synthesizer version I actually have installed."*
  — signatures come from the installed source.

Synthia is at its most useful where an answer depends on your specific
installation: which version, which grids, which spectra those grids hold. It
is least useful for pure astrophysics questions, which the model can answer
without it.

## What works today

The MCP server exposes:

- `inspect_environment` — Python and Synthesizer versions, install path,
  platform, and set `SYNTHESIZER_*` variables. Does not import Synthesizer.
- `inspect_synthesizer_api` — signature, docstring, and `path:lineno` for a
  public dotted name in the installed Synthesizer.
- `list_local_grids` — the resolved grid directory and the grids in it.
- `inspect_local_grid` — a grid's axes, units, model metadata, and available
  spectra and line names, without loading the arrays.
- `search_documentation` — the bundled skill references, plus Synthesizer's
  own `docs/` when a source checkout is detected.
- `find_example` — the closest bundled canonical example.
- `plot_grid_spectra`, `plot_grid_lines`, `plot_grid_ionising_luminosity` —
  render a figure from a local grid and return the path written.
- `validate_script` — syntax, import availability, and referenced Synthesizer
  objects. It never runs the script.

Two boundaries are deliberate: `validate_script` does not execute code
(execution is left to the host's permission-gated shell tool), and
`inspect_synthesizer_api` resolves public dotted names through a controlled
import plus static attribute access, never `eval`.

## What is planned, not built

Everything to do with remote grids: `search_grids`, `describe_grid`,
`compare_grids`, `recommend_grid`, `download_grid`, `verify_grid`. **Synthia
downloads nothing.** These depend on a grid catalogue service that does not
exist yet — no URL, no auth model, no schema — so they are blocked rather than
merely unscheduled. See [PLAN.md](PLAN.md) for the intended end state.

## Compatibility

Developed and tested against `cosmos-synthesizer` 1.2.1.dev. Note the name
split: install `cosmos-synthesizer`, import `synthesizer`. Synthia does not
depend on Synthesizer and will not install it; it inspects whatever is there,
and says so plainly when nothing is.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,test]'
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full check list.

## Licence

GPLv3, matching Synthesizer. See [LICENSE](LICENSE).
