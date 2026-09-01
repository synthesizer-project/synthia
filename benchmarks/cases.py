"""Benchmark cases, fixed verbatim before any run.

Each prompt is a plain research request. None mentions Synthia, its tools,
or the Synthesizer symbols the answer is expected to use. Every prompt ends
with the same instruction to write ``answer.py`` so both arms are graded on
an artefact found the same way.
"""

WRITE_INSTRUCTION = (
    "Write the final runnable script to answer.py in the current directory."
)

#: Single-question cases. ``turns`` is one prompt each.
CASES: list[dict[str, object]] = [
    {
        "id": 1,
        "name": "dust-comparison",
        "axis": "Emission model composition, dust",
        "turns": [
            "Using the Synthesizer package, compare the spectra of a "
            "parametric stellar population with little dust attenuation "
            "and with heavy dust attenuation, and plot both."
        ],
    },
    {
        "id": 2,
        "name": "agn-far-ir",
        "axis": "AGN, multi-component, parameter reasoning",
        "turns": [
            "Using the Synthesizer package, create a galaxy with a stellar "
            "population and a black hole, and work out which black hole "
            "properties in the unified AGN model lead to a spectrum "
            "dominated in the far-infrared by the AGN."
        ],
    },
    {
        "id": 3,
        "name": "basic-parametric-sed",
        "axis": "Core parametric workflow (control: model may know this)",
        "turns": [
            "Using the Synthesizer package, generate a rest-frame stellar "
            "SED for a galaxy with a constant star formation history."
        ],
    },
    {
        "id": 4,
        "name": "observer-frame-photometry",
        "axis": "Observables, cosmology, IGM",
        "turns": [
            "Using the Synthesizer package, produce observer-frame "
            "photometry at redshift 3 for a parametric galaxy in a few "
            "broadband filters."
        ],
    },
    {
        "id": 5,
        "name": "lines-bpt",
        "axis": "Lines, ratios",
        "turns": [
            "Using the Synthesizer package, get emission line luminosities "
            "for a galaxy and place it on a BPT diagram."
        ],
    },
    {
        "id": 6,
        "name": "pipeline-scale",
        "axis": "Pipeline, scale",
        "turns": [
            "Using the Synthesizer package, run the same emission model "
            "over 500 galaxies and collect their photometry."
        ],
    },
    {
        "id": 7,
        "name": "grid-interrogation",
        "axis": "Local fact, unanswerable from memory",
        "turns": [
            "Using the Synthesizer package, tell me what metallicity range "
            "my local grid covers and whether it contains the H-beta "
            "emission line. Write a script that reports this."
        ],
    },
    {
        "id": 8,
        "name": "total-keyerror",
        "axis": "Known trap",
        "turns": [
            "I built a TotalEmission model with fesc=0 in the Synthesizer "
            "package and spectra['total'] raises a KeyError. Why, and what "
            "is the fix?"
        ],
    },
    {
        "id": 9,
        "name": "missing-units",
        "axis": "Units model",
        "turns": [
            "I passed ages as a plain numpy array to Synthesizer's particle "
            "Stars and got a MissingUnits error. Why, and what is the fix?"
        ],
    },
    {
        "id": 10,
        "name": "remote-grid-honesty",
        "axis": "Honesty control: no correct implementation exists",
        "turns": [
            "Which emission grid should I download for high-redshift JWST "
            "work with the Synthesizer package, and how do I search the "
            "available grids?"
        ],
    },
    {
        "id": 11,
        "name": "session-build-up",
        "axis": "Amortisation over a session",
        "turns": [
            "Using the Synthesizer package, build a rest-frame SED for a "
            "parametric galaxy with a constant star formation history.",
            "Now add dust attenuation to that model.",
            "Now give me observer-frame photometry at redshift 3.",
        ],
    },
    {
        "id": 12,
        "name": "session-grid-first",
        "axis": "Local facts reused across turns",
        "turns": [
            "What emission grids do I have available locally, and what do "
            "they contain?",
            "Pick one that is suitable for modelling a young stellar "
            "population with nebular emission, and say why.",
            "Now write a script that uses it to produce a spectrum.",
        ],
    },
    # V2 additions. The original twelve above remain byte-for-byte unchanged.
    {
        "id": 13,
        "name": "custom-emission-network",
        "axis": "Custom extraction and transformation graph",
        "turns": [
            "Using the Synthesizer package, build a custom stellar emission "
            "network that extracts incident emission and applies a power-law "
            "dust screen whose optical depth comes from a custom attribute "
            "attached to the stars."
        ],
    },
    {
        "id": 14,
        "name": "parameter-resolution",
        "axis": "Model parameter precedence and emitter attributes",
        "turns": [
            "In Synthesizer, explain where an emission model parameter comes "
            "from when the same name exists on the model, spectrum and stars, "
            "then demonstrate an emitter-backed string parameter in a script."
        ],
    },
    {
        "id": 15,
        "name": "model-variations",
        "axis": "Parameter lists, distributions and graph expansion",
        "turns": [
            "Using Synthesizer, evaluate one emission network at several dust "
            "optical depths without manually building one model per value, "
            "and show how the resulting spectra map back to those values."
        ],
    },
]


def prompts(case: dict[str, object]) -> list[str]:
    """Return a case's prompts with the shared write instruction appended.

    Args:
        case: One entry from :data:`CASES`.

    Returns:
        The prompts to send, in order.
    """
    turns = list(case["turns"])
    turns[-1] = f"{turns[-1]} {WRITE_INSTRUCTION}"
    return turns
