"""Emission lines, ratios and diagnostic diagrams.

Synthesizer 1.2.1.dev. Verify signatures against the installed version.
Needs test_grid (reprocessed; it carries 254 lines). Runs offline.

Use for: emission lines, line ratios, BPT diagram, equivalent widths.

Assumptions to review:
  - the grid fixes the SPS model, IMF and photoionisation setup;
  - constant SF over 10 Myr, Z = 0.01, 1e9 Msun formed;
  - nebular emission only, with no dust attenuation applied to lines;
  - Planck18 cosmology at z = 3 for the flux conversion.
"""

from astropy.cosmology import Planck18
from synthesizer.emission_models import NebularEmission
from synthesizer.emissions import N2, Ha, Hb, O3b, O3r
from synthesizer.grid import Grid
from synthesizer.parametric import SFH, Galaxy, Stars, ZDist
from unyt import Msun, Myr

grid = Grid("test_grid")
stars = Stars(
    grid.log10ages,
    grid.metallicities,
    sf_hist=SFH.Constant(max_age=10 * Myr),
    metal_dist=ZDist.DeltaConstant(metallicity=0.01),
    initial_mass=1e9 * Msun,
)
galaxy = Galaxy(stars)

# Argument order is (line_ids, emission_model) -- ids FIRST.
# TRAP: use the imported constants -- they expand to full ids such as
# "H 1 4861.32A". The alias STRING "Hb" works for indexing a
# LineCollection but raises MissingLines here. And O3 is a single
# comma-composite id ("O 3 4958.91A, O 3 5006.84A"), so request O3b and
# O3r separately if you want a ratio built from them.
lines = galaxy.stars.get_lines([Ha, Hb, O3b, O3r, N2], NebularEmission(grid))

print("line ids:", lines.line_ids)
print("luminosity:", lines.luminosity)
print("equivalent width:", lines.equivalent_width)

# .flux is None until get_flux is called -- same rest/observed split as
# Sed.lnu versus Sed.fnu.
lines.get_flux(Planck18, 3.0)
print("flux:", lines.flux)

# Named ratios and diagrams. There is no get_line_luminosities method.
print("R3:", lines.get_ratio("R3"))
print("BPT-NII:", lines.get_diagram("BPT-NII"))
