# Troubleshooting

Symptom → cause → fix. The *mechanisms* are explained in the other references;
this file routes you there rather than restating them. Everything here was
checked against real Synthesizer behaviour, but confirm against the installed
version with `inspect_synthesizer_api` before acting.

## Exceptions, by name

The strings users paste in, and what they usually mean:

| exception | usual cause | see |
|---|---|---|
| `MissingUnits` | a bare array passed to an `@accepts` constructor; the message names the **parameter's** expected unit, not the storage default | `units-and-data.md` |
| `InconsistentArguments` | mixing particle and parametric objects, or a bad `Instrument`/`Galaxy` argument combination | `parametric.md`, `observables.md` |
| `MissingLines` | an alias *string* like `"Hb"` passed to `get_lines`; it needs the full id | below |
| `MissingSpectraType` | the grid does not have that spectrum — often because it was loaded with `ignore_spectra=True` | `units-and-data.md` |
| `UnimplementedFunctionality` | `emitter="gas"`, or `CoordinateGenerator.generate_2D_Sersic` / `generate_3D_spline` | `emission-models.md` |
| `UnrecognisedOption` | `.shape` on a grid loaded with both `ignore_*` flags | `units-and-data.md` |
| `MissingInstrumentFile` | a premade instrument (`JWSTNIRCam()`) with no downloaded instrument cache | `observables.md` |
| `InconsistentAddition` | adding images whose resolution or FOV differ | `observables.md` |
| `PackageNotFoundError` | `importlib.metadata.version("synthesizer")` — the distribution is `cosmos-synthesizer` | `units-and-data.md` |

## Imports

**`ImportError: cannot import name 'Pipeline' from 'synthesizer'`** — it is not
top level. Use `from synthesizer.pipeline import Pipeline`. The wrong form
appears in Synthesizer's own `pipeline/pipeline.py` docstring *and* in
`docs/source/parallelism.rst`, so `search_documentation` will show it to you
twice; that is not corroboration.

**`ImportError` from `synthesizer.components` or `synthesizer.load_data`** —
both have empty `__init__.py` files. Import the submodule directly.

**A premade instrument name "does not exist"** — they are injected dynamically at
import, so no static tool can see them. Enumerate `AVAILABLE_INSTRUMENTS`.
See `observables.md`.

**An emission model name "does not exist"** — no `__all__`. Enumerate
`PREMADE_MODELS` *and* `DUST_GENERATORS`; they are disjoint. See
`emission-models.md`.

**A name in `PREMADE_MODELS` will not import** — the lists are hand-maintained
and drift. `EscapedEmission` is listed but no such class is exported. Enumerate
to get candidates, then confirm each one resolves.

## Particle versus parametric

**`AttributeError` for a method that should exist, or a constructor rejecting
sensible arguments** — you almost certainly imported the wrong `Stars`. The
name-by-name table is in `troubleshooting`'s companions: `particle.md` and
`parametric.md`. Check which branch the object came from first.

**`InconsistentArguments` from the top-level `galaxy()` factory** — it rejects
any non-`None` `gas`/`black_holes` beside a parametric `stars`, with no type
check, and the message misleadingly blames "particle based" objects. Build
`synthesizer.parametric.Galaxy` directly. See `parametric.md`.

## Emission models

**`KeyError: 'total'`** — with `fesc=0` and no dust emission model,
`TotalEmission` returns an `AttenuatedEmission` labelled `"attenuated"`, and
`PacmanEmission` labels itself `"attenuated"`. Read `model.label`, or pass
`label=` explicitly.

**A label you did not ask for, or a missing one** — eight premade names are
`__new__` factories returning a different concrete class per argument set, so
`isinstance` is unreliable and the label set moves. `ReprocessedEmission(grid)`
also produces `escaped`; `IntrinsicEmission(fesc=0)` is labelled
`_intrinsic_reprocessed`. Print `sorted(component.spectra)`. See
`emission-models.md`.

