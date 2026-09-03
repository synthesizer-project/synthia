# Synthia

[![Contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/synthesizer-project/synthia/blob/main/CONTRIBUTING.md)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

<img alt="synthia_logo" src="https://github.com/user-attachments/assets/49c685bd-69d8-4b65-bba1-d78c4813e76d" align="right" width="140px"/>


Synthia is an agent companion for working with [Synthesizer](https://github.com/synthesizer-project/synthesizer). 

Synthia bundles an Agent Skill with a local MCP server so Claude Code, OpenCode, and other MCP-capable agents can answer Synthesizer questions from the user's actual installation rather than inflating context and relying on incomplete local memory. Note that it is not designed as a replacement for a human user but simply aims to make learning and using Synthesizer a frictionless experience. For more on these mechanisms see the [MCP documentation](https://modelcontextprotocol.io/docs/2026-07-28/getting-started/intro) and, for Agent Skills, [agentskills.io](https://agentskills.io/home).

## Installation

Synthia requires Synthesizer to be installed first. You'll need to install Synthia in the same environment containing Synthesizer, and you'll need to launch your agent from that same environment.

For agent-assisted installation, send your coding agent this prompt:

```text
Read <https://raw.githubusercontent.com/synthesizer-project/synthia/main/INSTALL.md and install Synthia for me.
```

Or install it directly (which is essentially all the install prompt does):

```bash
pip install 'git+https://github.com/synthesizer-project/synthia.git'
synthia-install
```

### In case you care what the install does...

`synthia-install` links the bundled skill at `~/.claude/skills/synthia` (which
OpenCode also loads, so one copy serves both clients), registers `synthia-mcp`
with Claude Code when the `claude` CLI is available, and adds it to
OpenCode's `~/.config/opencode/opencode.json`. `--dry-run` shows what it would
change, `--uninstall` reverses it. Restart your client afterwards: skills load
per session, but MCP servers only load at client start.

## Usage

Synthia has no interface of its own. Once installed, ask your agent about
Synthesizer in plain language: the skill triggers on the subject matter, and
the agent calls the MCP tools when it needs an exact local fact or a support operation.

```bash
cd ~/my-analysis
claude # or opencode
```

```text
> Compare the spectra of a parametric stellar population with little and with
> heavy dust attenuation, and plot them.
```

### What sort of thing can Synthia help with?

- _"Do any of my local grids cover the metallicity range I need, and do they contain H-beta?"_ — answered from the actual grid files you have, not from memory and without delving into the online documentation.
- _"Why is `spectra['total']` a KeyError after I built a TotalEmission model with fesc=0?"_ — a documented Synthesizer emission model initialisation trap.
- _"Show me what my BPASS v2.2.1 grid's spectra look like at 10 Myr and Z=0.01."_ — renders a figure with known plotting methods and returns its path.
- _"Adapt this script to the Synthesizer version I actually have installed."_ — take outdated scripts and update them for your specific Synthesizer install.
- _"Generate a young and old galaxy with black holes and produce plots showing whether JWST can detect the AGN contribution for a set of reasonable redshifts and galaxy properties."_ — render a complex astrophysics question by applying its knowledge of the local installation and available grids without the need to build up the quick script yourself.

Synthia is at its most useful where an answer depends on your specific installation: which version, which grids, which spectra those grids hold. It is least useful for pure astrophysics questions not specific to Synthesizer, which the model can answer without it.

## Performance

The benchmarks directory contains a series of 30 tests for common Synthia prompts. These were run on a bare agent (i.e. no plugins, MCPs, or skills) using Sonnet 5 with and without Synthia. Below is a comparison of the usage and runtime.

| metric | baseline | synthia | change |
|---|---|---|---|
| total cost | $11.30 | $8.22 | −27% |
| total wall time | 3682 s | 2174 s | −41% |
| source read | 954 kB | 92 kB | −90% |
| cache-read tokens | 21.5 M | 14.9 M | −31% |
| turns | 443 | 341 | −23% |

Note that all baseline and Synthia prompts produced "correct" and/or runnable outputs. 

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development workflow.

## Licence

[GNU General Public License v3.0](LICENSE).
