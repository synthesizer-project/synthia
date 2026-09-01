# Pipeline

Use `Pipeline` when many galaxies share one emission model. Do not hand-write a
loop around `get_spectra`: the pipeline batches extraction and collection.

The complete offline pattern is in `examples/pipeline.py`. Adapt the source
returned by `find_example`; do not inspect `pipeline.py` for this standard case.

## Construction and execution

```python
pipeline = Pipeline(emission_model, nthreads=1, verbose=1)
pipeline.add_galaxies(galaxies)
pipeline.get_spectra()
pipeline.get_photometry_luminosities(instrument)
pipeline.run()
```

`emission_model` is the only required constructor argument. Instruments belong
on the requested observable operation, not the constructor. `nthreads > 1`
needs an OpenMP-enabled build.

The `get_*` methods are lazy: they set work flags and return without computing.
`run()` performs requested operations, collects results, and consumes
`pipeline.galaxies`. Call every required `get_*` before one `run()`.

## Results in memory

For stellar integrated spectra:

```python
pipeline.lnu_spectra["Stars"][emission_label]  # (ngalaxy, nlambda)
```

For rest-frame photometric luminosities:

```python
photometry = pipeline.luminosities["Stars"][emission_label]
u = photometry["U"]  # one value per galaxy
```

The nesting is component name, emission label, then filter code. Flux results
use the corresponding flux collection populated by the flux operation. Check
the actual filter codes on the instrument rather than assuming them.

`pipeline.write(path)` is optional HDF5 serialisation. It is not needed to use
results already held in memory.

## Scaling choices

- Reuse one grid and one emission-model graph across all galaxies.
- Parametric galaxies are cheap when only their SFH, metallicity or mass varies.
- Particle galaxies can have different particle counts and properties.
- Integrated spectra are cheaper than per-particle spectra.
- Request only needed observables; every requested operation adds work and
  stored arrays.
- Use a fixed random seed when constructing a synthetic population for a
  reproducible example.

State grid, emission physics, galaxy distribution, redshift, filters, and
whether output is luminosity or flux. Inspect source only for an operation or
result type not covered here or by the installed signature.
