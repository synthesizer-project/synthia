"""Grade benchmark records automatically.

Two objective checks, neither of which needs a rubric:

* does the produced script run against the installed Synthesizer, and
* does it reference Synthesizer names that do not exist in that version.

The second is the cleanest signal in the benchmark: it is a count, not a
judgement, and it is exactly what version-specific inspection is supposed
to prevent. Scientific quality still needs the blind rubric.
"""

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def referenced_names(source: str) -> set[str]:
    """Collect the Synthesizer dotted names a script references.

    Args:
        source: Python source text.

    Returns:
        Dotted names rooted at ``synthesizer``.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    aliases: dict[str, str] = {}
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "synthesizer":
                    aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "synthesizer":
                for alias in node.names:
                    if alias.name != "*":
                        bound = alias.asname or alias.name
                        aliases[bound] = f"{node.module}.{alias.name}"
    names.update(aliases.values())
    return names


def hallucinated(source: str, python: Path) -> list[str]:
    """Return referenced Synthesizer names that do not resolve.

    Args:
        source: Python source text.
        python: Interpreter with Synthesizer installed.

    Returns:
        The names that could not be resolved.
    """
    names = sorted(referenced_names(source))
    if not names:
        return []
    probe = (
        "import importlib, sys, json\n"
        f"names = {names!r}\n"
        "missing = []\n"
        "for name in names:\n"
        "    parts = name.split('.')\n"
        "    obj = None\n"
        "    for i in range(len(parts), 0, -1):\n"
        "        try:\n"
        "            obj = importlib.import_module('.'.join(parts[:i]))\n"
        "            rest = parts[i:]\n"
        "            break\n"
        "        except Exception:\n"
        "            continue\n"
        "    else:\n"
        "        missing.append(name); continue\n"
        "    for attr in rest:\n"
        "        obj = getattr(obj, attr, None)\n"
        "        if obj is None:\n"
        "            missing.append(name); break\n"
        "print(json.dumps(missing))\n"
    )
    done = subprocess.run(
        [str(python), "-c", probe], capture_output=True, text=True, timeout=300
    )
    try:
        return json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return []


def runs(source: str, python: Path, timeout: int = 300) -> tuple[bool, str]:
    """Run a script and report whether it completed.

    Args:
        source: Python source text.
        python: Interpreter with Synthesizer installed.
        timeout: Seconds allowed.

    Returns:
        Whether it exited zero, and the tail of stderr.
    """
    if not source.strip():
        return False, "no script produced"
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "answer.py"
        path.write_text(source, encoding="utf-8")
        try:
            done = subprocess.run(
                [str(python), str(path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=directory,
                # A script calling plt.show() would otherwise block until
                # the timeout and be scored as "does not run".
                env={**os.environ, "MPLBACKEND": "Agg"},
            )
        except subprocess.TimeoutExpired:
            return False, f"timed out after {timeout}s"
    return done.returncode == 0, done.stderr.strip()[-600:]


def main(argv: list[str] | None = None) -> int:
    """Grade a results file in place, writing a graded copy.

    Args:
        argv: Command line arguments.

    Returns:
        Process exit status.
    """
    parser = argparse.ArgumentParser(description="Auto-grade benchmark runs.")
    parser.add_argument("results")
    parser.add_argument("--env", required=True)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    python = Path(args.env).resolve() / "bin" / "python"
    source_path = Path(args.results)
    out = (
        Path(args.out)
        if args.out
        else source_path.with_suffix(".graded.jsonl")
    )

    with (
        source_path.open(encoding="utf-8") as handle,
        out.open("w", encoding="utf-8") as sink,
    ):
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            source = record.get("answer", "")
            ok, stderr = runs(source, python)
            record["script_runs"] = ok
            record["script_stderr"] = stderr
            record["hallucinated_symbols"] = hallucinated(source, python)
            record["hallucinated_count"] = len(record["hallucinated_symbols"])
            sink.write(json.dumps(record) + "\n")
            print(
                f"{record['case']:24s} {record['arm']:9s} "
                f"runs={ok!s:5s} bad_symbols="
                f"{record['hallucinated_count']}",
                flush=True,
            )
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
