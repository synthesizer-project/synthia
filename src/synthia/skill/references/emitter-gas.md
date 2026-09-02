# The Gas Component

Gas is **not an emitter**. It is an attenuating medium. An emission model
declaring `emitter="gas"` passes validation and then raises
`UnimplementedFunctionality` at generation time.

There is **no parametric gas class**. `synthesizer.particle.Gas` exists;
`synthesizer.parametric.Gas` does not. Parametric attenuation is expressed as
a screen or a birth-cloud/diffuse split on the emission model instead — see
`emission-models.md`.

Confirm signatures with `inspect_synthesizer_api` before writing code.

## What you pass in

- `masses`, `metallicities` — required, unit-bearing where the category has
  units.
- `dust_to_metal_ratio` — a scalar; dust masses are then **derived for you**
  at construction.
- `dust_masses` — supply dust masses directly instead of a ratio.
- `star_forming` — a boolean mask over the particles.
- `coordinates`, `velocities`, `smoothing_lengths`, `softening_lengths`,
  `centre` — required for line-of-sight work and smoothed imaging.
- `tau_v`, `redshift`, `metallicity_floor`.

Pass one of `dust_to_metal_ratio` or `dust_masses`, not both. `calculate_dust_mass`
recomputes the derived masses if you change the ratio afterwards.

## What gas is actually for

Line-of-sight attenuation. The gas distribution supplies the column that
attenuates the stars behind it, which is how a spatially resolved optical
depth gets computed instead of assumed:

- `galaxy.get_stellar_los_tau_v(...)` and
  `galaxy.get_black_hole_los_tau_v(...)` compute per-particle `tau_v` from the
  gas distribution and attach it to the emitter.
- `LOSStellarEmission` then consumes those optical depths.
- `gas.get_los_column_density(...)` gives the raw column.

This needs coordinates and smoothing lengths on **both** the gas and the
emitter being attenuated. Without them the calculation cannot run.

Particle `Galaxy` also offers `calculate_dust_to_metal_vijayan19` and
`calculate_dust_screen_gamma` for prescriptions that set the dust content from
other properties, and gas maps via `get_map_gas_mass`,
`get_map_gas_metallicity` and `get_map_gas_metal_mass`.

## Common mistake

Reaching for gas to make a galaxy "have dust". For a parametric galaxy, or a
particle galaxy where you only want a uniform screen, dust is a **model**
concern: a `dust_curve` transformer plus a `tau_v` parameter. Only use gas when
the optical depth should come from the spatial distribution of the gas itself.
