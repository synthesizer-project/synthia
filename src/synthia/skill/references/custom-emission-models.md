# Custom Emission Models

An emission model is a directed graph. Each node performs exactly one operation:
extract, generate, transform, or combine. Build the smallest nodes first, then
pass them into downstream nodes. Confirm the installed `EmissionModel` signature
with `inspect_synthesizer_api`; its keyword surface changes.

## Pick the emitter wrapper

- `StellarEmissionModel` sets `emitter="stellar"`.
- `BlackHoleEmissionModel` sets `emitter="blackhole"`.
- `GalaxyEmissionModel` sets `emitter="galaxy"` and permits combinations only.
- Base `EmissionModel` needs an explicit emitter.

`"blackhole"` is one word. Gas is an attenuating component, not a supported
emission source. Galaxy nodes cannot extract grid spectra or work per-particle.

## Extract from a grid

An extraction node needs `label`, `grid`, and `extract`, where `extract` is a
spectrum key actually present in that grid.

```python
from synthesizer.emission_models import StellarEmissionModel

incident = StellarEmissionModel(
    label="my_incident",
    grid=grid,
    extract="incident",
)
```

Use `inspect_local_grid` before choosing keys such as `incident`, `transmitted`,
`nebular`, or `linecont`.

## Generate emission

A generation node needs a generator. Its required parameters are resolved from
the model/emission/emitter chain described in `model-parameters.md`.

```python
dust = StellarEmissionModel(
    label="my_dust",
    generator=dust_generator,
)
```

Dust generators normally also need nodes defining the intrinsic and attenuated
luminosity, or another scaler. Premade `DustEmission` and total/Pacman networks
perform that wiring for common energy-balance cases.

## Transform another node

A transformation node needs `apply_to` and a transformer. Attenuation curves,
escape/covering fractions and IGM transmission are transformers.

```python
from synthesizer.emission_models import StellarEmissionModel

attenuated = StellarEmissionModel(
    label="my_attenuated",
    apply_to=incident,
    transformer=dust_curve,
    tau_v="my_tau_v",
)
```

Here the string means that `my_tau_v` is resolved from the stellar emitter at
extraction time. A number would fix one optical depth for every emitter.

## Combine nodes

A combination node needs an iterable of existing nodes.

```python
from synthesizer.emission_models import GalaxyEmissionModel

total = GalaxyEmissionModel(
    label="stars_plus_agn",
    combine=(stellar_model, agn_model),
)
```

Component nodes must already identify compatible emitters. A galaxy combination
can combine component-level results but cannot extract from a grid itself.

## Controls shared by nodes

- `label` is the output key and must be unique across the graph.
- `related_models` attaches outputs that are not direct dependencies of root.
- `mask_attr`, `mask_op`, and `mask_thresh` restrict a node to matching emitter
  elements. Confirm exact installed arguments before use.
- `scale_by` names a resolved parameter used to scale generated or extracted
  emission.
- `per_particle=True` retains one spectrum per particle instead of integrating.
  It costs much more memory and is required by some resolved imaging workflows.
- Post-processing hooks alter a completed node; use them only when a premade
  transformer cannot express the operation.

Masks and per-particle parameters must have shapes compatible with the emitter.
A scalar applies uniformly; a particle array needs one value per emitting
element.

## Debug the graph, not one node

Call `model.unpack_model()` after changing graph links if the API does not do it
for you. Inspect `model._models`, index nodes by label (`model["label"]`), and
use `plot_emission_graph` or the model's graph-printing method. A missing result
usually comes from a changed factory label, mask, missing child, or unresolved
parameter rather than from spectral arithmetic.

After generating once, inspect `sorted(emitter.spectra)` instead of predicting
which child labels a factory emitted.