**Warnings about auto-created child models** — normal. Premade combination
models build their children and prefix the labels with an underscore.

**A component is zero** — check the model's mask before suspecting the grid.
Masks silently yield zero when nothing meets the threshold.

**`tau_v` or `fesc` ignored** — these default to a *string* naming an attribute
of the emitter, not a value. Pass a number for a fixed screen. See
`emission-models.md`.

## Grids

**File not found, naming a doubled extension like `..._grid.h5.hdf5`** — only
`.hdf5` is stripped from the name. `"test_grid"` and `"test_grid.hdf5"` are both
fine; `.h5` is not. Do not "fix" working code that passes `.hdf5`. See
`units-and-data.md`.

**A grid appears to have no lines or no spectra, or `.shape` raises** — it was
loaded with `ignore_spectra=True, ignore_lines=True`. Those flags skip loading;
they do not report file contents. **Use `inspect_local_grid`** to find out what
a grid really holds. This is the most consequential mistake in this file: it
turns "which lines does my grid have?" into a confident wrong answer.

**`spectra/nebular_continuum` is not in the file** — the nebular continuum
*spectrum* is computed as `nebular - linecont`. The *line* continuum
`lines/nebular_continuum` is a genuine dataset.

**Nebular, transmitted or reprocessed emission unavailable** — the grid was
never run through cloudy. Inspect it; do not assume.

## Lines

**`MissingLines` when the line obviously exists** — `get_lines` wants full ids.
The alias constants (`from synthesizer.emissions import Ha, Hb, O3b`) expand to
ids like `"H 1 4861.32A"`; the alias *string* `"Hb"` only works for indexing an
existing `LineCollection`. Note `O3` is one comma-composite id, so request `O3b`
and `O3r` separately if you want a ratio. See `examples/lines.py`.

**`.flux` is `None`** — call `get_flux(cosmo, z)` first, exactly as `Sed.fnu`
needs `get_fnu`. There is no `get_line_luminosities` method.

## Units

**Numbers wrong by orders of magnitude, no exception** — a bare value was
*assigned* to a `Quantity` attribute after construction, so it was taken to be
in the category default already (`ages = 10` means ten **years**). Constructors
decorated with `@accepts` would have raised `MissingUnits`; assignment does not.
See `units-and-data.md`.

**`obj._attr` does not match what was passed in** — it never will in general;
it is the converted value with units stripped.

**Changing `Units` had no effect** — it is a singleton, and changes do not
retroactively convert existing objects. See `units-and-data.md`.

**Edited the units YAML and nothing changed** — the effective file is the user's
`BASE_DIR/default_units.yml`, not the package copy.

## Observables

**Flux quantities missing or zero** — `fnu`/`flam` exist only after `get_fnu`.
Rest-frame work uses `lnu`/`llam` and the `*_lnu` / `*_luminosity` methods.

**`KeyError` indexing photometry by filter code** — the *component* method
returns a dict keyed by spectra label; only the `Sed` method is keyed by filter
code. `limit_to` needs a list, not a string. See `observables.md`.

**A network fetch you did not expect** — SVO filter codes and premade
instruments both download on first use. Offline alternatives are in
`examples/photometry.py`.

**Imaging fails or looks wrong** — parametric galaxies are `"smoothed"` only;
particle smoothed imaging needs smoothing lengths, a kernel and per-particle
photometry; angular FOV needs a redshift and cosmology. See `observables.md`.

## Performance

- Importing Synthesizer takes ~2 s and, on first import, creates directories and
  writes the default units file.
- Per-particle emission scales as particles x wavelengths — the usual cause of
  memory blow-ups. Use integrated emission unless resolved output is needed.
- To shrink a grid load, restrict the wavelength range or the spectra read — not
  the `ignore_*` flags, which leave you unable to inspect it.
- `nthreads > 1` raises without an OpenMP build; `check_openmp` reports.
- For many galaxies use `Pipeline`. See `examples/pipeline.py`.
