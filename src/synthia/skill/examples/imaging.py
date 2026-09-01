"""Rest-frame images of a parametric galaxy.

Synthesizer 1.2.1.dev. Verify signatures against the installed version.
Needs test_grid. Runs offline (UVJ filters are local top-hats).

Use for: image, map, resolved light, field of view.

Assumptions to review:
  - the grid fixes the SPS model, IMF and photoionisation setup;
  - a single 10 Myr burst at Z = 0.01, 1e9 Msun formed;
  - light follows one Sersic profile (n = 1, r_eff = 1 kpc) in every
    band, so there are no colour gradients;
  - no dust, and a physical (kpc) rather than angular field of view.
"""

from synthesizer.emission_models import ReprocessedEmission
from synthesizer.grid import Grid
from synthesizer.instruments import UVJ, Instrument
from synthesizer.parametric import Galaxy, Stars
from synthesizer.parametric.morphology import Sersic2D
from unyt import Msun, Myr, kpc

grid = Grid("test_grid")

# sf_hist and metal_dist also accept bare scalars for a single burst at
# a single metallicity, instead of SFH/ZDist objects.
stars = Stars(
    grid.log10ages,
    grid.metallicities,
    sf_hist=10 * Myr,
    metal_dist=0.01,
    initial_mass=1e9 * Msun,
    morphology=Sersic2D(r_eff=1.0 * kpc, sersic_index=1.0, ellipticity=0.5),
)
galaxy = Galaxy(stars)
galaxy.stars.get_spectra(ReprocessedEmission(grid))

# Images are built from photometry, so it must exist first. Rest-frame
# images use luminosities; observer-frame images need fluxes and
# get_images_flux instead.
filters = UVJ(new_lam=grid.lam)
galaxy.stars.get_photo_lnu(filters)

# Instrument is a factory: filters + a spatial resolution gives an
# imager. Filters alone would give integrated photometry.
resolution = 0.05 * kpc
instrument = Instrument("demo-imager", resolution=resolution, filters=filters)

# Positional arguments are the spectra labels to image. Parametric
# galaxies can only be "smoothed" -- the light comes from the
# morphology; "hist" is particle-only.
images = galaxy.get_images_luminosity(
    "reprocessed",
    fov=100 * resolution,
    instrument=instrument,
)

print("image filters:", list(images.keys()))
print("image shape:", images["V"].shape)
