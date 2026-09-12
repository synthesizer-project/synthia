# Local Grids and Data Directories

What is on **this machine**: where Synthesizer keeps its files, how to load a
grid that is already there, and which version is installed. What the project
*publishes* is `data-catalogue.md`; the unit system is `units.md`.

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

## Loading a grid that is already here

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

## Getting a grid you do not have

Everything about the published catalogue — which grids exist, what they
contain, which release to pin, and how to download one — is in
`references/data-catalogue.md`. This file covers grids that are already on
this machine.

## Which version is installed

The distribution is named **`cosmos-synthesizer`** but imports as
`synthesizer`. Consequently `importlib.metadata.version("synthesizer")` **fails**.
Use `synthesizer.__version__`, or ask `inspect_environment`, which reports both
without importing the package.
