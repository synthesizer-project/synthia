# Observatories and Observables

Emissions are theoretical. Observables are what a telescope would record. This
file covers the boundary between them. Confirm all signatures with
`inspect_synthesizer_api`.

## Rest frame versus observer frame

The most common source of confusion in a Synthesizer script:

| quantity | frame | needs |
|---|---|---|
| `lnu`, `llam` | rest | nothing beyond the emission |
| `fnu`, `flam` | observed | a cosmology and a redshift |

Fluxes are computed from an `Sed` by supplying an astropy cosmology and a
redshift, optionally with an IGM attenuation model (`Madau96`, `Inoue14`).
Until that is done, `fnu` does not exist and any flux-based observable will
fail. Correspondingly there are two of everything downstream:
`get_photo_lnu`/`get_photo_fnu`, `get_images_luminosity`/`get_images_flux`.
Choosing the wrong one is a silent scientific error as often as it is a crash.

For a redshift-zero or intrinsically rest-frame comparison, stay with
luminosities. Do not compute fluxes just because a filter is involved.

## Filters

`Filter` and `FilterCollection` live in `synthesizer.instruments`.
`FilterCollection` builds from:

- **SVO filter codes** such as `"JWST/NIRCam.F444W"` — these are fetched from
  the SVO service over the network on first use and cached locally. This is a
  download; mention it before writing a script that will trigger it on a machine
  with a cold cache.
- **top-hat definitions** — pure local, good for tests and for rest-frame bands.
- **arbitrary transmission arrays**.
- `UVJ()` gives the standard rest-frame U, V and J top-hats.

Only the SVO route needs the network. Premade instruments are **also** not
offline — `JWSTNIRCam()` and friends raise `MissingInstrumentFile` without a
downloaded instrument cache, so never build a reproducible script on them.
`examples/photometry.py` shows the offline alternatives.

Filters and the spectra they are applied to must share a wavelength grid;
`FilterCollection` accepts a new wavelength array so it can be resampled onto
the grid's wavelengths up front.

## Instruments

`Instrument` in `synthesizer.instruments` is a **factory**: it inspects the
arguments and returns a specialised class. The combination you pass determines
the kind of instrument you get, and therefore what it can do:

| arguments | you get |
|---|---|
| filters, no resolution | integrated photometry |
| filters + spatial resolution | imaging |
| wavelength array, no resolution | spectroscopy |
| wavelength array + spatial resolution | spectral data cube (IFU) |

Optional extras: PSFs, noise maps, depths and aperture radii for depth.
`InstrumentCollection` holds several instruments together.

Premade instruments (JWST, HST, Euclid, GALEX families) are injected into
`synthesizer.instruments` **dynamically at import time**, so static analysis and
editor autocomplete cannot see them. The runtime enumeration is
`AVAILABLE_INSTRUMENTS`, and there is a helper that prints them. If a premade
instrument name seems to be missing, check that list before concluding it does
not exist. Premade instruments pull their filter data on first use and cache it.

## Photometry

Photometry integrates an `Sed` through filter transmission curves. Luminosity
photometry needs only the rest-frame spectrum; flux photometry needs fluxes to
have been computed first.

**`get_photo_lnu` and `get_photo_fnu` exist on both the `Sed` and the component,
and they return different things.** This is the most common indexing mistake:

| called on | returns | indexed by |
|---|---|---|
| `sed.get_photo_lnu(filters)` | a `PhotometryCollection` | **filter code** |
| `galaxy.stars.get_photo_lnu(filters)` | a plain `dict` | **spectra label** |

The component method loops over every spectrum stored on the emitter, calls the
`Sed` method on each, and fills `self.photo_lnu`. So a many-node emission model
gives you photometry for the whole ladder, not just the final label — and access
is two levels deep:

```text
sed.get_photo_lnu(filters)["JWST/NIRCam.F444W"]            # correct
galaxy.stars.get_photo_lnu(filters)["JWST/NIRCam.F444W"]   # KeyError
galaxy.stars.get_photo_lnu(filters)["emergent"]["JWST/NIRCam.F444W"]  # correct
```

Pass `limit_to=["<label>"]` to the component method to compute photometry for
only some spectra; without it you pay for all of them. Despite what the
docstring says, `limit_to` must be a **list** — a bare string is iterated
character by character and raises `KeyError` on its first letter.

## Imaging

The imaging classes are `Image`, `ImageCollection` and `SpectralCube`.
`synthesizer.imaging` has no `__all__`, and `dir()` on it also lists eight
submodules, so neither is a way to decide whether a name exists — use
`inspect_synthesizer_api` for that.

Images come from the galaxy or component via `get_images_luminosity` /
`get_images_flux`, given a field of view and an instrument that has a spatial
resolution. The image type is `"smoothed"` or `"hist"`:

- **Parametric** galaxies can only be smoothed — the light distribution comes
  from the analytic morphology. Asking for a histogram raises.
- **Particle** galaxies can do either. `"smoothed"` distributes each particle's
  photometry over its SPH kernel and needs smoothing lengths plus a kernel
  object; `"hist"` simply bins particle positions.

Imaging needs per-particle photometry on the particle branch, which means the
emission model must have been run per-particle.

`ImageCollection` indexes by filter code, supports arithmetic between compatible
collections (matching resolution and FOV), and can produce RGB composites. PSF
convolution and noise are applied as separate steps after image creation, not
during it.

Resolution and FOV can be given in physical units (kpc) or angular units
(arcsec); angular imaging requires a redshift and a cosmology so the conversion
is defined. Mixing the two silently is a classic way to get an image at the
wrong scale.

## Spectroscopy and data cubes

Spectroscopy resamples emission onto an instrument's wavelength array and can
apply instrumental broadening; particle emitters can additionally apply velocity
(Doppler) broadening from particle velocities. `SpectralCube` combines the
spatial and spectral axes.

## Batching

`Pipeline` (`from synthesizer.pipeline import Pipeline`) runs a single emission
model and a set of instruments over many galaxies, producing photometry,
spectra, lines, images and spectroscopy, and writing to one HDF5 file. It
supports threading and MPI. Prefer it to a hand-written loop whenever there is
more than a handful of galaxies — it gets the output structure right, which is
tedious to reproduce by hand.
