"""AGN emission with the UnifiedAGN model.

Synthesizer 1.2.1.dev. Verify signatures against the installed version.
Needs BOTH test_grid_agn-nlr and test_grid_agn-blr. Runs offline.

Use for: black hole, quasar, active galactic nucleus, torus, accretion.

Assumptions to review:
  - the two grids fix the photoionisation setup for the line regions;
  - 1e8 Msun black hole accreting at 1 Msun/yr, viewed at 45 degrees;
  - Z = 0.01 for the line regions;
  - the torus is a 1000 K greybody with emissivity index 1.5;
  - no dust attenuation, so this is the intrinsic AGN spectrum.
"""

from synthesizer.emission_models import Greybody, UnifiedAGN
from synthesizer.grid import Grid
from synthesizer.parametric import BlackHole, Galaxy
from unyt import K, Msun, deg, yr

# Both line-region grids are mandatory. The torus is a dust EMISSION
# model, not a grid.
nlr_grid = Grid("test_grid_agn-nlr")
blr_grid = Grid("test_grid_agn-blr")

# Parametric is BlackHole (singular); particle is BlackHoles (plural).
# Geometry lives on the black hole, not the model: passing inclination
# or theta_torus to UnifiedAGN raises.
black_hole = BlackHole(
    mass=1e8 * Msun,
    accretion_rate=1 * Msun / yr,
    inclination=45 * deg,
    metallicity=0.01,
)

# UnifiedAGN is a __new__ factory: the class it returns and its default
# label depend on the dust arguments. None -> "intrinsic";
# diffuse_dust_curve -> "attenuated"; both -> "total".
model = UnifiedAGN(
    nlr_grid=nlr_grid,
    blr_grid=blr_grid,
    torus_emission_model=Greybody(1000 * K, 1.5),
)
print("model label:", model.label)

sed = black_hole.get_spectra(model)
print("bolometric luminosity:", sed.bolometric_luminosity)

# Black holes attach to a galaxy like any other component. Note the
# keyword is black_holes even though the model emitter is "blackhole".
galaxy = Galaxy(black_holes=black_hole, redshift=1.0)
print("spectra:", sorted(black_hole.spectra))
print("galaxy black hole mass:", galaxy.black_holes.mass)
