# The Black Hole Emitter

The AGN parameter surface is large and lives mostly on the **emitter**, not on
the emission model. That is the single most common reason for reading AGN
source code, so the surface is written out here.

Names differ by branch and do not both exist:

| branch | class | note |
|---|---|---|
| parametric | `synthesizer.parametric.BlackHole` | **singular**; no `BlackHoles` |
| particle | `synthesizer.particle.BlackHoles` | **plural**; no `BlackHole` |

The `Galaxy` keyword is `black_holes` (underscore) on both branches, while the
emission model's emitter string is `"blackhole"` (one word). They never match.

Confirm signatures with `inspect_synthesizer_api` before writing code.

## Accretion and luminosity

Give **either** a mass and an accretion rate, **or** a bolometric luminosity.

- `mass` / `masses` — black hole mass, unit-bearing.
- `accretion_rate` / `accretion_rates` — unit-bearing mass per time.
- `accretion_rate_eddington` / `accretion_rates_eddington` — Eddington-scaled
  alternative to the absolute rate.
- `epsilon` / `epsilons` — radiative efficiency, **default 0.1**.
- `bolometric_luminosity` — pass it directly to bypass the derivation.
- `spin` / `spins`, `metallicity` / `metallicities`.

Given mass, accretion rate and `epsilon`, the bolometric luminosity is
**derived for you** at construction; you do not compute it yourself. The
matching helpers are `calculate_bolometric_luminosity`,
`calculate_eddington_luminosity`, `calculate_eddington_ratio`,
`calculate_accretion_rate`, `calculate_accretion_rate_eddington`,
`calculate_bb_temperature`, `calculate_schwarzschild_radius` and
`calculate_ionising_luminosity`.

## Geometry

- `inclination` / `inclinations` — viewing angle, in angle units. Defaults to
  0 degrees on the parametric side.
- `theta_torus` — torus opening angle, **default 10 degrees**, unit-bearing.
- `offset` (parametric) — 2D positional offset, defaults to `[0, 0] kpc`.
- particle-only: `coordinates`, `velocities`, `smoothing_lengths`,
  `softening_lengths`, `centre`, plus `calculate_random_inclination`.

**There is no `covering_fraction_torus`.** The torus is controlled by
`theta_torus` and by the torus emission model you pass to `UnifiedAGN`.
Covering fractions exist only for the line regions, below.

## Line regions

Both regions carry an independent set, all with defaults:

| parameter | NLR default | BLR default |
|---|---|---|
| `ionisation_parameter_nlr` / `_blr` | `0.01` | `0.1` |
| `hydrogen_density_nlr` / `_blr` | `1e4 cm^-3` | `1e9 cm^-3` |
| `covering_fraction_nlr` / `_blr` | `0.1` | `0.1` |
| `velocity_dispersion_nlr` / `_blr` | `500 km/s` | `2000 km/s` |

These are physical commitments with real spectral consequences. State the ones
you rely on; never present a default as a recommended value.

`tau_v` (particle) and `fesc` are also accepted, as on other emitters.

## UnifiedAGN

`UnifiedAGN` is a `__new__` factory, so its `__init__` is
`(*args, **kwargs)`. `inspect_synthesizer_api` sees through that and reports
the real parameters; the required ones are:

- `nlr_grid` — a grid containing NLR emission;
- `blr_grid` — a **separate** grid containing BLR emission;
- `torus_emission_model` — a dust **generator** (`Blackbody`, `Greybody`,
  `Casey12`, `DraineLi07`), not an attenuation curve.

Optional: `disc_transmission` (default `"weighted_combination"`; also
`"random"`, `"none"`/`"escaped"`, `"nlr"`, `"blr"`), `diffuse_dust_curve`,
`diffuse_dust_emission_model`, `velocity_dispersion_blr`,
`velocity_dispersion_nlr`, `label`.

NLR and BLR grids are **not interchangeable** with a stellar grid and not with
each other. Use `list_local_grids` and `inspect_local_grid` to confirm you
actually have both before writing a script that needs them; if you do not,
say so rather than substituting a stellar grid.

Component-level AGN models — `NLREmission`, `BLREmission`,
`DiscIncidentEmission`, `DiscTransmittedEmission`, `TorusEmission`,
`AGNIntrinsicEmission` and the NLR/BLR incident and transmitted variants —
are catalogued in `premade-emission-models.md`.

## Which properties dominate the far-IR

The far-IR of a `UnifiedAGN` spectrum is torus reprocessing, so it is driven
by the torus emission model and `theta_torus` together with the bolometric
luminosity that sets the energy budget — not by the line-region parameters,
which shape the optical and UV. Reason about it as an energy balance and say
which knobs you turned.
