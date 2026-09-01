# Synthia evaluation — plan

## Question

Does an agent with Synthia produce correct Synthesizer code more often than
the same agent without it, and at what cost in time and tokens?

Correctness is the outcome. Time and tokens are the cost of reaching it.

Whether Synthia raises or lowers that cost is genuinely open, and depends on
what the baseline does when it does not know the answer:

- If the baseline **guesses from memory**, it is cheap and often wrong.
  Synthia costs more and buys correctness.
- If the baseline **explores the source** — greps `synthesizer/`, opens
  `pacman_model.py`, `grid.py`, pokes at an HDF5 grid — it is expensive *and*
  may still be wrong. Synthia costs less **and** buys correctness.

A capable agent does the second, and that is the case Synthia's tools are
shaped for: `inspect_synthesizer_api` returns a signature and a `path:lineno`
instead of a source file, `find_example` returns one 55-line script instead of
a directory sweep, `inspect_local_grid` returns capped structured metadata
instead of an exploratory HDF5 session. Targeted retrieval replacing
unstructured reading is the mechanism under test, not an incidental cost.

So the benchmark must measure the mechanism, not only the totals.

## Arms

| Arm | Setup |
|---|---|
| `baseline` | Agent, Synthesizer installed, no skill, no MCP server. |
| `synthia` | Same agent and environment, plus the bundled skill and `synthia-mcp`. |

Everything else identical: same model, same prompt, same working directory,
same Synthesizer version, same local grids.

## Metrics

Per run:

- `runs` — the produced script executes to completion, exit status 0.
- `correct` — rubric score 0-3 (below), graded blind.
- `hallucinated_symbols` — count of referenced `synthesizer.*` names that do
  not exist in the installed version. Objective; obtained by parsing the
  script and resolving each name.
- `wall_seconds` — from `duration_ms`.
- `tokens_in`, `tokens_out`, and `cache_read_input_tokens` **kept separate**.
- `cost_usd` — from `total_cost_usd`.
- `turns` — from `num_turns`.
- `exploration_bytes` — bytes returned by file-reading and searching tools
  (`Read`, `Grep`, `Glob`, `Bash` reads) targeting the Synthesizer source or
  grid files. **This is the discriminator** between the two baseline
  behaviours above, and the mechanism by which Synthia can be cheaper.
- `synthia_tool_calls`, `synthia_tool_bytes` — the same accounting for
  Synthia's tools, so targeted retrieval can be compared directly against
  unstructured reading.

### Derived

- `cost_per_correct` — total cost across repeats divided by the number scoring
  2 or 3. A cheap wrong answer is not cheaper than an expensive right one, and
  this is the number that says so.

Cache-read tokens must not be added to fresh input tokens. The skill is
context that gets cached and re-read, so a raw sum would charge Synthia full
price for tokens billed at a fraction of it. `total_cost_usd` already accounts
for cache pricing and is therefore the fairest single cost number; report it
alongside the raw counts rather than instead of them.

Primary outcome: `runs` and `correct`. Secondary: cost.

### Rubric

Scored against the produced script, not the prose around it.

| Score | Meaning |
|---|---|
| 0 | Does not run, or does not attempt the task. |
| 1 | Runs, but the science is wrong (wrong workflow, wrong emission, units wrong). |
| 2 | Runs and is scientifically defensible, but incomplete or ignores a stated constraint. |
| 3 | Runs, correct, and states its scientific assumptions. |

## Test cases

Twelve cases: ten single questions and two multi-turn sessions. Each is a
plain research request; none mentions Synthia, tools, or
any Synthesizer symbol the agent is being tested on.

| # | Case | Axis tested |
|---|---|---|
| 1 | Compare spectra of a parametric stellar population with little and with heavy dust attenuation. | Emission model composition, dust |
| 2 | Build a galaxy with a stellar population and a black hole; compare which UnifiedAGN parameters give a far-IR spectrum dominated by the AGN. | AGN, multi-component, parameter reasoning |
| 3 | Generate a rest-frame SED for a constant star formation history. | Core parametric workflow |
| 4 | Produce observer-frame photometry at z = 3 in a few bands. | Observables, cosmology, IGM |
| 5 | Get emission line luminosities and place the galaxy on a BPT diagram. | Lines, ratios |
| 6 | Run the same emission model over 500 galaxies. | Pipeline, scale |
| 7 | Does the local grid cover the metallicity range needed, and does it contain H-beta? | Local fact, no memory can answer |
| 8 | Diagnose: `spectra['total']` raises KeyError after building TotalEmission with fesc=0. | Known trap |
| 9 | Diagnose: `MissingUnits` when passing ages as a plain numpy array. | Units model |
| 10 | Which grid should be downloaded for high-redshift JWST work? | **Honesty control** |
| 11 | Session: build a parametric SED, then add dust, then add photometry at z = 3. | Amortisation over a session |
| 12 | Session: inspect the local grid, pick a suitable one, then write a script that uses it. | Local facts reused across turns |

Case 10 has no correct implementation — the remote catalogue does not exist.
It scores on whether the agent says so or invents an API. Baseline is expected
to hallucinate; Synthia is expected to decline and point at
`synthesizer-download`.

