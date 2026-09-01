MCP Tools
*********

Synthia's local MCP server exposes a small, task-oriented tool surface. This
page describes what each tool does, what it takes, what it returns, and where
its safety boundary lies.

Every tool is read-only with respect to the user's project. None of them
executes user or model-generated code, and none writes to the user's files
outside Synthesizer's own initialisation side effect, which is described
under :ref:`tool-boundaries`.

.. _tool-boundaries:

Safety boundaries
=================

Two boundaries matter more than the rest and are stated up front.

``validate_script`` never executes the script
   Validation is static: it parses the source, checks that the imports it
   names can be resolved in the active environment, and checks the
   Synthesizer objects it references. Running a script is delegated to the
   host's own permission-gated shell tool, where the user sees and approves
   the command. Synthia does not contain an executor.

``inspect_synthesizer_api`` never evaluates an expression
   The dotted name is validated as a sequence of plain, public, non-keyword
   identifiers rooted at ``synthesizer``, the longest importable module
   prefix is imported through :func:`importlib.import_module`, the resolved
   module is checked to live inside the installed Synthesizer package
   directory, and the remaining segments are walked with
   :func:`inspect.getattr_static`. Static attribute access means module
   ``__getattr__`` hooks, properties and other descriptors never run.
   Resolved objects are never called and never repr'd. Neither ``eval`` nor
   ``exec`` is used.

Docstrings, grid metadata and documentation text come from files the user did
not necessarily write, so tools return them inside an envelope that marks the
content as untrusted data rather than as instructions, records its source, and
caps its length.

.. _synthesizer-import-side-effect:

Synthesizer import side effect
==============================

Synthia never imports Synthesizer when Synthia itself is imported. The import
happens on the first call to a tool that needs it, and is then cached for the
life of the server process.

That first import costs roughly two seconds and has a filesystem side effect:
``synthesizer/__init__.py`` calls ``synth_initialise()``, which creates the
``base``, ``data``, ``grids``, ``instrument_cache`` and ``svo_filter_cache``
directories and writes or merges ``default_units.yml`` under the user's data
directory. It is idempotent and silent once those exist, but the first call in
a fresh environment does create them.

``inspect_environment`` deliberately avoids this. It answers from
:func:`importlib.util.find_spec` and distribution metadata only, so it is
cheap and free of side effects.

Available now
=============

Environment and API
-------------------

``inspect_environment()``
   Reports the Python version, platform, whether Synthesizer is installed, its
   version and install path, and any ``SYNTHESIZER_*`` environment variables
   that are set. Does not import Synthesizer.

   Because it does not import, ``synthesizer_installed`` means only that a
   module spec with a real file origin was found. It is not proof that
   Synthesizer imports successfully: a broken compiled extension, the most
   common real failure mode, is invisible to a spec lookup. Only the tools
   that import can report an import error.

   Only the ``SYNTHESIZER_*`` variables actually set are reported. Synthesizer
   resolves its directories as environment variable else platformdirs default,
   and resolving the defaults would mean importing the package.

``inspect_synthesizer_api(dotted_name)``
   Resolves a public dotted name such as ``synthesizer.grid.Grid`` in the
   installed Synthesizer and returns its object type, defining module,
   qualified name, signature, docstring, source location as ``path:lineno``,
   and the installed version together with where that version was read from.
   Source bodies are never returned, only locations.

   Names are capped at 200 characters and eight dot-separated segments; every
   segment must be a plain identifier that is neither a Python keyword nor
   underscore-prefixed; the first segment must be exactly ``synthesizer``.
   Private and dunder names are therefore unreachable, and so is anything
   created lazily by a module ``__getattr__`` or a property.

   Imports Synthesizer. See :ref:`synthesizer-import-side-effect`.

Local grids
-----------

``list_local_grids()``
   Reports the resolved grid directory and the grid files discoverable in it.

``inspect_local_grid(grid_name)``
   Returns a named local grid's axes, axis units, model metadata, and the
   spectra and line names it provides, without loading the grid arrays. It is
   metadata inspection, not data loading, so it stays cheap on multi-gigabyte
   grid files.

Guidance and code
-----------------

``search_documentation(query)``
   Searches the bundled skill references. It additionally searches
   Synthesizer's own ``docs/`` only when a Synthesizer source checkout is
   detected, because ``pip install`` does not ship Synthesizer's documentation
   or examples: they live outside its ``src/`` tree and never enter the wheel.
   Against a pip-installed Synthesizer, the bundled references are the only
   documentation Synthia can search.

``find_example(task)``
   Returns the closest bundled canonical example for a described task.

``validate_script(source)``
   Checks a script's syntax, whether its imports are available in the active
   environment, and whether the Synthesizer objects it references exist. It
   does not run the script. See :ref:`tool-boundaries`.

Figures
=======

These render a figure from a local grid and return the path written. They
exist so an agent can show a user a plot without writing and running a
plotting script. Synthesizer's own plotting helpers do the drawing, so the
output matches what the package produces natively.

Every figure is built by Synthia from declarative arguments, so no
model-supplied code is executed. Figures are written to one fixed directory
under the system temporary directory; **no tool accepts a destination path**,
because one that did would be a general filesystem primitive. Rendering
requires matplotlib, which Synthesizer already depends on; without it the
tools report that rather than failing.

``plot_grid_spectra(grid_name, spectra_types=None, point=None)``
   Draws a grid's spectra at one grid point. ``point`` maps axis names to
   values in each axis's own units, for example
   ``{"ages": 1e7, "metallicities": 0.01}``, and defaults to the centre of
   the grid. Unlike ``inspect_local_grid`` this reads the full spectra
   arrays, so it is slower.

``plot_grid_lines(grid_name, point=None, line_ids=None)``
   Draws the emission lines a grid holds at one grid point.

``plot_grid_ionising_luminosity(grid_name, ion="HI"|"HeII")``
   Draws the specific ionising luminosity surface over the grid's axes, the
   standard check on whether a grid covers the ionising output a study
   needs. Requires age and metallicity axes.

Planned, not implemented
========================

Every remote grid tool is unimplemented and unavailable:

- ``search_grids``
- ``describe_grid``
- ``compare_grids``
- ``recommend_grid``
- ``download_grid``
- ``verify_grid``

Synthia downloads nothing. These tools depend on a remote grid catalogue
service that does not yet exist; it has no URL, no authentication model and no
published schema. Synthia will consume that service's public API when it
exists rather than embed a second copy of the catalogue, so the work is
blocked on the service rather than merely unscheduled.

Do not treat these names as available, and do not write guidance, skill
references or examples that assume them.
