Agent Skill
***********

The bundled ``SKILL.md`` is Synthia's domain-guidance entry point. Claude Code
and OpenCode should share the same installed copy.

Evidence hierarchy
==================

Synthia should prefer:

#. The user's installed Synthesizer source and version.
#. Documentation and examples matching that version.
#. Curated Synthia references.
#. General model knowledge.

This ordering prevents plausible but obsolete API suggestions.

Progressive disclosure
======================

The entry-point skill remains concise. It directs the agent to focused
references for particle workflows, parametric workflows, emission models,
observables, units, and troubleshooting. Exact signatures are obtained through
runtime inspection rather than duplicated in static JSON.

Scientific behaviour
====================

Synthia must expose assumptions rather than silently choosing scientific
models. Where a choice of grid, emission model, or set of units changes the
result, the skill requires the agent to state the choice and its consequences
instead of quietly making one.

Grid recommendation is not implemented. When a grid catalogue service exists,
a recommendation must report relevant coverage, model choices, compatibility,
provenance, and alternatives rather than returning a single answer. Until
then, the skill directs the agent to the grids already on the user's machine
through ``list_local_grids`` and ``inspect_local_grid``, and Synthia neither
searches nor downloads remote grids. See :doc:`tools`.
