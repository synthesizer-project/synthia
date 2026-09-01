# Units, Grids and Data Directories

## Units: the `Quantity` descriptor

Synthesizer attaches units to almost every physical attribute using a `Quantity`
descriptor (`synthesizer.units`). The behaviour is specific and worth learning
properly, because getting it wrong produces wrong numbers rather than errors.

**Public attribute versus underscore attribute:**

- `obj.attr` returns a `unyt` array **with units attached**.
- `obj._attr` returns a **bare numpy array**, already converted to that
  `Quantity`'s own unit. On a stock install that is the default unit for the
  quantity's category, but `Quantity.__set_name__` overrides it if `Units` was
  given a per-attribute unit under that attribute's name, so check the
  configuration before assuming the category default.

`obj._attr` is *not* the raw value the user supplied or the value as stored in a
file. It is the converted value with the units stripped off. Use it for speed
and for plotting; never use it to reason about what the user passed in.

**Construction raises; assignment converts silently.** These are two different
mechanisms and they fail in opposite ways.

*Constructors and functions decorated with `@accepts(...)` raise* on a value
with no units. This is most of the emitter constructors, so the common beginner
mistake is caught:

```text
Stars(initial_masses=..., ages=np.full(3, 10.0), metallicities=...)
MissingUnits: ages is missing units! Expected to be in Myr (or equivalent).
```

Note the unit in that message is the **per-parameter unit the decorator
demands** (`Myr` for `ages`), which is not the same as the *category default*
that the value will be stored in (`yr` for time). Both are correct; they answer
different questions. Do not let the mismatch make you doubt the diagnosis — the
fix is simply to attach units.

*Assignment after construction does not raise.* Setting a public `Quantity`
attribute converts silently, and the object does not remember the input unit:

```text
s.ages = np.full(3, 10.0)      -> [10. 10. 10.] yr    (bare: assumed default)
s.coordinates = arr * kpc      -> stored as Mpc       (converted, not tagged)
```

Dimensionless input bypasses conversion entirely, and a bare value is assumed to
already be in the category default. So a bare `10` assigned to `ages` means ten
**years**, not ten Myr. This is the silent-error path: it produces wrong numbers
rather than an exception, and only assignment reaches it. Always attach units.

## Default unit categories

There are 17 categories (spatial, mass, time, wavelength, luminosity, the
luminosity and flux densities, velocity, temperature, angle, angular resolution,
frequency, and mass rate among them). Rather than trusting a copy of the values,
read the effective configuration: `BASE_DIR/default_units.yml`, whose path
`inspect_environment` reports. That file is the authority, and it is per-user
(see below).

## The `Units` singleton

`Units` is a **singleton**, enforced by a metaclass. Two consequences:

- Re-instantiating `Units(...)` with a new dictionary does **nothing**. It
  returns the existing instance. Overriding requires `force=True`, and doing so
  is explicitly discouraged in the source.
- Changing units does **not retroactively convert** quantities that already
  exist. Anything constructed before the change keeps its old numbers with new
  labels — which is worse than an error. Set units before building anything, or
  not at all.

The effective unit configuration is the **user's own copy**, written to
`BASE_DIR/default_units.yml` on first import — not the copy inside the installed
package. Editing the package copy has no effect. If a user reports units that do
not match the documentation, check their file.

## Data directories

On first import, Synthesizer runs an initialisation step that **creates
directories and writes the default units file**. Importing Synthesizer is
therefore not side-effect-free; `inspect_environment` deliberately does not
import it.

Top-level constants expose the locations: `BASE_DIR`, `DATA_DIR`, `GRID_DIR`,
`TEST_DATA_DIR`, `INSTRUMENT_CACHE_DIR`, `SVO_FILTER_CACHE_DIR`. Read them from
the installed package rather than hard-coding paths.

`$SYNTHESIZER_DIR` overrides `BASE_DIR`, which is where `default_units.yml`
lives and, when `$SYNTHESIZER_GRID_DIR` is unset, the parent of the grid
directory. Otherwise `BASE_DIR` is the platform user data directory for
"Synthesizer" (`~/Library/Application Support/Synthesizer` on macOS,
`~/.local/share/Synthesizer` on Linux).

