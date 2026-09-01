"""Expand one emission network over several parameter values.

Synthesizer 1.2.1.dev. Verify signatures against the installed version.
Needs test_grid. Runs offline.

Use for: parameter list, model variants, distributions, expand_models.
"""

from synthesizer.emission_models import PacmanEmission, ParameterList
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

model = PacmanEmission(
    grid,
    tau_v=ParameterList(
        [0.1, 0.5, 1.0],
        label_modifier="tauv_%.1f",
    ),
    dust_curve=PowerLaw(slope=-1.0),
    fesc=0.0,
).expand_models()

galaxy.stars.get_spectra(model)
for variant in model.select("attenuated*"):
    print(variant.label, variant.variant_params)
