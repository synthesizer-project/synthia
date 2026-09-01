"""Custom emission graph with an emitter-provided parameter.

Synthesizer 1.2.1.dev. Verify signatures against the installed version.
Needs test_grid. Runs offline.

Use for: custom model, arbitrary emitter attribute, string parameter alias.
"""

from synthesizer.emission_models import (
    AttenuatedEmission,
    StellarEmissionModel,
)
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

# Emitters are ordinary Python objects. A string model parameter resolves this
# attribute at extraction time; a number would instead fix one value on model.
galaxy.stars.my_tau_v = 0.3

incident = StellarEmissionModel(
    label="custom_incident",
    grid=grid,
    extract="incident",
)
attenuated = AttenuatedEmission(
    label="custom_attenuated",
    apply_to=incident,
    emitter="stellar",
    dust_curve=PowerLaw(slope=-1.0),
    tau_v="my_tau_v",
)

galaxy.stars.get_spectra(attenuated)
print("nodes:", sorted(attenuated._models))
print("spectra:", sorted(galaxy.stars.spectra))
print(
    "resolved tau_v:",
    galaxy.stars.model_param_cache[attenuated.label]["tau_v"],
)