The grid directory is `$SYNTHESIZER_GRID_DIR` if set, otherwise `grids` under
`BASE_DIR`. `$SYNTHESIZER_DATA_DIR`, `$SYNTHESIZER_TEST_DATA_DIR`,
`$SYNTHESIZER_INSTRUMENT_CACHE` and `$SYNTHESIZER_SVO_FILTER_CACHE` redirect the
rest. All are read at initialisation, so changing one and expecting an
already-imported session to notice will not work.

## Grids

A `Grid` is an HDF5 file, produced by the sister package **`syncretize`**.
Loading one:

- **Only a `.hdf5` extension is safe** on the name passed to `Grid`. The
  filename is built as `<grid_dir>/<name>.<ext>` where `ext` defaults to
  `"hdf5"`, and the name has `".hdf5"` stripped from it first. The
  extension-detection code is broken — it inspects the *last character* of the
  split extension rather than the extension itself, so it never updates `ext`.
  The consequence is narrow but real: `"test_grid"` and `"test_grid.hdf5"` both
  resolve correctly to `test_grid.hdf5`, while any other extension is **not**
  stripped and gets `.hdf5` appended on top of it —
  `"test_grid.h5"` becomes `test_grid.h5.hdf5` and fails to open. Pass the bare
  name, or `.hdf5` if the user wrote it that way; never pass `.h5`. (Grids with
  a genuine `.h5` filename cannot be loaded by name at all — rename them.)
- **`ignore_spectra=True, ignore_lines=True` is not a "metadata-only" mode you
  can inspect.** It gives you axes, axis units and model metadata and nothing
  else — it *destroys* exactly the information people reach for it to get:

  ```text
  g = Grid("test_grid", ignore_spectra=True, ignore_lines=True)
  g.available_spectra -> []          # not "none in the file" - none LOADED
  g.available_lines   -> []          # same
  g.shape             -> UnrecognisedOption: "The grid has neither spectra
                                              or lines associated with it."
  ```

  Answering "does this grid have H-beta?" from that mode gives the confidently
  wrong answer "no lines at all". Building a model on it raises
  `MissingSpectraType: The Grid does not contain the key 'incident'`.
  The keywords are `ignore_*` (there is no `read_spectra=False`), and they are
  for skipping arrays you will not use — e.g. `ignore_spectra=True` alone still
  loads all 254 lines of `test_grid`.
- Wavelength range can be truncated at load time, and specific spectra can be
  selected, which is the usual fix for a grid that will not fit in memory.

**To find out what a grid actually contains, call Synthia's
`inspect_local_grid`.** It reads the HDF5 keys directly and returns the real
axes, spectra keys and line identifiers without loading any arrays — which is
the thing `ignore_*` cannot do. Never answer a "does this grid have X" question
from a partially loaded `Grid` object.

A grid's axes, spectra keys and line IDs are **properties of that file**. A
stellar grid usually has age and metallicity, but may have more; AGN NLR/BLR
grids have entirely different axes.

**The `nebular_continuum` *spectrum* is computed, not stored.** For a
reprocessed grid it is derived as `nebular - linecont` after the spectra are
read, so there is no `spectra/nebular_continuum` dataset to look for. This is a
statement about spectra only: `lines/nebular_continuum` **is** a real dataset in
the file and is read directly into the grid's line continua. Neither is
available from a grid that was never run through cloudy.

"Reprocessed" means specifically "run through the photoionisation code cloudy".
A grid that is not reprocessed has incident spectra only, and every nebular,
transmitted, or reprocessed quantity is unavailable from it.

## What grids exist to download

Synthia has no grid-catalogue tool, but the installed package ships one:
`synthesizer/downloader/_data_ids.yml`, a 727-line YAML index of every
downloadable asset, needing no network to read. Its top-level sections are
`TestData`, `DustData`, `InstrumentData`, `GenerationData`, `ProductionGrids`,
`SVOFilterCache` and `SynferenceData`, each mapping a filename to a direct link.

So "which grid should I download?" is answerable offline: read that file from
the install path (`inspect_environment` gives it) and show the user the relevant
names. `synthesizer-download` is the entry point that fetches them, and running
it is a download — get approval first.

## Versions

The distribution is named **`cosmos-synthesizer`** but imports as
`synthesizer`. Consequently `importlib.metadata.version("synthesizer")` **fails**.
Use `synthesizer.__version__`, or ask `inspect_environment`, which reports both
without importing the package.
