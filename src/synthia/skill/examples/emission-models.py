"""Emission models: dust, labels, and the composition traps.

Synthesizer 1.2.1.dev. Verify signatures against the installed version.
Needs test_grid (reprocessed). Runs offline.

Use for: dust attenuation model, model composition, pacman, escape fraction.

Assumptions to review:
  - the grid fixes the SPS model, IMF and photoionisation setup;
  - constant SF over 100 Myr, Z = 0.01, 1e9 Msun formed;
  - a uniform dust screen, tau_v = 0.3, power-law curve of slope -1;
  - fesc = 0, so nothing escapes the birth cloud unprocessed.
"""

from synthesizer.emission_models import PacmanEmission, TotalEmission
from synthesizer.emission_models.attenuation import PowerLaw
from synthesizer.grid import Grid
from synthesizer.parametric import SFH, Galaxy, Stars, ZDist
from unyt import Msun, Myr

grid = Grid("test_grid")
stars = Stars(
    grid.log10ages,
    grid.metallicities,
    sf_hist=SFH.Constant(max_age=100 * Myr),
    metal_dist=ZDist.DeltaConstant(metallicity=0.01),
    initial_mass=1e9 * Msun,
)
galaxy = Galaxy(stars)

# A number for tau_v imposes a uniform screen. The default is the
# STRING "tau_v", meaning "look this up on the emitter at extraction
# time" -- which is how per-particle optical depths reach the model.
model = PacmanEmission(
    grid,
    tau_v=0.3,
    dust_curve=PowerLaw(slope=-1),
    fesc=0.0,
    fesc_ly_alpha=1.0,
)

# TRAP: with fesc=0 and no dust emission model, both PacmanEmission and
# TotalEmission are __new__ factories that return a model labelled
# "attenuated" -- so spectra["total"] is a KeyError. Read model.label
# rather than assuming, or pass label= explicitly.
print("pacman label:", model.label)
print("total label:", TotalEmission(grid, PowerLaw(), fesc=0.0).label)

galaxy.stars.get_spectra(model)

# Children are auto-created and warned about; their labels are prefixed
# with an underscore. Pass your own children to control them.
print("spectra:", sorted(galaxy.stars.spectra))

# Models index by label and can print their network -- do this first
# when a component comes out zero or missing.
print("attenuated node emitter:", model["attenuated"].emitter)
