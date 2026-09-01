# Synthesizer Concepts

The conceptual map. Nothing here is a substitute for `inspect_synthesizer_api`;
this file explains what the pieces *are* and why they are separate, so you can
choose the right ones. Exact signatures come from the installed source.

## The chain

```text
emission grid          pre-computed spectra/lines on a parameter space
      +
galaxy components      Stars, Gas, BlackHoles - the "emitters"
      |
emission model         a network describing how emission is made and altered
      |
emissions              Sed (spectra) and LineCollection (lines), rest frame
      +
observatory            Filter / FilterCollection / Instrument
      |
observables            photometry, spectroscopy, images, spectral data cubes
      |
Pipeline               the whole chain applied to many galaxies at once
```

Each arrow is a deliberate boundary. Emissions know nothing about telescopes;
instruments know nothing about stellar populations. Keeping the two vocabularies
apart is most of what it takes to reason correctly about a Synthesizer script.

## Emission grids

A `Grid` is an HDF5 file holding spectra and/or emission lines tabulated over a
parameter space. For a stellar grid the axes are usually age and metallicity,
but **axes are grid-specific** — a grid may add ionisation parameter, hydrogen
density, alpha enhancement, or something else entirely. Black hole grids
(NLR/BLR) have their own axes.

A grid built by running the incident spectra through the photoionisation code
**cloudy** is called *reprocessed*, and carries nebular emission. A grid that is
not reprocessed has only incident stellar spectra, and any request for nebular,
transmitted, or reprocessed emission from it will fail.

Grids are produced by the sister package **`syncretize`**, not by Synthesizer
itself. Never assume a grid contains an axis, a spectrum key, or a line ID; call
`inspect_local_grid`.

## Galaxy components and emitters

The emitting components are **stars**, **gas** and **black holes**. A galaxy is
a container that holds components plus galaxy-wide properties such as redshift
and centre. Components are usable on their own — you do not need a galaxy to get
a stellar spectrum, and much of the API lives on the component
(`galaxy.stars.get_spectra(...)`) rather than on the galaxy.

Gas currently acts as an attenuating medium (line-of-sight optical depths)
rather than as an emitter in its own right.

## Particle versus parametric

This is the fork in the road. Both branches define `Stars` and `Galaxy` with the
same names in different packages, and mixing them raises errors or, worse,
produces something misleading.

- **Particle** (`synthesizer.particle`): discrete resolution elements, each with
  its own mass, age, metallicity, and usually coordinates. This is what a
  hydrodynamic simulation gives you. Supports gas, black holes, line-of-sight
  attenuation, SPH-smoothed imaging, and per-particle emission.
- **Parametric** (`synthesizer.parametric`): a binned or analytic description —
  a star formation history and metallicity distribution defining a mass
  distribution over the grid's age/metallicity axes (an "SFZH"), plus an
  optional analytic morphology for imaging.

A parametric `Stars` object is defined *on the grid's own axes*, which is why
it is constructed from `grid.log10ages` and `grid.metallicities`. A particle
`Stars` object is independent of the grid and is interpolated onto it at
extraction time.

See `particle.md` and `parametric.md`.

## Emission models

An `EmissionModel` is a node in a directed network. Each node does one of a
small number of operations:

- **extract** a named spectrum straight from the grid (e.g. `incident`),
- **generate** emission from a model rather than a grid (e.g. dust emission,
  or a fixed template),
- **transform** another node's emission (e.g. apply a dust attenuation curve,
  or an IGM transmission),
- **combine** several nodes by summation.

Composing these gives the standard emission ladder, and Synthesizer ships
premade models for the common combinations. Every model declares an **emitter**
saying which component it applies to. See `emission-models.md`.

## Emissions

Applying an emission model to an emitter produces:

- `Sed` — a spectral energy distribution. Rest-frame quantities are `lnu`
  (luminosity density per frequency) and `llam` (per wavelength). Observer-frame
  quantities `fnu`/`flam` only exist after fluxes are computed, which requires a
  cosmology and a redshift, and optionally an IGM attenuation model.
- `LineCollection` — emission line luminosities (and continuum values) for a set
  of line IDs.

Results are stored on the emitter keyed by the emission model's label, so a
single call to get spectra typically populates several labels at once, not just
the one you asked for.

## Observatories

A `Filter` is a transmission curve; a `FilterCollection` is a set of them.
Filters can come from the SVO service by filter code (which downloads and caches
them), from a top-hat definition, or from arbitrary arrays.

An `Instrument` bundles filters and/or a wavelength array with optional
resolution, PSFs, noise and depth. Synthesizer ships premade instruments for
common facilities. What an instrument *is* determines what it can do: filters
alone give integrated photometry; filters plus a spatial resolution give
imaging; a wavelength array gives spectroscopy; a wavelength array plus a
spatial resolution gives a spectral data cube.

## Observables

- **Photometry** — a `Sed` integrated through filter transmission curves.
  Luminosity photometry comes from `lnu`; flux photometry comes from `fnu` and
  therefore requires fluxes to have been computed first.
- **Spectroscopy** — an emission resampled onto an instrument's wavelength
  array, optionally with instrumental broadening.
- **Imaging** — `Image` and `ImageCollection`, built from photometry plus
  spatial information. Parametric galaxies image via an analytic morphology;
  particle galaxies image as a histogram or smoothed over an SPH kernel.
- **Spectral data cubes** — `SpectralCube`, the spatial and spectral axes
  together.

## Pipeline

`Pipeline` runs the same emission model and instrument set over many galaxies
and writes the results to a single HDF5 file, with threading and MPI support. It
is the right tool the moment the question becomes "and now for ten thousand
galaxies". It is **not** exported at the top level of `synthesizer` — see
`troubleshooting.md`.

## Standard emission labels

These names appear as spectra keys, emission model labels, and grid dataset
names. They mean specific, different things:

| label | meaning |
|---|---|
| `incident` | the pure stellar (or AGN disc) emission before any reprocessing |
| `transmitted` | incident emission that passed through the nebula, minus what was absorbed |
| `nebular` | emission produced by the nebula: lines plus nebular continuum |
| `linecont` | the line contribution to the nebular spectrum (this is the grid dataset name; the emission model that produces it is labelled `nebular_line`) |
| `nebular_continuum` | the nebular continuum, i.e. `nebular` minus `linecont` |
| `escaped` | incident emission that escaped the birth cloud unprocessed |
| `reprocessed` | `transmitted` + `nebular`: everything the nebula did |
| `intrinsic` | emission before dust attenuation (`reprocessed` + `escaped`) |
| `attenuated` | intrinsic emission after dust attenuation |
| `emergent` | what leaves the galaxy: `attenuated` + `escaped` |
| `total` | `emergent` + dust emission, when a dust emission model is present |

Escape fraction (`fesc`) splits incident emission into the part that reaches the
nebula and the part that escapes it directly. With `fesc = 0` there is no
`escaped` component and `emergent` collapses onto `attenuated`.
