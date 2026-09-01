Architecture
************

Synthia combines one Agent Skill with one local MCP server:

.. code-block:: text

   Claude Code / OpenCode
        |            |
        |            +-- starts local synthia-mcp
        |                         |
        +-- loads skill           +-- inspect local Synthesizer
                                  +-- inspect local grids
                                  +-- search guidance and examples
                                  +-- validate scripts statically

Agent Skill
===========

The Agent Skill teaches the model Synthesizer's conceptual structure, workflow
selection, evidence hierarchy, and scientific constraints. It routes detailed
questions to focused references rather than placing the whole package API in
the model context.

Local MCP server
================

The MCP server provides version-specific facts from the user's own
installation: Python and Synthesizer versions and paths, signatures and
docstrings resolved from the installed package, and metadata for grids already
on disk. A hosted MCP server could not do any of this, which is why the server
is local.

The server is read-only with respect to the user's project. It writes nothing
outside Synthesizer's own initialisation side effect and the figures the plot
tools place under the system temporary directory, and it never executes user or model-generated code.
Script execution is delegated to the host's permission-gated shell tool.

Remote grid boundary
====================

Not implemented, and blocked on work outside this repository.

The grid catalogue is a separate service and the intended source of truth for
grid identifiers, versions, manifests, compatibility, provenance, citations,
licences, checksums, and download URLs. That service does not exist yet: no
URL, authentication model, or schema has been agreed, so nothing has been
built against it.

When it does exist, Synthia will consume its public API rather than embed a
second catalogue. Grid search and metadata will remain remote, while approved
downloads and checksum verification will happen locally. Until then Synthia
performs no grid search, no recommendation, and no downloading of any kind.

Non-goals
=========

Synthia does not provide its own model, chat interface, TUI, GUI, or
operational CLI. It also avoids client-specific plugins while standard Agent
Skills and MCP can satisfy the requirement.
