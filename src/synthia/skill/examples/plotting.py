"""Plotting helpers, written to a file rather than a window.

Synthesizer 1.2.1.dev. Verify signatures against the installed version.
Needs test_grid. Runs offline and writes spectra.png to the CWD.

Use for: plot, figure, chart, save an image of a spectrum.

Assumptions to review:
  - the grid fixes the SPS model, IMF and photoionisation setup;
  - constant SF over 100 Myr, Z = 0.01, 1e9 Msun formed;
  - the comparison is incident versus reprocessed, i.e. the effect of
    the nebula only -- no dust is involved.
"""

import matplotlib

matplotlib.use("Agg")

from synthesizer.emission_models import IncidentEmission, ReprocessedEmission
from synthesizer.emissions import plot_spectra
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
galaxy.stars.get_spectra(ReprocessedEmission(grid))
galaxy.stars.get_spectra(IncidentEmission(grid))

# plot_spectra takes a single Sed or a labelled dict and returns
# (fig, ax). It is the cleanest helper in the library.
fig, ax = plot_spectra(
    {
        "incident": galaxy.stars.spectra["incident"],
        "reprocessed": galaxy.stars.spectra["reprocessed"],
    },
    show=False,
)
fig.savefig("spectra.png", dpi=100, bbox_inches="tight")
print("wrote spectra.png")

# Siblings: Sed.plot_spectra, Sed.plot_spectra_as_rainbow,
# Image.plot_img, LineCollection.plot_lines and
# FilterCollection.plot_transmission_curves.
# ALWAYS pass show=False -- several default to show=True, and a few
# (SFH.Common.plot_sfh, Morphology.plot_density_grid) return None and
# call plt.show() unconditionally.
