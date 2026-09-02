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


def _column(axis, records, cases, field, label, unit, show_labels):
    """Draw one metric as a column of paired horizontal bars.

    Args:
        axis: Target axes.
        records: Graded records.
        cases: Case names, in plot order.
        field: Record field to plot.
        label: Short column heading.
        unit: Callable rendering an axis tick.
        show_labels: Whether to draw the shared case labels.
    """
    import numpy
    from matplotlib.ticker import FuncFormatter

    positions = numpy.arange(len(cases))
    height = 0.38
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
    axis.set_title(
        f"{label}   {change:+.0f}%",
        loc="left",
        fontsize=9.5,
        fontweight="bold",
        pad=6,
    )
    axis.set_yticks(positions)
    if show_labels:
        axis.set_yticklabels(
            [case.replace("-", " ") for case in cases], fontsize=8.5
        )
    axis.invert_yaxis()
    axis.grid(axis="x", color="#e3e6e9", linewidth=0.6)
    axis.set_axisbelow(True)
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.tick_params(axis="y", length=0)
    axis.tick_params(axis="x", labelsize=8)
    axis.xaxis.set_major_formatter(FuncFormatter(unit))


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

    # One row, shared case labels: three stacked panels repeated the same
    # fifteen labels and did not fit a README column.
    panels = [
        ("cost_usd", "Cost (USD)", lambda v, _: f"{v:.1f}"),
        ("wall_seconds", "Wall time (s)", lambda v, _: f"{v:.0f}"),
        (
            "exploration_bytes",
            "Source read (kB)",
            lambda v, _: f"{v / 1000:.0f}",
        ),
    ]
    figure, axes = pyplot.subplots(
        1, len(panels), figsize=(9.5, 4.2), sharey=True
    )
    for index, (axis, (field, label, unit)) in enumerate(zip(axes, panels)):
        _column(axis, records, cases, field, label, unit, index == 0)
    handles, labels = axes[0].get_legend_handles_labels()
    # A legend inside a panel lands on top of the longest bars.
    figure.legend(
        handles,
        labels,
        loc="lower center",
        ncols=2,
        frameon=False,
        fontsize=9,
        handlelength=1.4,
        bbox_to_anchor=(0.5, 0.0),
    )
    figure.tight_layout(pad=0.6, rect=(0, 0.045, 1, 1))

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
