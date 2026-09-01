"""Particle SED from simulation-like star particles.

Synthesizer 1.2.1.dev. Verify signatures against the installed version.
Needs test_grid (age/metallicity axes; incident needs no cloudy run).
Runs offline.

Use for: particle, simulation snapshot, star particles, discrete.

Assumptions to review:
  - the grid fixes the SPS model and IMF;
  - ages/metallicities are arbitrary and must lie inside the grid axes;
  - incident emission only, so no nebular reprocessing and no dust;
  - integrated, not per-particle (per-particle is opt-in on the model
    and costs particles x wavelengths of memory).

See mock-data.py for building particles from a parametric SFZH.
"""

import numpy as np
from synthesizer.emission_models import IncidentEmission
from synthesizer.grid import Grid
from synthesizer.particle import Galaxy, Stars
from unyt import Msun, Myr, kpc

grid = Grid("test_grid")

n_star = 500
rng = np.random.default_rng(42)

# Particle Stars carry their own properties and are interpolated onto
# the grid at extraction time. Coordinates and smoothing lengths are
# only needed for line-of-sight attenuation and smoothed imaging.
stars = Stars(
    initial_masses=np.full(n_star, 1e6) * Msun,
    ages=rng.uniform(1.0, 500.0, n_star) * Myr,
    metallicities=np.full(n_star, 0.01),
    coordinates=rng.normal(0.0, 1.0, (n_star, 3)) * kpc,
    smoothing_lengths=np.full(n_star, 0.5) * kpc,
    redshift=5.0,
)
galaxy = Galaxy(stars=stars, redshift=5.0)

sed = galaxy.stars.get_spectra(IncidentEmission(grid))

print("spectra:", sorted(galaxy.stars.spectra))
print("bolometric luminosity:", sed.bolometric_luminosity)

# Given in kpc, returned in Mpc: public Quantity attributes are
# silently converted to their category default on assignment.
print("coordinates unit:", stars.coordinates.units)
