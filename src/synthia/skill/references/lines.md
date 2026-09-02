# Emission Lines, Ratios and Diagrams

Lines are a `LineCollection`, not a `Sed`. The traps here are about **line
identifiers** and about which dict you are indexing; the catalogues themselves
should be enumerated, never recalled.

Enumerate rather than trust this file:

- `inspect_synthesizer_api` on `synthesizer.emissions.line_ratios` lists every
  helper it defines.
- `...line_ratios.available_ratios` and `...available_diagrams` report the
  defined ratio and diagram ids.
- `...line_ratios.ratios` and `...diagrams` report the exact line ids each one
  is built from.
- `inspect_local_grid` reports, in its `available` section, every line id the
  grid actually names. A ratio is only computable if the grid has both lines.

## Getting lines at all

`component.get_lines(line_ids, model)` produces a `LineCollection`. Two things
bite immediately:

- **`get_lines` wants full line ids**, like `"H 1 4861.32A"`. The alias
  *constants* (`from synthesizer.emissions import Ha, Hb, O3b`) expand to those
  ids and are the right way to name lines. The alias *string* `"Hb"` only works
  for indexing a `LineCollection` you already have.
- A grid must have been run through cloudy to carry lines at all. Inspect it
  first; a grid loaded with `ignore_lines=True` reports nothing, which is not
  the same as containing nothing.

`O3` is a single comma-composite id covering both components. If you want a
ratio using one component, request `O3b` and `O3r` separately.

## Ratios and diagrams

A `LineCollection` computes them for you; do not divide luminosities by hand:

```python
lines = galaxy.stars.get_lines(line_ids, model)
r = lines.get_ratio("N2")          # one ratio, by id
x, y = lines.get_diagram("BPT-NII")  # both axes of a diagram
```

`lines.available_ratios` and `lines.available_diagrams` are properties on the
collection, and they report what **this** collection can actually compute given
the lines it holds — narrower than the module-level catalogue. Check the
collection's, not the module's, before asking for a ratio.

Both `get_ratio` and `get_diagram` return the ratio itself, not a logarithm.
BPT axes are conventionally plotted as log10 of each ratio; take the log
yourself and say that you did.

## Classification lines

`line_ratios` provides the standard demarcations as both a curve and a plot
helper: `get_bpt_kewley01` / `plot_bpt_kewley01` (maximum starburst) and
`get_bpt_kauffman03` / `plot_bpt_kauffman03` (empirical star-forming
boundary). `get_diagram_labels(diagram_id)` returns axis labels for a diagram,
and `get_line_label` / `get_ratio_label` render individual names.

Kauffmann03 is defined for the N2 (BPT-NII) diagram. Do not draw a
demarcation on a diagram it was not derived for; if you plot one, name the
paper and the diagram it belongs to.

## Fluxes

`LineCollection` mirrors `Sed`: luminosities are available immediately, and
fluxes only after `get_flux(cosmo, z)`. `.flux` is `None` until then. There is
no `get_line_luminosities` method.

## Common failures

| symptom | cause |
|---|---|
| `MissingLines` on an obvious line | an alias string passed to `get_lines`; it needs the full id |
| a ratio "does not exist" | the grid lacks one of its lines — check `inspect_local_grid` |
| `.flux` is `None` | `get_flux(cosmo, z)` not called |
| ratio looks wrong by orders of magnitude | a log taken twice, or a composite id used as one component |

See `examples/lines.py` for a runnable script and `troubleshooting.md` for the
wider set of traps.