Case 7 is the case no amount of model knowledge can answer, and case 3 is the
case a good model can probably answer unaided. Both are kept deliberately: a
benchmark of only favourable cases measures nothing.

## Harness

`claude -p "<prompt>" --output-format json` returns the result plus usage.
Verified available: `usage.input_tokens`, `usage.output_tokens`,
`usage.cache_read_input_tokens`, `duration_ms`, `num_turns` and
`total_cost_usd`. One run is one temporary `HOME`:

- `baseline`: empty `HOME`, no skill directory, no MCP registration.
- `synthia`: `synthia-install` into that `HOME`, pinned to the Synthesizer
  environment.

Working directory is a fresh temporary directory per run so nothing carries
over. The Synthesizer environment and grid directory are shared and read-only.

### Sessions, not only single questions

The skill is a **fixed, cached** cost paid once per session. Exploration is a
**per-question, uncached** cost paid again for every question. So the arms are
expected to cross over somewhere: Synthia may look worse on one isolated
question and better across a working session.

Cases 11 and 12 are therefore multi-turn sessions of three related requests in
one context, scored on the final state. Isolated-question results alone would
measure the least favourable point on that curve and would not reflect how the
tool is used.

Repeats: **n = 3 per cell**, arms interleaved rather than run in blocks, so
drift in service latency does not land entirely on one arm. Report median and
full range, never a single run. 12 cases x 2 arms x 3 repeats = 72 agent runs (the two sessions are three
turns each, so ~84 turns); budget accordingly.

## Grading

Two stages.

1. **Automatic.** Extract the script from the transcript, run it in the
   Synthesizer environment with a timeout, record exit status and stderr.
   Resolve every `synthesizer.*` name it references against the installed
   package to count hallucinated symbols.
2. **Blind rubric.** A separate grading agent sees the prompt and the script,
   with no indication of which arm produced it and no access to Synthia's
   skill text. Transcripts are shuffled before grading. Grading prompt fixed
   in advance and stored with the results.

Not grading with Synthia's own reference text matters: those files assert what
correct usage looks like, so using them to grade would score the `synthia` arm
against its own answer key.

## Outputs

- `benchmarks/results/<timestamp>.json` — one record per run, raw.
- `benchmarks/report.py` — reads the JSON, emits the figures and a summary table.

Figures:

1. **Correctness by case** — grouped bars, rubric score per arm per case, with
   the range across repeats.
1b. **Cost per correct answer** — grouped bars. Together with the above, this
   is the headline: correctness achieved, and what it cost to achieve it.
2. **Cost by case** — grouped bars, median `cost_usd` and median wall time per
   arm, with fresh and cached input tokens stacked separately. Plotted beside
   the correctness figure, never instead of it.
3. **Hallucinated symbols by case** — grouped bars. Expected to be the
   cleanest separation between arms.

## Threats to validity

State these with the results.

- **Contamination.** The model may already know Synthesizer from training. This
  compresses the gap and makes any measured improvement a lower bound.
- **Version skew.** Synthesizer 1.2.1.dev is recent; the baseline may be
  answering from an older API it saw in training. That is a real effect
  Synthia exists to fix, not a confound to remove — but say so plainly.
- **Small n.** Three repeats detects large effects only. Do not report
  differences smaller than the observed spread.
- **Case selection.** Ten cases chosen by the same people who built the tool.
  Cases 3 and 10 are included as controls precisely to expose this.
- **Grader bias.** Mitigated by blinding and by withholding the skill text.
- **Prompt phrasing.** Fixed verbatim before any run, and stored with the
  results.

## Pre-registered expectations

Recorded before running, so the analysis cannot be steered afterwards.

- Correctness: **higher** for `synthia` on cases 1, 2, 5, 6, 7, 8, 9.
- No correctness difference expected on case 3.
- Case 10: baseline invents an API; `synthia` declines. If the baseline also
  declines, report that honestly.
- `exploration_bytes`: **much higher** for `baseline`, and this is the
  mechanism. If the baseline instead guesses without reading, the token
  comparison flips and Synthia will look expensive — record which happened
  per case rather than assuming.
- Cost, single questions: **direction not predicted.** Case 7 is the clearest
  test — it cannot be answered from memory, so the baseline must explore and
  `synthia` should be cheaper outright. Cases 3 and 8 are where `synthia` is
  most likely to cost more.
- Cost, sessions (11, 12): **lower** for `synthia`, because the skill is paid
  once and cached while exploration repeats per question.
- `cost_per_correct`: **lower** for `synthia` overall. This is the headline
  claim; the raw token totals are not.

If correctness does not improve, the honest conclusion is that Synthia costs
tokens and buys nothing, and that is the result to publish.

## Order of work

1. Fix the twelve prompts verbatim. Commit them before running anything.
2. Build the harness: run one case, one arm, end to end, and confirm the JSON
   carries usage.
3. Build the automatic grader and validate it against three hand-checked scripts.
4. Full run, interleaved, n = 3.
5. Blind rubric grading.
6. `report.py`, figures, and a short written summary that leads with
   correctness and reports cost beside it.
