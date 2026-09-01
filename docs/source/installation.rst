Installation
************

Synthia is a normal Python distribution containing two cooperating parts: a
bundled Agent Skill and the ``synthia-mcp`` local MCP server. Installing
Synthia means installing the package, putting the skill where your agent host
finds skills, and registering the server with that host.

Install the package
===================

.. _same-environment:

.. important::

   **Install Synthia into the same Python environment as**
   ``cosmos-synthesizer``.

   Synthia reports on Synthesizer by importing it in its own process.
   The interpreter that runs ``synthia-mcp`` is therefore the
   interpreter whose Synthesizer you get: there is no second lookup
   path, no configured interpreter, and no search of other
   environments. If the server runs somewhere Synthesizer is not
   importable, every Synthesizer-specific tool correctly reports that
   nothing is installed.

   This rules out isolated tool installers such as ``uv tool install``
   and ``pipx``, which deliberately create an environment containing
   only Synthia. To keep Synthia out of your main science environment,
   make a dedicated one holding both:

   .. code-block:: bash

      python -m venv ~/.venvs/synthia
      ~/.venvs/synthia/bin/pip install cosmos-synthesizer cosmos-synthia
      ~/.venvs/synthia/bin/synthia-install

   You do not need to activate it afterwards. ``synthia-install``
   registers the absolute path of that environment's ``synthia-mcp``,
   so agent hosts start the right one from their own environment.

   Two things make the binding explicit rather than a matter of luck.
   ``synthia-install`` registers the **absolute path** of the
   ``synthia-mcp`` beside the interpreter that ran it, so the agent
   host cannot resolve a different one through its own ``PATH``; and it
   warns at install time when that environment has no Synthesizer.
   ``inspect_environment`` then reports the ``executable`` and
   ``environment`` actually in use, so a mismatch is visible rather
   than silent.

.. code-block:: bash

   # In the environment that already has cosmos-synthesizer:
   python -m pip install cosmos-synthia

To confirm the binding, ask the agent to call ``inspect_environment``
and check that ``environment`` is the environment you expect and
``synthesizer_version`` is the version you work with.

.. note::

   The distribution is ``cosmos-synthia`` but the import name is
   ``synthia``, mirroring ``cosmos-synthesizer`` and ``synthesizer``.
   The bare name ``synthia`` on PyPI belongs to an unrelated project.

   Until the first release, install from a checkout:

   .. code-block:: bash

      python -m pip install /path/to/synthia

``synthia-install`` records the absolute path of the ``synthia-mcp`` it
installed, so the executables do not need to be on your ``PATH``.

If you keep several Synthesizer environments, install Synthia into each one
and register the one you want per project, using the absolute path that
``synthia-install`` reports — see :ref:`manual-setup`.

Synthia does not depend on Synthesizer and does not install it. It inspects
whichever Synthesizer is importable in its own environment; if there is none,
the inspection tools say so rather than failing.

Automatic setup
===============

.. code-block:: bash

   synthia-install

``synthia-install`` is a one-time setup command with flags only and no
subcommands. It:

1. Links the bundled skill at ``~/.claude/skills/synthia``, falling back to
   a copy where symbolic links are unavailable. OpenCode loads that same
   path, so one installation serves both clients.
   OpenCode also loads skills from that location natively, so a single copy
   serves both clients.
2. Registers ``synthia-mcp`` with Claude Code using
   ``claude mcp add-json --scope user``.
3. Adds a ``synthia`` entry under the ``mcp`` key of OpenCode's
   ``~/.config/opencode/opencode.json``, writing the file atomically and
   preserving unrelated configuration.

Flags
-----

``--dry-run``
   Report every change that would be made and change nothing. Run this first
   if you keep hand-edited client configuration.

``--force``
   Replace something Synthia does not own: a foreign directory at the skill
   path, or an existing ``synthia`` server entry that differs from the one
   Synthia writes. Without it, either of those is reported and refused.

