# Particle Workflows

Use the particle branch when the user has **discrete resolution elements** —
star particles, gas particles, black hole particles — typically loaded from a
hydrodynamic simulation snapshot. Signatures and keyword names change between
versions; confirm them with `inspect_synthesizer_api` before writing code.

## Names

Everything lives under `synthesizer.particle`:

| concept | particle name |
|---|---|
| stars | `synthesizer.particle.Stars` |
| gas | `synthesizer.particle.Gas` |
| black holes | `synthesizer.particle.BlackHoles` (**plural**) |
| galaxy | `synthesizer.particle.Galaxy` |
| generic particles | `synthesizer.particle.Particles` (also aliased `DarkMatter`) |

`BlackHoles` is plural on the particle side and **singular** (`BlackHole`) on
the parametric side. This bites constantly — see `troubleshooting.md`.

## Building the components

Particle `Stars` are defined by their own physical properties, independent of
any grid: initial masses, ages, metallicities, plus optional coordinates,
velocities, current masses, smoothing lengths, and a centre. Attach coordinates
and smoothing lengths if you intend to do line-of-sight attenuation or smoothed
imaging; without them those operations cannot run.

Particle `Gas` carries masses, metallicities, and optionally dust masses or a
dust-to-metal ratio. In the current design gas is an **attenuating medium**, not
an emitter: an emission model with `emitter="gas"` is validated but raises
`UnimplementedFunctionality`.

Assemble them with `synthesizer.particle.Galaxy` directly, or via the top-level
`galaxy()` factory, which dispatches on the type of the `stars` argument. Note
the galaxy keyword for black holes is `black_holes` (with an underscore) even
though the emission model's emitter string is `"blackhole"` (one word).

## Getting emission

Emission is requested from the component, not usually from the galaxy:
`galaxy.stars.get_spectra(model)`. Particle extraction interpolates each
particle onto the grid axes; the assignment scheme (cloud-in-cell versus
nearest grid point) is a keyword on the call and is a real scientific choice —
say which one you used.

Results land in `galaxy.stars.spectra`, keyed by emission model label. One call
usually populates several labels, because the model network computes its
children.

## Per-particle emission

Particle emitters can produce either one integrated spectrum for the component
or one spectrum **per particle**. Per-particle is switched on via the emission
model, not the call, and it costs memory proportional to the number of
particles times the number of wavelengths — this is easily tens of gigabytes for
a big galaxy. Integrated spectra can be recovered from per-particle spectra by
integration; the reverse is impossible. Default to integrated unless the user
needs spatial or per-particle information (imaging, resolved spectroscopy,
per-particle photometry).

## Line-of-sight attenuation

The particle branch can compute a per-star `tau_v` from the gas distribution
along the line of sight, using an SPH kernel. This requires coordinates,
smoothing lengths, and gas dust masses (or a dust-to-metal ratio), and it
depends on the viewing direction — so rotating the galaxy changes the answer.
`LOSStellarEmission` is the premade model built around this.

Alternatives, in increasing order of physical detail: a single uniform screen
`tau_v`, a birth-cloud/diffuse split (`CharlotFall2000`, `BimodalPacmanEmission`),
and full line-of-sight ray tracing. Say which one a script uses and why.

## Imaging

Particle galaxies can be imaged as a plain histogram of particle photometry
(`"hist"`) or smoothed over each particle's SPH kernel (`"smoothed"`). Smoothed
imaging needs smoothing lengths and an SPH kernel object. Both need per-particle
photometry, so the emission model must have been run per-particle.

## Sampling a parametric population into particles

`synthesizer.particle.stars.sample_sfzh_from_array` turns a parametric SFZH into
star particles. (`sample_sfzh` is deprecated and merely forwards to it.) It does
**not** take a `parametric.Stars` object — it takes the raw SFZH array, both
axis arrays and a particle count:

```text
sample_sfzh_from_array(sfzh, log10ages, log10metallicities, nstar,
                       initial_mass=None, seed=None, **kwargs)
```

so you unpack those attributes off the parametric `Stars` object yourself.
`**kwargs` go straight to the particle `Stars` constructor, which is how
`coordinates`, `smoothing_lengths`, `redshift` and `current_masses` are
attached. Sampling is *within* each histogram cell, not snapped to grid nodes.

This is the practical way to build mock particle data offline, and it makes the
two branches directly comparable — see `examples/mock-data.py`. For spatial
positions, `CoordinateGenerator.generate_3D_gaussian` is the only generator
implemented; the 2D Sersic and 3D spline ones raise
`UnimplementedFunctionality`, and it returns a bare dimensionless array, so
attach a length unit yourself.

## Loading simulation data

`synthesizer.load_data` ships loaders for **bluetides, camels, eagle, flares,
illustris, scsam, simba** and **yt** (its `__init__.py` is empty, so import the
submodule: `synthesizer.load_data.load_camels`). There is **no SWIFT loader** —
a user with a SWIFT snapshot builds particle `Stars` from arrays themselves, as
`examples/particle-sed.py` does. Say so rather than inventing a loader name.

## Scale

For more than a handful of galaxies use `synthesizer.pipeline.Pipeline` rather
than a hand-rolled loop: it handles threading, MPI, and structured HDF5 output.
