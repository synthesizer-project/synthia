# Emission Models

An `EmissionModel` describes **how** emission is produced and altered. It is a
node in a directed network, not a single function call. Understanding the
network is what lets you read an unfamiliar model and predict what it will
produce.

`EmissionModel` itself lives in `synthesizer.emission_models`. Get its
signature from `inspect_synthesizer_api` — it has a large keyword surface and
it changes.

## The four operations

Every node does exactly one of:

- **extract** — pull a named spectrum straight out of the grid
  (`incident`, `transmitted`, `nebular`, `linecont`, ...). Requires a grid, and
  requires that the grid actually contains that spectrum.
- **generate** — produce emission from a model instead of a grid: dust emission,
  or a fixed template scaled to some property.
- **transform** — take another node's emission and change it: apply a dust
  attenuation curve, or IGM transmission.
- **combine** — sum the emission of several nodes.

See `custom-emission-models.md` for constructor recipes, emitter wrappers,
masks, scaling, per-particle output, and graph debugging.

A premade model such as `ReprocessedEmission` is just a pre-wired network:
it combines a `NebularEmission` node and a `TransmittedEmission` node. If you
do not pass those children explicitly, the model **creates them for you and
emits a warning** saying so, with generated labels prefixed by an underscore.
Those warnings are informational, not errors — but if the user wants control
over the children, pass them in.

## The emitter

Every model must declare an `emitter`, one of `"stellar"`, `"gas"`,
`"blackhole"`, `"galaxy"`. Two traps:

- `"blackhole"` is **one word**, while the `Galaxy` keyword for the component is
  `black_holes` with an underscore. They do not match, and never will.
- `"gas"` passes validation and then raises `UnimplementedFunctionality`. Gas is
  an attenuating medium, not an emitter.

Premade stellar models set `emitter="stellar"` for you; you only set it by hand
when building a model from scratch.

## Enumerating premade models

`synthesizer.emission_models` has **no `__all__`**. Enumerate the module-level
lists instead — but read **both** of these, because they do not overlap:

- `PREMADE_MODELS` — exactly `STELLAR_MODELS | AGN_MODELS | COMMON_MODELS`.
- `DUST_GENERATORS` — **disjoint** from `PREMADE_MODELS`. `Blackbody`,
  `Greybody`, `Casey12` and `DraineLi07` appear only here. Checking
  `PREMADE_MODELS` alone will tell you they do not exist.

The lists are hand-maintained and can drift from the code, so treat them as
candidate names and confirm each one resolves before using it.
`inspect_synthesizer_api` reports either list's contents directly — pass
`synthesizer.emission_models.PREMADE_MODELS` or `...DUST_GENERATORS` — and
called on the module itself it enumerates every exported class with its
signature. See
`premade-emission-models.md` for the complete current stellar, AGN, common and
dust-generator catalogue, including requirements and selection guidance.

Attenuation laws (`PowerLaw`, `Calzetti2000`, ...) and IGM models (`Madau96`,
`Inoue14`) live in `synthesizer.emission_models.attenuation`.

## Several "classes" are actually factories

Eight premade names define `__new__` and return a **different concrete class**
depending on their arguments — with or without an escaped component, with or
without dust emission:

`TotalEmission`, `IntrinsicEmission`, `PacmanEmission`,
`BimodalPacmanEmission`, `CharlotFall2000`, `ScreenEmission`, `UnifiedAGN`, and
**`TransmittedEmission`** — which is easy to miss, because it appears in the
plain stellar ladder above alongside genuine subclasses.

`EmergentEmission` and `ReprocessedEmission` are ordinary subclasses and behave
as you would expect.

Because these are `__new__` factories their `__init__` is `(*args, **kwargs)`.
`inspect_synthesizer_api` sees through that and reports the real `__new__`
parameters, including the `label` default that decides the output key.

Consequences:

- `isinstance(model, TotalEmission)` is not a reliable check.
- Runtime introspection of the returned object shows the concrete class, not the
  name you called.
- The set of labels the model produces changes with the arguments. With
  `fesc=0`, `IntrinsicEmission` returns a `ReprocessedEmission` — and its label
  is `_intrinsic_reprocessed`, not `intrinsic` and not `reprocessed`.
- **The concrete class changing does not mean the label changes.** Verified
  against 1.2.1.dev: `TotalEmission(grid, dust_curve, tau_v=..., fesc=0)`
  returns an `AttenuatedEmission` **still labelled `"total"`**, because
  `TotalEmission.__new__` defaults `label="total"`. `spectra["total"]` works.
  `PacmanEmission` and `ScreenEmission` default `label=None` and compute one
  instead: with `fesc=0` and no dust emission they label themselves
  **`"attenuated"`**, and `spectra["total"]` raises `KeyError`. Do not assume
  which case you are in — read `model.label`, or pass `label=` explicitly.
- Models produce labels you did not ask for. `ReprocessedEmission(grid)` also
  yields an **`escaped`** label, because the `TransmittedEmission` factory
  underneath it splits off the escaped component at the default `fesc`. Read
  `sorted(component.spectra)` after the first run rather than predicting it.

Always check what labels a model actually defines rather than assuming the
standard set is present.

## Parameters that come from the emitter

Several model parameters default to a **string naming an attribute of the
emitter** — for example `tau_v="tau_v"` or `fesc="fesc"`. This means "look this
value up on the emitter at extraction time". Passing a number instead fixes the
value on the model for every emitter. The two are very different scientifically:
the string form allows per-particle optical depths from line-of-sight
calculations, the number form imposes a uniform screen. Say which one a script
uses.

See `model-parameters.md` for exact `get_param` precedence, arbitrary emitter
attributes, computed parameters, lists, distributions, and model expansion.

## Masks, scaling and post-processing

Nodes can carry a mask (apply this model only to particles satisfying a
threshold on some attribute — young stars only, say), a `scale_by` property, and
post-processing steps. Masks are how the birth-cloud/diffuse split is
implemented, and they are the usual mechanism behind "why is this component
zero" — check the mask before suspecting the grid.

## Choosing a model

Ask what the user actually wants to compare against:

- Pure stellar population, no gas, no dust → `IncidentEmission`.
- Nebular emission included, no dust → `ReprocessedEmission` or
  `IntrinsicEmission`.
- Dust-attenuated UV/optical → `EmergentEmission`, `ScreenEmission`,
  `CharlotFall2000`, or a Pacman variant depending on the geometry.
- Full UV-to-IR energy balance → a `TotalEmission` or Pacman variant with a dust
  emission generator supplied.
- AGN contribution → `UnifiedAGN`, with black hole properties on the emitter.

Each of these is a scientific commitment about geometry and dust. State it.

## Inspecting a built model

Emission models can print or plot their network, and index like a mapping by
label (`model["escaped"]`). When debugging a surprising spectrum, dump the
network first — the answer is usually a missing child, a mask, or a label that
does not exist for this argument combination.
