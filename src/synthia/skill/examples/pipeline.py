"""Pipeline: one model over many galaxies.

Synthesizer 1.2.1.dev. Verify signatures against the installed version.
Needs test_grid. Runs offline.

Use for: batch, many galaxies at once, survey, run N galaxies, scale up.

Assumptions to review:
  - the grid fixes the SPS model, IMF and photoionisation setup;
  - three galaxies differing only in burst age (10, 100, 500 Myr);
  - log10(Z) = -2 and 1e8 Msun formed in each, all at z = 1;
  - incident emission only, so no nebular reprocessing and no dust.
"""

import numpy as np
from synthesizer.emission_models import IncidentEmission
from synthesizer.grid import Grid
from synthesizer.instruments import UVJ, PhotometricInstrument
from synthesizer.parametric import SFH, Galaxy, Stars, ZDist
from synthesizer.pipeline import Pipeline
from unyt import Msun, Myr, angstrom

grid = Grid("test_grid")

galaxies = [
    Galaxy(
        Stars(
            grid.log10ages,
            grid.metallicities,
            sf_hist=SFH.Constant(max_age=age * Myr),
            metal_dist=ZDist.DeltaConstant(log10metallicity=-2.0),
            initial_mass=1e8 * Msun,
        ),
        redshift=1.0,
    )
    for age in (10, 100, 500)
]

lam = np.linspace(1e3, 1e5, 1000) * angstrom
instrument = PhotometricInstrument(label="UVJ", filters=UVJ(new_lam=lam))

# emission_model is the ONLY required constructor argument; instruments
# are passed to the get_* calls, not to the constructor. nthreads > 1
# raises without an OpenMP build.
pipeline = Pipeline(IncidentEmission(grid), nthreads=1, verbose=1)
pipeline.add_galaxies(galaxies)

# Every get_* is LAZY: it sets a flag and computes nothing until run().
pipeline.get_spectra()
pipeline.get_photometry_luminosities(instrument)
pipeline.run()

# run() leaves results in memory; write(path) is optional and is the
# library's only HDF5 output. run() also CONSUMES pipeline.galaxies.
print("galaxies after run:", len(pipeline.galaxies))
print("spectra:", pipeline.lnu_spectra["Stars"]["incident"].shape)
print("photometry:", pipeline.luminosities["Stars"]["incident"]["U"])
