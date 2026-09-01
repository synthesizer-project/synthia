"""Run the benchmark and write one JSON record per run.

Arms are interleaved rather than run in blocks, so drift in service latency
does not land entirely on one arm.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cases import CASES  # noqa: E402
from harness import ARMS, run_case  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"


def preflight(server: Path, model: str, backend: str, env: dict) -> bool:
    """Verify arm isolation and MCP availability before paid benchmark work."""
    synthesizer_file = "synthesizer-source/synthesizer/__init__.py"
    prompts = {
        "baseline": (
            f"Preflight only. Use Read on {synthesizer_file}. Do not search "
            "any other path. Then write a script that prints 'preflight'."
        ),
        "synthia": (
            "Preflight only. Call synthia_inspect_environment once, then "
            "write "
            "a script that prints 'preflight'."
        ),
    }
    for arm in ARMS:
        case = {
            "id": 0,
            "name": "preflight",
            "axis": "harness",
            "turns": [prompts[arm]],
        }
        with tempfile.TemporaryDirectory(prefix="synthia-preflight-") as path:
            record = run_case(
                case,
                arm,
                0,
                server,
                Path(path),
                model,
                timeout=60,
                env=env,
                backend=backend,
            )
        if record["errors"] or not record["answer_written"]:
            reason = (
                record["errors"][0] if record["errors"] else "no answer.py"
            )
            print(f"preflight {arm} failed: {reason}", file=sys.stderr)
            return False
        if arm == "baseline":
            reads = [
                str(
                    item.get("input", {}).get("file_path")
                    or item.get("input", {}).get("filePath")
                    or ""
                )
                for item in record["tool_trace"]
                if item["tool"].lower() == "read"
            ]
            if not any(path.endswith(synthesizer_file) for path in reads):
                print(
                    "preflight baseline cannot read Synthesizer",
                    file=sys.stderr,
                )
                return False
            if record["synthia_tool_calls"]:
                print(
                    "preflight baseline reached Synthia MCP", file=sys.stderr
                )
                return False
        elif record["synthia_tool_calls"] == 0:
            print("preflight Synthia MCP was not called", file=sys.stderr)
            return False
    print("preflight passed", flush=True)
    return True


def main(argv: list[str] | None = None) -> int:
    """Run the benchmark.

    Args:
        argv: Command line arguments.

    Returns:
        Process exit status.
    """
    parser = argparse.ArgumentParser(description="Run the Synthia benchmark.")
    parser.add_argument("--env", required=True, help="Synthesizer env prefix")
    parser.add_argument(
        "--backend", choices=("claude", "opencode"), default="claude"
    )
    parser.add_argument("--model", default="")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--cases", default="", help="Comma separated ids")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--out", default="")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    model = args.model or (
        "opencode/mimo-v2.5-free"
        if args.backend == "opencode"
        else "claude-sonnet-5"
    )

    prefix = Path(args.env).resolve()
    server = prefix / "bin" / "python"
    if not server.is_file():
        print(f"no python in {prefix}", file=sys.stderr)
        return 1
    probe = subprocess.run(
        [
            str(server),
            "-c",
            "import importlib.util; "
            "print(int(importlib.util.find_spec('synthia') is not None))",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if probe.stdout.strip() == "1":
        print(
            "benchmark env contains Synthia; use a clean Synthesizer env",
            file=sys.stderr,
        )
        return 1

    wanted = (
        {int(value) for value in args.cases.split(",") if value.strip()}
        if args.cases
        else {case["id"] for case in CASES}
    )
    selected = [case for case in CASES if case["id"] in wanted]

    env = dict(os.environ)
    env["PATH"] = f"{prefix / 'bin'}{os.pathsep}{env['PATH']}"
    if "SYNTHESIZER_GRID_DIR" not in env:
        grid_probe = subprocess.run(
            [
                str(server),
                "-c",
                "from synthesizer.data.initialise import get_grids_dir; "
                "print(get_grids_dir())",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if grid_probe.returncode:
            print(grid_probe.stderr.strip(), file=sys.stderr)
            return 1
        env["SYNTHESIZER_GRID_DIR"] = (
            grid_probe.stdout.strip().splitlines()[-1]
        )

    if args.preflight_only and args.skip_preflight:
        parser.error("--preflight-only conflicts with --skip-preflight")
    if not args.skip_preflight:
        if not preflight(server, model, args.backend, env):
            return 1
        if args.preflight_only:
            return 0

    RESULTS.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = Path(args.out) if args.out else RESULTS / f"{stamp}.jsonl"

    total = len(selected) * len(ARMS) * args.repeats
    done = 0
    with out.open("a", encoding="utf-8") as handle:
        for repeat in range(args.repeats):
            for case in selected:
                for arm in ARMS:
                    done += 1
                    label = f"[{done}/{total}] {case['name']} {arm} r{repeat}"
                    print(label, flush=True)
                    with tempfile.TemporaryDirectory(
                        prefix="synthia-bench-"
                    ) as directory:
                        record = run_case(
                            case,
                            arm,
                            repeat,
                            server,
                            Path(directory),
                            model,
                            timeout=args.timeout,
                            env=env,
                            backend=args.backend,
                        )
                    handle.write(json.dumps(record) + "\n")
                    handle.flush()
                    print(
                        f"    {record['wall_seconds']}s "
                        f"${record['cost_usd']:.3f} "
                        f"explore={record['exploration_bytes']} "
                        f"tools={record['synthia_tool_calls']}",
                        flush=True,
                    )
                    if record["errors"]:
                        print(record["errors"][0], file=sys.stderr)
                        return 1
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
