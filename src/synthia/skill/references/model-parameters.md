# Emission Model Parameters

Emission models resolve named parameters at calculation time. A model argument
can therefore be a fixed value, an alias to emitter data, a computed function,
or a declaration that expands into several model variants.

## Resolution order

`get_param(name, model, emission, emitter, obj)` searches in this exact order:

1. `model.fixed_parameters`
2. an attribute on the current emission (`Sed` or `LineCollection`)
3. an attribute on the emitter (`Stars`, `BlackHoles`, or `Galaxy`)
4. an attribute on the optional fallback object

The first value found wins. Model values therefore override identically named
emission or emitter attributes.

## Fixed values and string aliases

Passing a number, array, unit-bearing quantity or other ordinary object fixes
that value on the model. Passing a string means **alias this parameter to an
attribute with that name on the emitter**:

```python
model = ScreenEmission(grid, dust_curve, tau_v="my_tau_v")
stars.my_tau_v = 0.4
```

Emitter classes are ordinary Python objects: attach arbitrary attributes after
construction, or pass custom keyword attributes where that emitter constructor
supports them. Any model or transformer can use the attribute when one of its
parameters points to that name. The model does not discover arbitrary
attributes automatically; the alias or `ParameterFunction` must request it.

A scalar custom attribute applies uniformly. For particle emitters, arrays used
per-particle must have one entry per particle and carry units when the consuming
operation requires them. Parametric emitters usually need scalar or grid-shaped
values appropriate to the operation.

String aliases are followed recursively on the emitter. Alias cycles raise
`MissingAttribute`. Once alias resolution starts, it does not restart the full
model/emission/object precedence chain.

## Fallbacks and caching

- If a requested name contains `log10` and is missing, resolution tries the
  unlogged name, takes `numpy.log10`, and attaches the result to the emitter.
- Resolution tries singular and plural spellings when the exact name is absent.
- Resolved values are cached under
  `emitter.model_param_cache[model.label][parameter]` where possible.
- Without an explicit default, failure raises `MissingAttribute` and reports the
  objects searched.
- Array-like values are normalised for C-backed calculations unless
  `preserve_units=True` is requested internally.

These conveniences can hide spelling errors. Prefer exact attribute names and
inspect the cache when debugging.

## Computed parameters

`ParameterFunction` wraps a function whose named arguments are themselves
resolved through the same precedence chain. It is suitable for a scalar or
per-particle value derived from emitter attributes and fixed model parameters.

```python
from synthesizer.emission_models import ParameterFunction

def optical_depth(metallicities, normalisation):
    return metallicities * normalisation

tau = ParameterFunction(
    optical_depth,
    sets="tau_v",
    func_args=["metallicities", "normalisation"],
)
model = ScreenEmission(
    grid,
    dust_curve,
    tau_v=tau,
    normalisation=20.0,
)
```

The wrapped function signature must exactly match `func_args`. Its return shape
must match the emitter when returning per-particle values. The result is cached
under the name given by `sets`.

## Explicit model variants

`ParameterList` declares one model variant per value. It is not itself a usable
parameter value.

```python
from synthesizer.emission_models import ParameterList

fesc = ParameterList(
    [0.0, 0.1, 0.5],
    label_modifier="fesc_%.1f",
)
model = IntrinsicEmission(grid, fesc=fesc).expand_models()
stars.get_spectra(model)
```

Use exactly one naming mode: a printf-style `label_modifier`, or explicit
`labels` with one unique label per value. Expansion copies the varied node and
everything downstream, while sharing unaffected upstream work. Generated
emissions are stored under the suffixed labels.

## Sampled model variants

`ParameterDistribution` subclasses sample one scalar per **model variant**, not
one value per particle. Current families include uniform, normal and log-normal
distributions; confirm exact exported names and signatures with
`inspect_synthesizer_api`.

Specify the number of samples and exactly one label mode. Pass a seed for
reproducible values and stable labels. Unit-bearing parameter distributions need
compatible units. Expansion realises each distribution once before graph copies
are made.

Use `ParameterFunction` instead when each particle needs a separately computed
or sampled value.

## What can vary

Variation declarations can be attached to:

- any fixed model parameter, such as `fesc` or `tau_v`;
- the transformer's or generator's complete object;
- an attribute on a transformer or generator, represented internally by dotted
  names such as `transformer.slope`.

Call `expand_models()` on the root before generating emission. An unexpanded
`ParameterList` or `ParameterDistribution` raises `InconsistentArguments`.
Inspect each expanded node's `variant_params` and `variant_base` rather than
parsing labels to recover which parameters produced it.
