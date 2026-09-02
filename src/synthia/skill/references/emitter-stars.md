# The Stars Emitter

`Stars` is the emitter almost every task uses. Pick the branch first
(`parametric.md` or `particle.md`); this file describes what the object
**carries**, because emission models read their parameters off it.

Confirm every signature with `inspect_synthesizer_api` before writing code.

## What you pass in

`synthesizer.parametric.Stars` is defined by distributions over a grid's axes:

- `log10ages` and `metallicities` — the **grid axes**, normally passed straight
  from `grid.log10ages` and `grid.metallicities`, not values of your own.
- `sf_hist` — an `SFH.*` object, or a precomputed array.
- `metal_dist` — a `ZDist.*` object, or a precomputed array.
- `initial_mass` — the total mass formed. Needs mass units.
- `sfzh` — supply the 2D age/metallicity grid directly instead of
  `sf_hist`/`metal_dist`.
- `morphology` — a `Sersic2D`, `Gaussian2D` or `PointSource` for imaging.
- `fesc`, `fesc_ly_alpha` — escape fractions, if you want them fixed on the
  emitter rather than on the model.

`synthesizer.particle.Stars` is defined by per-particle physical properties,
independent of any grid:

- `initial_masses`, `ages`, `metallicities` — required, and unit-bearing where
  the category has units.
- `tau_v` — per-particle optical depths, accepted **at construction**.
- `coordinates`, `velocities`, `smoothing_lengths`, `centre`,
  `current_masses`, `softening_lengths` — needed for line-of-sight
  attenuation, smoothed imaging and radial measurements. Without coordinates
  and smoothing lengths those operations cannot run.
- `redshift`, `alpha_enhancement`, `metallicity_floor`, `fesc`,
  `fesc_ly_alpha`.

Both constructors accept `**kwargs`, so a misspelled keyword is **silently
absorbed** rather than rejected. Check the attribute exists after construction.

## What emission models read off it

Model parameters that are strings name attributes on the emitter and are
resolved at extraction time — `tau_v="tau_v"`, `fesc="fesc"` and so on. The
full precedence chain is in `model-parameters.md`. The consequence here:

- a per-particle `tau_v` array gives per-particle attenuation;
- a number passed on the model imposes one uniform screen for every particle;
- an arbitrary attribute you attach yourself (`stars.my_tau_v = 0.3`) is
  usable by any model parameter that points at that name.

Resolved values are cached under
`stars.model_param_cache[model.label][parameter]`, which is the honest way to
check what a model actually used.

## Where the output goes

`stars.get_spectra(model)` fills `stars.spectra`, a dict keyed by **model
label**. Read `sorted(stars.spectra)` after the first run rather than
predicting the keys — premade models emit labels you did not ask for, and
underscore-prefixed internal ones. See `emission-models.md`.

The `Sed` objects in that dict carry `lam`, `lnu`, `llam`, and `fnu`/`flam`
**only after** `get_fnu`. A `Sed` has **no `label` attribute** — the label is
the dict key, not a property of the spectrum.

## Useful derived quantities

Both branches offer weighted summaries rather than hand-rolled averages:
`get_mass_weighted_age`, `get_mass_weighted_metallicity`,
`get_lum_weighted_age`, `get_flux_weighted_age`,
`get_mass_weighted_optical_depth`, `get_weighted_attr`, and
`get_ionising_photon_luminosity`.

Parametric `Stars` adds `get_sfh`, `get_sfzh`, `calculate_mean_age`,
`calculate_average_sfr`, `calculate_surviving_mass` and `plot_sfh`/`plot_sfzh`.

Particle `Stars` adds `get_radii`, `get_half_mass_radius`,
`get_los_column_density`, `resample_young_stars`, `parametric_young_stars`,
`integrate_particle_spectra`, and the rotation helpers `rotate_face_on` /
`rotate_edge_on`.

`stars.is_parametric` and `stars.is_particle` tell you which branch an object
came from. Use them instead of guessing from the class name when handling
data you did not construct.
