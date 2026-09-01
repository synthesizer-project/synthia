"""Parametric and particle galaxies side by side.

Synthesizer 1.2.1.dev. Verify signatures against the installed version.
Needs test_grid. Runs offline. There is no general random-galaxy
sampler and no test-data loader that avoids downloading, so mock
particles are built by sampling a parametric SFZH.

Use for: synthetic, fake, mock data, no simulation, test data,
sample particles.

Assumptions to review:
  - the grid fixes the SPS model, IMF and photoionisation setup;
  - constant SF over 100 Myr, Z = 0.01, 1e9 Msun formed;
  - 500 particles drawn from that SFZH with a fixed seed;
  - a 3D Gaussian spatial distribution of scale 1 kpc, which is a
    stand-in for real structure, not a physical model.
"""

import numpy as np
from synthesizer.emission_models import IncidentEmission
from synthesizer.grid import Grid
from synthesizer.parametric import SFH, Stars, ZDist
from synthesizer.parametric import Galaxy as ParametricGalaxy
from synthesizer.particle import CoordinateGenerator
from synthesizer.particle import Galaxy as ParticleGalaxy
from synthesizer.particle.stars import sample_sfzh_from_array
from synthesizer.particle.utils import calculate_smoothing_lengths
from unyt import Msun, Myr, kpc

grid = Grid("test_grid")
n_part = 500

# --- Parametric: a distribution over the grid's own axes -------------
par_stars = Stars(
    grid.log10ages,
    grid.metallicities,
    sf_hist=SFH.Constant(max_age=100 * Myr),
    metal_dist=ZDist.DeltaConstant(metallicity=0.01),
    initial_mass=1e9 * Msun,
)
par_galaxy = ParametricGalaxy(par_stars)

# --- Particle: discrete elements sampled from that same SFZH ---------
# Only generate_3D_gaussian works; generate_2D_Sersic and
# generate_3D_spline raise UnimplementedFunctionality. It returns a
# BARE dimensionless (n, 3) array, so attach a length unit yourself.
coords = CoordinateGenerator.generate_3D_gaussian(n_part) * kpc
smls = calculate_smoothing_lengths(coords, num_neighbours=32)

# sample_sfzh_from_array is the current API; sample_sfzh is deprecated
# and merely forwards. It takes the raw SFZH array plus both axes plus
# a particle count -- not the Stars object -- and samples WITHIN each
# histogram cell rather than snapping to grid nodes. Extra kwargs go
# straight to the particle Stars constructor.
part_stars = sample_sfzh_from_array(
    par_stars.sfzh,
    par_stars.log10ages,
    par_stars.log10metallicities,
    n_part,
    seed=42,
    coordinates=coords,
    smoothing_lengths=smls,
    redshift=3.0,
    current_masses=np.full(n_part, 1e9 / n_part) * Msun,
)
part_galaxy = ParticleGalaxy(stars=part_stars, redshift=3.0)

# --- The same emission model works on both --------------------------
model = IncidentEmission(grid)
par_sed = par_galaxy.stars.get_spectra(model)
part_sed = part_galaxy.stars.get_spectra(model)

print("parametric Lbol:", par_sed.bolometric_luminosity)
print("particle   Lbol:", part_sed.bolometric_luminosity)
print("particle count:", part_stars.nstars)
