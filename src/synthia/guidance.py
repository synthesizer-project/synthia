"""Search Synthia's bundled guidance and canonical examples.

The always-available corpus is the skill tree bundled inside this
package: ``SKILL.md``, ``references/*.md`` and ``examples/*.py``.

Synthesizer's own ``docs/`` and ``examples/`` directories are *not*
installed by pip, they live outside the packaged ``src/`` tree, so they
exist only in a source checkout. When such a checkout is detected the
search covers it too; otherwise the result says so rather than implying
a corpus that is not there. Synthia never downloads anything.
"""

import re
from functools import cache
from importlib.resources import files
from importlib.util import find_spec
from math import log
from pathlib import Path

from synthia._safety import (
    MAX_EXAMPLE_BYTES,
    MAX_FILE_BYTES,
    MAX_SNIPPET_CHARS,
    clean_text,
    contained_path,
    describe,
    read_capped,
    truncate,
    untrusted,
)

# The MCP SDK sends a dict return on both the text and structured
# channels, so a response costs an agent roughly twice its serialised
# size. Twelve ranked hits is enough to answer or to re-query; the
# response reports `truncated` so nothing is silently dropped.
MAX_HITS = 12
MAX_HIT_CHARS = 240
MAX_FILES = 2000
MAX_HITS_PER_FILE = 3
MAX_QUERY_CHARS = 200
# Bundled examples are short by design, so match against the whole
# file: the words a user actually searches for ("BPT", "batch",
# "synthetic") are in the code, not the docstring.
MAX_EXAMPLE_HEAD_LINES = 200

_TOKEN = re.compile(r"[a-z0-9_]+")

_SKILL_PATTERNS = ("SKILL.md", "references/*.md", "examples/*.py")
_DOC_PATTERNS = ("docs/source/**/*.rst", "docs/source/**/*.ipynb")
_EXAMPLE_PATTERNS = ("examples/*/*.py", "examples/*.py")


def _resolve_skill_root() -> Path | None:
    """Locate the bundled skill tree once, at import time.

    Returns:
        The skill directory, or ``None`` if the package resources are not
        backed by a real filesystem path.
    """
    try:
        root = Path(str(files("synthia") / "skill")).resolve()
    except Exception:  # pragma: no cover - exotic loaders only
        return None
    return root if root.is_dir() else None


SKILL_ROOT = _resolve_skill_root()


@cache
def _checkout_root() -> Path | None:
    """Locate a Synthesizer source checkout without importing it.

    ``find_spec`` runs the path finders but executes no module code, so
    this stays cheap and free of Synthesizer's import side effects.

    Returns:
        The checkout root holding ``docs`` and ``examples``, or ``None``
        when Synthesizer is missing or installed from a wheel.
    """
    try:
        spec = find_spec("synthesizer")
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.origin:
        return None
    origin = Path(spec.origin)
    if len(origin.parents) < 3 or origin.parents[1].name != "src":
        return None
    root = origin.parents[2]
    if (root / "docs").is_dir() and (root / "examples").is_dir():
        return root
    return None


def _iter_files(root: Path, patterns: tuple[str, ...]):
    """Yield readable files under a root, refusing escapes.

    Args:
        root: Directory the files must stay within.
        patterns: Glob patterns relative to ``root``.

    Yields:
        Paths contained by ``root``.
    """
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            try:
                relative = path.relative_to(root).as_posix()
                contained = contained_path(root, relative)
            except ValueError:
                continue
            if contained.is_file():
                yield contained


def _meaningful(token: str) -> bool:
    """Report whether a query token carries topic information.

    Args:
        token: A single lowercase token.

    Returns:
        False for bare numbers and single characters, which match
        incidental code detail rather than subject matter.
    """
    return len(token) > 1 and not token.isdigit()


def _tokenise(text: str) -> tuple[list[str], str]:
    """Reduce a caller-supplied string to search tokens.

    Args:
        text: Raw query or task description.

    Returns:
        The distinct lowercase tokens and the cleaned lowercase phrase.
    """
    phrase, _ = truncate(clean_text(text).lower(), MAX_QUERY_CHARS)
    seen: list[str] = []
    for token in _TOKEN.findall(phrase):
        if token not in seen and _meaningful(token):
            seen.append(token)
    return seen, phrase.strip()


def _score(lowered: str, tokens: list[str], phrase: str) -> int:
    """Score one line against the query.

    Args:
        lowered: Lowercase line text.
        tokens: Query tokens.
        phrase: Whole cleaned query.

    Returns:
        The number of matching tokens, plus a bonus for the whole phrase.
    """
    score = sum(1 for token in tokens if token in lowered)
    if score and len(phrase) > 2 and phrase in lowered:
        score += 2
    return score


