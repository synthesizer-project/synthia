# Synthia

Synthia is an agent companion for working with [Synthesizer](https://github.com/synthesizer-project/synthesizer). It is not designed as a replacement for a human user but aims to make learning and using Synthesizer easier.

Synthia bundles an Agent Skill with a local MCP server so Claude Code, OpenCode, and other MCP-capable agents can answer Synthesizer questions from the user's actual installation rather than inflating context and relying on incomplete local memory.

**Pre-alpha. Interfaces may change.**

## Installation

Synthia requires Synthesizer to be installed first. You'll need to install
Synthia in the same environment containing Synthesizer, and you'll need to launch your agent from that same environment.

For agent-assisted installation, send your coding agent this prompt:

> Read <https://raw.githubusercontent.com/synthesizer-project/synthia/main/INSTALL.md and install Synthia for me.

Or install it directly (which is essentially all the install prompt does):

```bash
pip install 'git+https://github.com/synthesizer-project/synthia.git'
synthia-install
```

`synthia-install` links the bundled skill at `~/.claude/skills/synthia` (which
OpenCode also loads, so one copy serves both clients), registers `synthia-mcp`
with Claude Code when the `claude` CLI is available, and adds it to
OpenCode's `~/.config/opencode/opencode.json`. `--dry-run` shows what it would
change, `--uninstall` reverses it. Restart your client afterwards: skills load
per session, but MCP servers only load at client start.

## Usage

Synthia has no interface of its own. Once installed, ask your agent about
Synthesizer in plain language: the skill triggers on the subject matter, and
the agent calls the MCP tools when it needs an exact local fact.

```bash
cd ~/my-analysis
claude # or opencode
```

```text
> Compare the spectra of a parametric stellar population with little and with
> heavy dust attenuation, and plot them.
```

Check the wiring at any time:

```text
> Which Synthesizer is Synthia inspecting?
```

### What sort of thing can Synthia help with?

- _"Does my local grid cover the metallicity range I need, and does it contain
  H-beta?"_ — answered from the actual grid file, not from memory.
- _"Why is `spectra['total']` a KeyError after I built a TotalEmission model
  with fesc=0?"_ — a documented Synthesizer trap.
- _"Show me what the grid's spectra look like at 10 Myr and Z=0.01."_ —
  renders a figure and returns its path.
- _"Adapt this script to the Synthesizer version I actually have installed."_
  — signatures come from the installed source.
- "Generate a young and old galaxy with black holes and produce plots showing whether JWST can detect the AGN contribution for a set of reasonable redshifts and galaxy properties." — a complex astrophysics question that Synthia can help with by applying its knowledge of the local installation and available grids.

Synthia is at its most useful where an answer depends on your specific
installation: which version, which grids, which spectra those grids hold. It
is least useful for pure astrophysics questions, which the model can answer
without it.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development workflow.

## Licence

See [GNU General Public License v3.0](LICENSE).
