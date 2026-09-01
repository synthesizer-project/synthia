Synthia
^^^^^^^

Synthia is an agent companion for the `Synthesizer
<https://github.com/synthesizer-project/synthesizer>`_ Python package. It gives
existing agent hosts Synthesizer-specific guidance and local tools without
introducing another chat application or command interface.

Synthia ships an Agent Skill and a local MCP server. The server's tools inspect
the installed Synthesizer environment and API, list and describe local grids,
search the bundled guidance and examples, and statically validate generated
scripts. See :doc:`tools` for the exact surface.

Synthia downloads nothing. Every remote grid tool described in the plan is
unimplemented and blocked on a grid catalogue service that does not yet exist.
Anything marked planned here must not be treated as available.

Contents
^^^^^^^^

.. toctree::
   :maxdepth: 2

   installation
   tools
   architecture
   skill
   API

Contributing
^^^^^^^^^^^^

Please see `CONTRIBUTING.md
<https://github.com/synthesizer-project/synthia/blob/main/CONTRIBUTING.md>`_
for development setup, style, required checks and packaging guidance.