def _scan(
    root: Path,
    corpus: str,
    patterns: tuple[str, ...],
    tokens: list[str],
    phrase: str,
    budget: int,
) -> tuple[list[dict[str, object]], int, bool]:
    """Scan one corpus line by line.

    ponytail: linear substring scan, a few dozen small files. Ceiling is
    roughly a few thousand files or a few MB per query; add an index only
    if the corpus ever outgrows that.

    Args:
        root: Corpus root directory.
        corpus: Name reported for hits from this root.
        patterns: Glob patterns relative to ``root``.
        tokens: Query tokens.
        phrase: Whole cleaned query.
        budget: Maximum number of files to open.

    Returns:
        The hits, the number of files scanned, and whether a cap bit.
    """
    hits: list[dict[str, object]] = []
    scanned = 0
    truncated = False
    for path in _iter_files(root, patterns):
        if scanned >= budget:
            truncated = True
            break
        scanned += 1
        try:
            text = read_capped(path, MAX_FILE_BYTES)
        except (OSError, ValueError):
            continue
        lines = text.splitlines()
        found = 0
        for number, line in enumerate(lines, 1):
            score = _score(line.lower(), tokens, phrase)
            if not score:
                continue
            snippet = "\n".join(lines[number - 1 : number + 2])
            hits.append(
                {
                    "corpus": corpus,
                    "path": str(path),
                    "line": number,
                    "score": score,
                    "snippet": untrusted(snippet, str(path), MAX_HIT_CHARS),
                }
            )
            found += 1
            if found >= MAX_HITS_PER_FILE:
                truncated = True
                break
    return hits, scanned, truncated


def search_documentation(query: str) -> dict[str, object]:
    """Search the bundled skill tree and any Synthesizer checkout docs.

    Args:
        query: Words to look for. Matching is plain substring and token
            matching, not a query language.

    Returns:
        A mapping with ``query``, ``corpora_searched`` (a list of
        ``{corpus, root}`` recording what was actually covered),
        ``corpora_unavailable`` explaining, in a sentence each, any
        corpus that was not,
        ``files_scanned``, ``hit_count``, and ``hits``. Each hit is
        ``{corpus, path, line, score, snippet}`` where ``snippet`` is an
        untrusted-content envelope. ``truncated`` records whether a cap
        bit, ``notes`` explains an unsearchable query, and ``error`` is
        present only when the search itself failed.

        The bundled skill tree is always searched; a Synthesizer source
        checkout is searched in addition to it when one is found, never
        instead of it. Synthesizer's own documentation is not installed
        by pip, so it is unavailable unless such a checkout exists.
    """
    result: dict[str, object] = {
        "query": clean_text(str(query))[:MAX_QUERY_CHARS],
        "corpora_searched": [],
        "corpora_unavailable": [],
        "files_scanned": 0,
        "hit_count": 0,
        "hits": [],
        "truncated": False,
    }
    try:
        tokens, phrase = _tokenise(str(query))
        if not tokens:
            result["notes"] = ["Query contained no searchable words."]
            return result

        searched: list[dict[str, str]] = []
        unavailable: list[str] = []
        hits: list[dict[str, object]] = []
        scanned = 0
        truncated = False

        if SKILL_ROOT is None:
            unavailable.append(
                "Bundled skill tree is not available as files on disk."
            )
        else:
            found, count, cut = _scan(
                SKILL_ROOT,
                "bundled_skill",
                _SKILL_PATTERNS,
                tokens,
                phrase,
                MAX_FILES,
            )
            hits += found
            scanned += count
            truncated |= cut
            searched.append(
                {"corpus": "bundled_skill", "root": str(SKILL_ROOT)}
            )

        checkout = _checkout_root()
        if checkout is None:
            unavailable.append(
                "Synthesizer's docs/ and examples/ are not shipped in an "
                "installed package; no source checkout was found, so "
                "installed-version documentation was not searched."
            )
        else:
            found, count, cut = _scan(
                checkout,
                "checkout_docs",
                _DOC_PATTERNS,
                tokens,
                phrase,
                MAX_FILES - scanned,
            )
            hits += found
            scanned += count
            truncated |= cut
            searched.append(
                {"corpus": "checkout_docs", "root": str(checkout / "docs")}
            )

        hits.sort(key=lambda hit: (-hit["score"], hit["path"], hit["line"]))
        result["corpora_searched"] = searched
        result["corpora_unavailable"] = unavailable
        result["files_scanned"] = scanned
        result["hit_count"] = min(len(hits), MAX_HITS)
        result["hits"] = hits[:MAX_HITS]
        result["truncated"] = truncated or len(hits) > MAX_HITS
    except Exception as error:  # never raise at the MCP boundary
        result["error"] = describe(error)
    return result


