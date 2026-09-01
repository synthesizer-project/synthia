"""Photometry: rest-frame luminosities and observer-frame fluxes.

Synthesizer 1.2.1.dev. Verify signatures against the installed version.
Needs test_grid. Runs offline: every filter here is defined locally.

Use for: filters, magnitudes, broadband, fluxes, colours.

Assumptions to review:
  - the grid fixes the SPS model, IMF and photoionisation setup;
  - exponentially declining SF, tau = 200 Myr over 1 Gyr, Z = 0.005;
  - 1e9 Msun formed, no dust (see emission-models.py for dust);
  - Planck18 cosmology, observed at z = 3, Madau96 IGM attenuation.
"""

import numpy as np
from astropy.cosmology import Planck18
from synthesizer.emission_models import IncidentEmission
from synthesizer.emission_models.attenuation import Madau96
from synthesizer.grid import Grid
from synthesizer.instruments import UVJ, FilterCollection
from synthesizer.parametric import SFH, Galaxy, Stars, ZDist
from unyt import Gyr, Msun, Myr, angstrom

grid = Grid("test_grid")
stars = Stars(
    grid.log10ages,
    grid.metallicities,
    sf_hist=SFH.DecliningExponential(tau=200 * Myr, max_age=1 * Gyr),
    metal_dist=ZDist.DeltaConstant(metallicity=0.005),
    initial_mass=1e9 * Msun,
)
galaxy = Galaxy(stars, redshift=3.0)
sed = galaxy.stars.get_spectra(IncidentEmission(grid))

# Offline filter routes, in ascending order of effort: UVJ top-hats,
# a tophat_dict, or generic_dict with your own transmission arrays.
# Real work usually uses SVO codes -- FilterCollection(filter_codes=
# ["JWST/NIRCam.F444W"]) -- but those DOWNLOAD on first use.
uvj = UVJ(new_lam=grid.lam)

# Called on the COMPONENT, get_photo_lnu returns a plain dict keyed by
# SPECTRA LABEL (a PhotometryCollection per label), and covers every
# spectrum unless limit_to is given. limit_to must be a LIST: a bare
# string is iterated character by character and raises KeyError.
photo_lnu = galaxy.stars.get_photo_lnu(uvj, limit_to=["incident"])
print("component -> keyed by label:", sorted(photo_lnu))
print("  incident V:", photo_lnu["incident"]["V"])

# Fluxes need a cosmology and a redshift; until get_fnu is called there
# is no fnu to integrate, and get_photo_fnu fails.
sed.get_fnu(Planck18, 3.0, igm=Madau96)

bands = FilterCollection(
    tophat_dict={
        "blue": {"lam_min": 8000 * angstrom, "lam_max": 12000 * angstrom},
        "red": {"lam_eff": 30000 * angstrom, "lam_fwhm": 8000 * angstrom},
    },
    new_lam=np.linspace(5e3, 6e4, 2000) * angstrom,
)

# Called on the SED, get_photo_fnu returns a PhotometryCollection keyed
# directly by FILTER CODE -- one level shallower than the component
# method above. Confusing the two is the usual KeyError here.
photo_fnu = sed.get_photo_fnu(bands)
print("sed -> keyed by filter code:", photo_fnu["red"])
