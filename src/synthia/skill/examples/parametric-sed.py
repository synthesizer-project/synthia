"""Parametric SED: the canonical starting point.

Synthesizer 1.2.1.dev. Verify signatures against the installed version.
Needs test_grid (reprocessed, age/metallicity axes). Runs offline.

Use for: parametric, star formation history, analytic galaxy, sfzh.

Assumptions to review:
  - the grid fixes the SPS model, IMF and photoionisation setup;
  - constant star formation over the last 100 Myr;
  - a single metallicity, Z = 0.01, and 1e9 Msun of stars formed;
  - no dust: this is the reprocessed spectrum, not the emergent one.
"""

from synthesizer.emission_models import ReprocessedEmission
from synthesizer.grid import Grid
from synthesizer.parametric import SFH, Galaxy, Stars, ZDist
from unyt import Msun, Myr

# Grid names take no extension (".hdf5" is tolerated, ".h5" is not).
grid = Grid("test_grid")

# SFH and ZDist supply only the shape; initial_mass sets the scale.
# A parametric Stars is defined on the grid's own axes, hence log10ages
# and metallicities being passed in.
stars = Stars(
    grid.log10ages,
    grid.metallicities,
    sf_hist=SFH.Constant(max_age=100 * Myr),
    metal_dist=ZDist.DeltaConstant(metallicity=0.01),
    initial_mass=1e9 * Msun,
)
galaxy = Galaxy(stars)

# ReprocessedEmission combines nebular and transmitted emission. It
# builds those children itself and warns that it has done so; pass your
# own if you need control over their parameters.
sed = galaxy.stars.get_spectra(ReprocessedEmission(grid))

# One call populates the whole network, not just the requested label.
print("spectra:", sorted(galaxy.stars.spectra))

# lam/lnu are unyt arrays; sed._lam/._lnu are bare numpy already
# converted to the default units (Angstrom, erg/s/Hz).
print("wavelengths:", sed.lam.min(), "to", sed.lam.max())
print("bolometric luminosity:", sed.bolometric_luminosity)