def _head(path: Path, limit: int = MAX_EXAMPLE_HEAD_LINES) -> str:
    """Read the leading lines of a file, where a description lives.

    Args:
        path: File to read.
        limit: Number of leading lines to keep.

    Returns:
        The leading text, or an empty string if the file is unreadable.
    """
    try:
        text = read_capped(path, MAX_EXAMPLE_BYTES)
    except (OSError, ValueError):
        return ""
    return "\n".join(text.splitlines()[:limit])


def _best(
    root: Path, patterns: tuple[str, ...], tokens: list[str], phrase: str
) -> tuple[Path | None, int, list[dict[str, object]]]:
    """Pick the closest matching example file.

    Query tokens are weighted by how rare they are across the examples.
    Without that, words every example uses — spectra, grid, galaxy —
    contribute as much as the one distinctive word in the query, and the
    file that happens to repeat them most wins. The filename is a
    curated label, so a match there counts for more than one in the
    body.

    Args:
        root: Directory to search.
        patterns: Glob patterns relative to ``root``.
        tokens: Task tokens.
        phrase: Whole cleaned task description.

    Returns:
        The best matching path, its score, and the next few candidates
        with theirs. Scores are comparable only within one query, so the
        runners-up are what let a caller judge a close call.
    """
    documents = []
    for path in _iter_files(root, patterns):
        stem = path.stem.lower().replace("-", " ").replace("_", " ")
        documents.append((path, stem, _head(path).lower()))
    if not documents:
        return None, 0, []

    frequency = {
        token: sum(
            1 for _, stem, head in documents if token in stem or token in head
        )
        for token in tokens
    }
    total = len(documents)
    weights = {
        token: log(1 + total / count) if count else 0.0
        for token, count in frequency.items()
    }

    ranked: list[tuple[float, Path]] = []
    best: Path | None = None
    best_score = 0.0
    for path, stem, head in documents:
        score = sum(w for t, w in weights.items() if t in head)
        score += 2 * sum(w for t, w in weights.items() if t in stem)
        if phrase and len(phrase) > 2:
            score += 2 * weights.get(phrase, 1.0) * (phrase in head)
        ranked.append((score, path))
        if score > best_score:
            best, best_score = path, score
    runners_up = [
        {"name": path.stem, "score": round(score * 10)}
        for score, path in sorted(ranked, key=lambda item: -item[0])[1:4]
        if score > 0
    ]
    return best, round(best_score * 10), runners_up


def find_example(task: str) -> dict[str, object]:
    """Find the closest canonical example for a task.

    Args:
        task: Short description of what the user wants to do.

    Returns:
        A mapping with ``task`` and ``example``.
        ``available_examples`` lists every bundled example name, so
        another can be requested when the match is wrong, and
        ``other_candidates`` ranks the next best matches so a close call
        is visible. ``example`` is ``None`` when nothing
        matched, otherwise ``{path, score, source}`` where ``source`` is
        the complete example in an untrusted-content envelope, capped at
        32 KiB. ``checkout_example`` is the nearest match in a
        Synthesizer source checkout when one exists, and carries only an
        ``excerpt``, not the whole file. ``notes`` explains an empty
        result and ``error`` is present only when the search failed.
    """
    result: dict[str, object] = {
        "task": clean_text(str(task))[:MAX_QUERY_CHARS],
        "example": None,
        "checkout_example": None,
        "notes": [],
    }
    notes: list[str] = result["notes"]
    try:
        tokens, phrase = _tokenise(str(task))
        if SKILL_ROOT is None:
            notes.append("Bundled examples are not available on disk.")
        else:
            examples = SKILL_ROOT / "examples"
            available = (
                sorted(path.name for path in _iter_files(examples, ("*.py",)))
                if examples.is_dir()
                else []
            )
            result["available_examples"] = available
            best, score, runners_up = (
                _best(examples, ("*.py",), tokens, phrase)
                if available and tokens
                else (None, 0, [])
            )
            if runners_up:
                result["other_candidates"] = runners_up
            if best is None:
                notes.append(
                    "No bundled example matched; "
                    f"{len(available)} example(s) available."
                )
            else:
                result["example"] = {
                    "path": str(best),
                    "score": score,
                    "source": untrusted(
                        read_capped(best, MAX_EXAMPLE_BYTES),
                        str(best),
                        MAX_EXAMPLE_BYTES,
                    ),
                }

        checkout = _checkout_root()
        if checkout is None:
            notes.append(
                "Synthesizer's examples/ directory ships only in a source "
                "checkout; none was found."
            )
        elif tokens:
            best, score, _ = _best(checkout, _EXAMPLE_PATTERNS, tokens, phrase)
            if best is not None:
                result["checkout_example"] = {
                    "path": str(best),
                    "score": score,
                    "excerpt": untrusted(
                        _head(best), str(best), MAX_SNIPPET_CHARS
                    ),
                }
    except Exception as error:  # never raise at the MCP boundary
        result["error"] = describe(error)
    return result
