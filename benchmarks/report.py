"""Summarise graded benchmark records and draw the figures.

Correctness comes first and cost second, deliberately. A figure of token
counts alone would say Synthia is worse whenever it loads a skill, which is
not the question being asked.
"""

import argparse
import json
import statistics
from pathlib import Path

ARMS = ("baseline", "synthia")
COLOURS = {"baseline": "#a8adb4", "synthia": "#087e8b"}


def load(path: Path) -> list[dict]:
    """Read a graded results file.

    Args:
        path: Path to a ``.jsonl`` file.

    Returns:
        The records.
    """
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _case_medians(records: list[dict], cases: list[str], field: str) -> dict:
    """Return one median per case and arm for a numeric field."""
    values = {}
    for arm in ARMS:
        values[arm] = [
            statistics.median(
                record[field]
                for record in records
                if record["case"] == case and record["arm"] == arm
            )
            for case in cases
        ]
    return values


def _bars(axis, records, cases, field, label):
    """Draw one horizontal grouped-bar panel."""
    import numpy
    from matplotlib.ticker import FuncFormatter

    positions = numpy.arange(len(cases))
    height = 0.36
    values = _case_medians(records, cases, field)
    for index, arm in enumerate(ARMS):
        axis.barh(
            positions + (index - 0.5) * height,
            values[arm],
            height,
            label=arm,
            color=COLOURS[arm],
        )
    baseline = sum(values["baseline"])
    synthia = sum(values["synthia"])
    change = 100 * (synthia / baseline - 1) if baseline else 0
    direction = "less" if change < 0 else "more"
    axis.set_title(
        f"{label}  |  Synthia: {abs(change):.0f}% {direction}",
        loc="left",
        fontsize=11,
        fontweight="bold",
    )
    axis.set_yticks(positions)
    axis.set_yticklabels([case.replace("-", " ") for case in cases])
    axis.invert_yaxis()
    axis.grid(axis="x", color="#dfe3e6", linewidth=0.8)
    axis.set_axisbelow(True)
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.tick_params(axis="y", length=0)
    axis.ticklabel_format(axis="x", style="plain")
    if field == "exploration_bytes":
        axis.xaxis.set_major_formatter(
            FuncFormatter(lambda value, _: f"{value / 1000:g}k")
        )
    elif field == "cost_usd":
        axis.xaxis.set_major_formatter(
            FuncFormatter(lambda value, _: f"${value:.2f}")
        )


def main(argv: list[str] | None = None) -> int:
    """Write the summary table and figures.

    Args:
        argv: Command line arguments.

    Returns:
        Process exit status.
    """
    parser = argparse.ArgumentParser(description="Report benchmark results.")
    parser.add_argument("results")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as pyplot

    records = load(Path(args.results))
    cases = [
        record["case"]
        for record in sorted(records, key=lambda row: row["case_id"])
        if record["arm"] == "baseline" and record["repeat"] == 0
    ]

    panels = [
        ("cost_usd", "Cost (USD, cache-aware)"),
        ("wall_seconds", "Wall time (seconds)"),
        ("exploration_bytes", "Unstructured exploration (bytes)"),
    ]
    figure, axes = pyplot.subplots(
        len(panels), 1, figsize=(10, 13), sharey=True
    )
    for axis, (field, label) in zip(axes, panels):
        _bars(axis, records, cases, field, label)
    axes[0].legend(
        loc="lower right", frameon=False, ncols=2, fontsize=10
    )
    completed = {
        arm: sum(
            int(bool(record.get("script_runs")))
            for record in records
            if record["arm"] == arm
        )
        for arm in ARMS
    }
    totals = {
        arm: sum(record["arm"] == arm for record in records) for arm in ARMS
    }
    figure.suptitle(
        "Targeted retrieval replaces source-code archaeology",
        x=0.08,
        y=0.995,
        ha="left",
        fontsize=17,
        fontweight="bold",
    )
    figure.text(
        0.08,
        0.968,
        "Same tasks, model, and environment. Bars show median per case. "
        f"Runnable scripts: baseline {completed['baseline']}/"
        f"{totals['baseline']}, Synthia {completed['synthia']}/"
        f"{totals['synthia']}.",
        color="#555b61",
        fontsize=10,
    )
    figure.subplots_adjust(
        left=0.24, right=0.97, top=0.945, bottom=0.05, hspace=0.28
    )

    out = (
        Path(args.out) if args.out else Path(args.results).with_suffix(".png")
    )
    figure.savefig(out, dpi=150)
    pyplot.close(figure)

    print(f"{'case':24s} {'arm':9s} {'runs':>6s} {'bad':>5s} {'$':>8s}")
    for case in cases:
        for arm in ARMS:
            rows = [
                record
                for record in records
                if record["case"] == case and record["arm"] == arm
            ]
            if not rows:
                continue
            ran = sum(int(bool(row.get("script_runs"))) for row in rows)
            bad = statistics.median(
                row.get("hallucinated_count", 0) for row in rows
            )
            cost = statistics.median(row.get("cost_usd", 0) for row in rows)
            print(
                f"{case:24s} {arm:9s} {ran:>3d}/{len(rows):<2d} "
                f"{bad:>5.0f} {cost:>8.3f}"
            )
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
