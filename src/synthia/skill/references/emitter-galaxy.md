# The Galaxy Container

`Galaxy` holds components and coordinates work across them. It is an emitter
in its own right, but only for **combination**: a galaxy node cannot extract
grid spectra and cannot work per-particle.

Both branches exist and are not interchangeable:

- `synthesizer.parametric.Galaxy(stars=None, name=..., black_holes=None, redshift=None, centre=None, **kwargs)`
  — note there is **no `gas` argument**.
- `synthesizer.particle.Galaxy(name=..., stars=None, gas=None, black_holes=None, redshift=None, centre=None, **kwargs)`

The top-level `galaxy()` factory dispatches on the type of `stars`, but
**rejects a parametric black hole**: given parametric `stars` it raises
`InconsistentArguments` if `gas` or `black_holes` is not `None`, with no type
check, and the message misleadingly blames "particle based" objects. Construct
`synthesizer.parametric.Galaxy` directly instead. See `parametric.md`.

Confirm signatures with `inspect_synthesizer_api` before writing code.

## Components and where emission lands

Components hang off the galaxy as `galaxy.stars`, `galaxy.gas` and
`galaxy.black_holes`; a component you did not supply is `None`. Check before
using one.

There are two places spectra can end up, and they are different dicts:

- `galaxy.stars.get_spectra(model)` fills **`galaxy.stars.spectra`**;
- `galaxy.get_spectra(galaxy_model)` fills **`galaxy.spectra`**.

A galaxy-level call needs a `GalaxyEmissionModel` whose `combine=` names
component-level nodes. Handing a stellar model to `galaxy.get_spectra` is not
the same operation as calling it on `galaxy.stars`, and the results live in
different places. `get_spectra_combined` exists for the common case of summing
what the components already produced.

`redshift` lives on the galaxy and is required for anything observer-frame —
fluxes, observed-frame photometry, angular sizes. Emissions are rest-frame and
instrument-free until you ask for observables; see `observables.md`.

## Cross-component work

These are the operations that justify the container existing, and they are
easy to reimplement badly by hand:

- **Line-of-sight attenuation**: `get_stellar_los_tau_v`,
  `get_black_hole_los_tau_v` — compute per-particle optical depths from the
  gas distribution and attach them to the emitter (particle only).
- **Integrated properties**: `calculate_integrated_stellar_properties`,
  `calculate_integrated_gas_properties`,
  `calculate_black_hole_metallicity`, `get_surviving_mass`.
- **Dust prescriptions**: `calculate_dust_to_metal_vijayan19`,
  `calculate_dust_screen_gamma` (particle only).
- **Orientation**: `rotate_face_on`, `rotate_edge_on`, `rotate_particles`
  (particle only) — these move every component together.
- **Observables**: `get_photo_lnu`, `get_photo_fnu`, `get_lines`,
  `get_observed_spectra`, `get_observed_lines`, `get_images_luminosity`,
  `get_images_flux`, `get_data_cube`, `get_spectroscopy`.
- **Maps** (particle only): `get_map_stellar_mass`, `get_map_sfr`,
  `get_map_ssfr`, `get_map_stellar_age`, `get_map_gas_metallicity` and
  siblings.
- **Housekeeping**: `clear_all_spectra`, `clear_all_emissions`,
  `clear_all_photometry`, `print_used_parameters`.

`print_used_parameters` is the fastest honest answer to "what did this model
actually assume", and it exists on every emitter, not just the galaxy.

## Checklist before writing a galaxy script

1. Particle or parametric? The components must all come from the same branch.
2. Which components does the task actually need? Do not attach gas unless the
   optical depth should come from its distribution (`emitter-gas.md`).
3. Component-level or galaxy-level emission? That decides which `spectra`
   dict holds the answer.
4. Is `redshift` needed? Anything observer-frame requires it and a cosmology.
