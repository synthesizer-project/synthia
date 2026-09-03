# Install Synthia

These instructions are for the coding agent reading this file. Install Synthia
for the user; do not merely describe the commands.

1. Use the Python environment containing the user's `cosmos-synthesizer`
   installation. Check with:

   ```bash
   python -c "import sys, synthesizer; print(sys.executable); print(synthesizer.__file__)"
   ```

   If this fails, ask which environment contains Synthesizer. Do not use
   `pipx`, `uv tool install`, `sudo`, or a separate environment: Synthia must
   import Synthesizer from the same environment.

2. Install Synthia and run its idempotent setup command:

   ```bash
   python -m pip install cosmos-synthia
   synthia-install
   ```

   The distribution is named `cosmos-synthia`; the import name is `synthia`.
   Install from `git+https://github.com/synthesizer-project/synthia.git`
   instead only if the user asks for an unreleased change.

3. Report the environment and server paths printed by `synthia-install`, plus
   any warnings or refusals. Do not use `--force` without asking the user: it
   can replace an existing skill or MCP configuration owned by them.

4. Tell the user to restart their agent client. After restart, verify the
   installation by asking Synthia's `inspect_environment` tool for the
   Synthesizer version and path.

`synthia-install --dry-run` previews changes. `synthia-install --uninstall`
removes the skill and MCP registrations; run it before uninstalling the Python
package.