``--uninstall``
   Remove the installed skill and Synthia's client registrations, leaving the
   rest of each configuration file untouched. An entry you have since edited
   is reported and left alone rather than removed.

``--quiet``
   Suppress all output and report through the exit status only. Refusals are
   silent too, so use it only where the status is checked.

The installer is a convenience, never a requirement. Everything it does can be
done by hand, and managed or containerised environments should generally do it
by hand.

.. _manual-setup:

Manual installation
===================

Install the skill
-----------------

Locate the packaged skill and copy it to ``~/.claude/skills/synthia``:

.. code-block:: bash

   PKG=$(python -c "import synthia; print(synthia.__path__[0])")
   mkdir -p ~/.claude/skills
   rm -rf ~/.claude/skills/synthia
   cp -R "$PKG/skill" ~/.claude/skills/synthia

The directory must be named ``synthia`` and must contain ``SKILL.md`` at its
top level, alongside the ``references`` and ``examples`` directories.

Register the server with Claude Code
------------------------------------

The supported route is the Claude Code CLI:

.. code-block:: bash

   SERVER=$(python -c "import sys, pathlib; \
       print(pathlib.Path(sys.executable).parent / 'synthia-mcp')")
   claude mcp add-json --scope user synthia \
       "{\"type\": \"stdio\", \"command\": \"$SERVER\", \"args\": []}"

That writes a user-scope entry equivalent to the following in
``~/.claude.json``:

.. code-block:: json

   {
     "mcpServers": {
       "synthia": {
         "type": "stdio",
         "command": "/absolute/path/to/your/env/bin/synthia-mcp",
         "args": []
       }
     }
   }

If ``synthia-mcp`` is not on the ``PATH`` Claude Code inherits, give the
absolute path to the executable instead, for example
``"/path/to/.venv/bin/synthia-mcp"``.

Register the server with OpenCode
---------------------------------

Add a ``synthia`` entry under the ``mcp`` key of
``~/.config/opencode/opencode.json``, keeping any existing keys:

.. code-block:: json

   {
     "$schema": "https://opencode.ai/config.json",
     "mcp": {
       "synthia": {
         "type": "local",
         "command": ["/absolute/path/to/your/env/bin/synthia-mcp"],
         "enabled": true
       }
     }
   }

Note that OpenCode takes ``command`` as an argument list, while Claude Code
takes a command string plus separate arguments. Only the shape differs; both
start the same stdio server.

Restarting
==========

Skills are read from disk when a session starts, so an installed or updated
skill is picked up by the next session without restarting the client.

MCP servers are not. After adding, removing or changing Synthia's MCP
registration, restart Claude Code or OpenCode before the tools appear.

Verifying
=========

.. code-block:: bash

   synthia-mcp

The server starts a stdio MCP session and waits silently for a host to
connect. Silence is success; press ``Ctrl-C`` to stop it. ``synthia-mcp`` is
process plumbing for agent hosts, not a command interface, and it produces no
useful output when run by hand.

Inside an agent session, ask the agent to call ``inspect_environment``. It
returns your Python version, platform, and Synthesizer version and path, and
it does not import Synthesizer.

Compatibility
=============

Synthia is developed and tested against ``cosmos-synthesizer`` 1.2.1.dev. It
should work with nearby releases, since it reads the installed package's own
signatures and docstrings rather than a static symbol database, but only that
version is exercised.

Both packages separate their distribution name from their import name:
install ``cosmos-synthesizer`` and ``cosmos-synthia``; import ``synthesizer``
and ``synthia``. Synthia reports the version
from ``synthesizer.__version__`` when the module exposes one, and otherwise
from the ``cosmos-synthesizer`` distribution metadata, labelling which source
it used, because the two genuinely disagree in an editable checkout.

Development installation
========================

To work on Synthia itself, see `CONTRIBUTING.md
<https://github.com/synthesizer-project/synthia/blob/main/CONTRIBUTING.md>`_
for the environment, the required checks and the packaging rules.
