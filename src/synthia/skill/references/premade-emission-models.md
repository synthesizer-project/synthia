# Premade Emission Models

This catalogue describes the models registered by the current Synthesizer
development version. Registries are hand-maintained candidate lists: a name can
be registered without being exported from `synthesizer.emission_models`. Confirm
the import and signature against the installed version with
`inspect_synthesizer_api` before writing code.

Dust attenuation curves are transformers, and dust emission objects are
generators. Neither is a complete emission network by itself.

## Stellar models

All stellar models act on `emitter="stellar"` unless stated otherwise.

| Model | Produces and requires | Use when |
|---|---|---|
| `IncidentEmission` | Extracts grid `incident`; needs a stellar grid | Unprocessed stellar spectrum |
| `TransmittedEmission` | Extracts `transmitted`, applies `fesc`, and may return transmitted plus escaped children | Stellar light after birth-cloud transmission |
| `NebularLineEmission` | Extracts nebular line emission; needs line-capable reprocessed grid | Lines without nebular continuum |
| `NebularContinuumEmission` | Extracts grid `linecont` continuum | Nebular continuum without lines |
| `NebularEmission` | Combines line and nebular continuum components | Complete nebular contribution |
| `EscapedEmission` | Scales incident emission by escape fraction | Ionising light escaping without reprocessing |
| `ReprocessedEmission` | Combines transmitted and nebular emission; needs a reprocessed grid | Stellar plus nebular emission, no dust screen |
| `IntrinsicEmission` | Combines reprocessed and escaped components | All emission before diffuse dust attenuation |
| `EmergentEmission` | Attenuates intrinsic emission and combines escaped light; needs a dust curve or supplied children | Dust-attenuated UV/optical spectrum |
| `TotalEmission` | Combines attenuated stellar and optional dust re-emission | Full UV-to-IR energy balance |
| `ScreenEmission` | Applies one foreground attenuation screen, with optional dust re-emission | Simple uniform screen geometry |
| `CharlotFall2000` | Birth-cloud and diffuse screens split at `age_pivot`; needs two optical depths and curves | Two-component age-dependent attenuation |
| `PacmanEmission` | Pre-wired stellar, nebular, attenuation, escape and optional dust network | One-screen complete stellar model |
| `BimodalPacmanEmission` | Pacman network with separate birth-cloud and diffuse attenuation/dust | Complete two-component geometry |
| `LOSStellarEmission` | Applies per-particle line-of-sight optical depths, normally derived from gas | Spatially resolved particle attenuation |

The stellar ladder uses conventional labels such as `incident`, `nebular`,
`reprocessed`, `intrinsic`, `escaped`, `emergent`, `attenuated`, and `total`, but
factory arguments can change both network and root label. Inspect `model.label`,
`model._models`, or the keys written to `emitter.spectra`; never assume a key.

`TotalEmission`, `IntrinsicEmission`, `TransmittedEmission`, `ScreenEmission`,
`CharlotFall2000`, `PacmanEmission`, and `BimodalPacmanEmission` can return a
different concrete model from the class called. The returned class and the
output label move independently: with `fesc=0` and no dust generator,
`PacmanEmission` and `ScreenEmission` label themselves `attenuated`, while
`TotalEmission` returns an `AttenuatedEmission` that is still labelled
`total`, and `IntrinsicEmission` is labelled `_intrinsic_reprocessed`. Read
`model.label`, or pass `label=` when a stable output key matters.

## AGN models

AGN component models use `emitter="blackhole"`. NLR and BLR extraction requires
the corresponding grids; they are not interchangeable with a stellar grid.

| Model | Produces and requires | Use when |
|---|---|---|
| `NLRIncidentEmission` | NLR grid `incident` | Disc radiation entering NLR |
| `NLRTransmittedEmission` | NLR `transmitted`, scaled by NLR covering fraction | Disc light transmitted through NLR |
| `NLREmission` | NLR grid `nebular` | Narrow-line-region emission |
| `BLRIncidentEmission` | BLR grid `incident` | Disc radiation entering BLR |
| `BLRTransmittedEmission` | BLR `transmitted`, scaled by BLR covering fraction | Disc light transmitted through BLR |
| `BLREmission` | BLR grid `nebular` | Broad-line-region emission |
| `DiscIncidentEmission` | Incident disc emission, represented by incident NLR grid spectrum | Intrinsic accretion-disc spectrum |
| `DiscTransmittedEmission` | Combines NLR and BLR transmitted disc components; needs both grids and covering fractions | Obscured/transmitted disc light |
| `DiscEscapedEmission` | Incident disc scaled by complement of NLR/BLR covering | Disc light escaping both regions |
| `DiscEmission` | Combines transmitted and escaped disc light | Total disc component |
| `TorusEmission` | Generates torus spectrum from a dust generator scaled to incident disc emission | Infrared torus component |
| `AGNIntrinsicEmission` | Combines disc, NLR, BLR and torus components | Full AGN before host attenuation |
| `UnifiedAGN` | Factory wiring all AGN components and orientation/covering behavior | Complete unified AGN model |

Covering fractions commonly default to string aliases. The value must then
exist on the black-hole emitter, for example as `covering_fraction_nlr` or
`covering_fraction_blr`, unless a numeric value is fixed on the model. Confirm
the exact names for the installed version.

## Common building blocks

These require an explicit emitter because they can be used in more than one
component network.

| Model | Produces and requires | Use when |
|---|---|---|
| `AttenuatedEmission` | Transforms `apply_to` with `dust_curve`; requires `emitter` | Apply a curve to any existing node |
| `DustEmission` | Runs `dust_emission_model`, normally scaled by intrinsic minus attenuated luminosity; requires `emitter` | Add energy-balanced IR re-emission |
| `TemplateEmission` | Generates from a fixed template and scales it; requires `emitter` | Empirical or externally supplied component |

## Dust emission generators

Pass these to a premade model's dust-emission argument or to a custom generation
node. They generate an SED but do not select an emitter or define a root label.

| Generator | Main requirements | Use when |
|---|---|---|
| `Blackbody` | Temperature with units; optional CMB heating and scaler | Single-temperature thermal spectrum |
| `Greybody` | Temperature, emissivity, optical-depth choice and optional `lam_0` | Modified blackbody far-IR model |
| `Casey12` | Temperature, emissivity and mid-IR power-law slope | Greybody plus mid-IR power law |
| `DraineLi07` | Dust-emission grid and dust-mass or gas-mass scaling; `qpah`, `umin`, `gamma`, `alpha` control templates | Draine and Li dust templates |

Dust generators need a luminosity scaler. Premade total/Pacman models wire this
from energy absorbed by dust. In a custom network, supply `intrinsic` and
`attenuated` nodes or call the generator's scaler setup as required by its
installed signature.

## Selection shortcut

- Pure stellar SPS: `IncidentEmission`.
- Stellar plus nebular: `ReprocessedEmission`.
- One dust screen: `ScreenEmission`.
- Birth-cloud plus diffuse dust: `CharlotFall2000` or
  `BimodalPacmanEmission`.
- Full energy balance: `TotalEmission` or a Pacman model plus a dust generator.
- Per-particle attenuation from geometry: `LOSStellarEmission`.
- Complete black-hole network: `UnifiedAGN`.

Every choice fixes scientific assumptions about SPS grids, nebular processing,
escape, attenuation geometry and dust energy balance. State those assumptions.
