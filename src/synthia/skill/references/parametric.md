# Parametric Workflows

Use the parametric branch when the galaxy is described by **distributions**
rather than particles: a star formation history, a metallicity distribution, and
optionally an analytic light profile. Confirm all signatures with
`inspect_synthesizer_api`.

## Names

Everything lives under `synthesizer.parametric`:

| concept | parametric name |
|---|---|
| stars | `synthesizer.parametric.Stars` |
| galaxy | `synthesizer.parametric.Galaxy` |
| black hole | `synthesizer.parametric.BlackHole` (**singular**) |
| gas | **does not exist** |

`synthesizer.parametric` also re-exports three modules under short aliases:

- `SFH` — star formation history parametrisations
  (module `synthesizer.parametric.sf_hist`)
- `ZDist` — metallicity distributions
  (module `synthesizer.parametric.metal_dist`)
- `Kernels` — SFH kernels (module `synthesizer.parametric.sfh_kernels`)

and morphologies including `Sersic2D`, `Gaussian2D` and `PointSource`.

There is no parametric gas component. Parametric attenuation is a screen or a
birth-cloud/diffuse split defined on the emission model, not a gas distribution.

**The top-level `galaxy()` factory cannot build a parametric galaxy with a black
hole.** Given a parametric `stars`, it raises `InconsistentArguments` if `gas`
or `black_holes` is anything other than `None` — there is **no type check**, so
a perfectly valid parametric `BlackHole` is rejected too. The error message
blames "particle based" objects, which is misleading in that case. The fix is to
construct `synthesizer.parametric.Galaxy(stars=..., black_holes=...)` directly,
which works.

## The SFZH

A parametric `Stars` object holds an **SFZH**: the distribution of stellar mass
formed across the grid's age and metallicity axes. Because it is defined on the
grid's axes, it is built from the grid's own age and metallicity arrays. This is
the reason `grid.log10ages` and `grid.metallicities` appear in every parametric
example — a `Stars` object built on different axes cannot be extracted from that
grid.

Construction takes:

- the age and metallicity axes (from the grid),
- a star formation history: an `SFH` object, or a scalar age for a single burst,
- a metallicity distribution: a `ZDist` object, or a scalar metallicity,
- a normalisation, given as a total initial stellar mass,
- optionally a morphology, for imaging.

Total mass is a normalisation. The SFH and ZDist objects supply only the
*shape*; the mass scale is separate and must be set deliberately.

## Choosing an SFH and ZDist

`SFH` covers the usual analytic families (constant, exponential and delayed
exponential, log-normal, double power law, Gaussian, truncated forms, plus
piecewise and non-parametric families such as continuity and Dirichlet priors).
`ZDist` covers a fixed metallicity (`DeltaConstant`) and a normal distribution.
Enumerate what the installed version actually offers rather than guessing:
inspect `synthesizer.parametric.sf_hist` and `synthesizer.parametric.metal_dist`.

`ZDist.DeltaConstant` typically accepts either a linear metallicity or its
log10 — two different keywords with very different values. Check which one you
are passing; `0.01` and `-2.0` are both plausible-looking and mean the same
thing only by coincidence.

## Morphology and imaging

Parametric galaxies have no particles, so their spatial structure comes from an
analytic morphology (`Sersic2D`, `Gaussian2D`, `PointSource`) attached to the
`Stars` object. Parametric imaging is therefore always "smoothed" — requesting a
histogram image raises an exception.

## Getting emission

Identical in shape to the particle branch: build the model, then
`galaxy.stars.get_spectra(model)`, and read results from `galaxy.stars.spectra`
keyed by model label. Parametric emitters have no per-particle mode — the SFZH
bin weights play the role that particles play on the other branch.

## When to prefer parametric

- Fitting or exploring SFH/metallicity parameter space.
- Idealised or toy galaxies, and tests.
- Semi-analytic model output that is already expressed as histories.
- Any case where the user has no particle data.

Convert to particles with
`synthesizer.particle.stars.sample_sfzh_from_array` when you need particle-only
machinery such as line-of-sight attenuation. It takes the raw SFZH array and
both axes, not the `Stars` object itself (`sample_sfzh` is the deprecated
spelling) — see `particle.md` and `examples/mock-data.py`.
