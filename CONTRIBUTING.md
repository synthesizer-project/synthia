# Contributing

Synthia follows Synthesizer's development and documentation standards.

## Development Environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,test,docs]'
pre-commit install
```

## Required Checks

```bash
ruff check .
ruff format --check .
pytest
make -C docs clean
make -C docs html SPHINXOPTS="-W --keep-going"
```

The docs build runs `python -m sphinx`, so it uses whichever interpreter is
active; activate the development environment first.

Most Synthesizer-specific tests skip when `cosmos-synthesizer` is not
importable. Run the suite a second time in an environment that has it, as CI
does, before claiming a change is covered:

```bash
pytest -q                     # Synthesizer absent
/path/to/synth-env/bin/pytest -q   # Synthesizer present
```

`pre-commit run --all-files` runs repository hygiene, linting, and formatting
checks together. CI runs the same checks, plus a wheel build.

## Python Style

- Follow PEP 8 and the repository Ruff configuration (79-character lines).
- Write Google-style docstrings for public modules, classes, methods, and
  functions.
- Use `snake_case` for variables and functions and `PascalCase` for classes.
- Add focused tests for non-trivial behaviour and bug fixes.

## Documentation

User-facing behaviour must be documented under `docs/source`, which is the
single source of truth for tool contracts and installation. `PLAN.md` records
design intent and open work only; do not restate tool behaviour there. Build
Sphinx with warnings treated as errors before submitting changes.

Bundled skill references and examples are product behaviour. Keep them concise,
version-aware, and tested where executable.

Do not document a tool as available before it is implemented. Anything blocked
on the remote grid catalogue service must stay explicitly marked as planned.

## Packaging: the skill must reach the wheel

Synthia's entire packaging story is that the bundled skill ships inside the
distribution. Everything under `src/synthia/skill/` — `SKILL.md`, every
reference, every example — must be present in the built wheel and resolvable
through `importlib.resources` after a clean install.

Hatchling ships every file under the selected package directory, so no
`package_data`, `MANIFEST.in`, or `force-include` is needed. There is one
sharp edge:

> **Hazard: `.gitignore` can silently eat the skill.** Hatchling's default
> file selection honours VCS ignore files. A broad pattern in `.gitignore` —
> `examples/`, `*.md`, `references/`, a bare `docs/` — will quietly drop
> matching skill files from the wheel. The package still imports, the tests
> still pass under an editable install, and users get a skill with holes in
> it. Before adding a `.gitignore` pattern, check it cannot match anything
> under `src/synthia/skill/`.

`tests/test_server.py` checks that `skill/SKILL.md` resolves, but under an
editable install that check passes trivially by reading the source tree; it
cannot catch a build-configuration regression. The wheel job in CI is the real
guard: it builds the distribution, installs it into a clean environment away
from the source tree, and asserts the packaged skill resources resolve. If you
change build configuration or `.gitignore`, verify locally too:

```bash
python -m pip install build   # not in any extra
python -m build
python -m venv /tmp/synthia-wheel-check
/tmp/synthia-wheel-check/bin/python -m pip install dist/*.whl
cd /tmp && /tmp/synthia-wheel-check/bin/python -c "
from importlib.resources import files
skill = files('synthia') / 'skill'
assert (skill / 'SKILL.md').is_file()
assert (skill / 'references' / 'concepts.md').is_file()
"
```

Run that check from outside the repository. Inside it, `src/` on the path can
mask a missing file.
