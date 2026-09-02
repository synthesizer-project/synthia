"""Inspect the local Python and Synthesizer environment.

Two tools live here. :func:`inspect_environment` answers "what is on this
machine" without importing Synthesizer, so it is cheap and free of side
effects. :func:`inspect_synthesizer_api` resolves a public dotted name in
the installed Synthesizer, which requires importing it.

Importing Synthesizer is not free. It takes roughly 1.7-2.0 seconds and
``synthesizer/__init__.py`` calls ``synth_initialise()``, which creates
the ``base``, ``data``, ``grids``, ``instrument_cache`` and
``svo_filter_cache`` directories and writes or merges
``default_units.yml`` under the user's data directory. That is idempotent
and silent once the directories exist, but it does touch the filesystem.
Nothing here imports Synthesizer when Synthia is imported: the import
happens on the first :func:`inspect_synthesizer_api` call and is cached
by ``sys.modules`` for the rest of the process.

Dotted names arrive from a language model, so importing one is an
arbitrary-code-execution primitive. Resolution is restricted to
identifier-shaped, non-underscore segments rooted at ``synthesizer``.

Provenance is established *before* anything is imported. The installed
package is located by asking the ``sys.meta_path`` finders directly
rather than through :func:`importlib.util.find_spec`, which consults
``sys.modules`` first and would let a poisoned entry answer for itself.
The result must be a real package, so a bare ``synthesizer.py`` earlier
on ``sys.path`` is refused before an import could execute it. After the
import, the module's own ``__spec__`` origin must be that same file, and
every submodule must live inside that package directory. The verified
location is cached for the process, so a later ``sys.path`` change
cannot re-point resolution.

Traversal of the remaining segments is static: it uses
:func:`inspect.getattr_static`, so PEP 562 module ``__getattr__`` hooks,
properties and other descriptors are not executed while walking. The
extraction step afterwards uses the ordinary :mod:`inspect` helpers
(:func:`inspect.getdoc`, :func:`inspect.signature`,
:func:`inspect.getsourcefile`), which can run descriptors on the
resolved object; that object has already been proven to live inside the
installed Synthesizer, so the boundary being defended is the
model-supplied string, not a hostile Synthesizer. Resolved objects are
never called and never repr'd.

Neither ``eval`` nor ``exec`` is used anywhere in this module. CPython
has no sandboxed ``eval``: a ``{"__builtins__": {}}`` namespace is
escaped in a single expression via
``().__class__.__base__.__subclasses__()``, so a restricted-eval design
would be security theatre.

``main()`` in :mod:`synthia.server` scrubs the current working directory
from ``sys.path`` before serving. This module neither does that nor
relies on the working directory being importable.
"""

import inspect
import keyword
import os
import re
import sys
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
from pathlib import Path
from platform import platform, python_version

from synthia._safety import (
    MAX_SNIPPET_CHARS,
    clean_text,
    truncate,
    untrusted,
)

ROOT = "synthesizer"
DISTRIBUTION = "cosmos-synthesizer"
MAX_NAME_CHARS = 200
MAX_SEGMENTS = 8

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Resolved package location, cached after the first verified import.
_verified_init: Path | None = None


def _detail(error: BaseException) -> str:
    """Summarise an exception as short, cleaned, quotable text."""
    text = clean_text(f"{type(error).__name__}: {error}")
    return truncate(text, MAX_SNIPPET_CHARS)[0]


def _split_name(dotted_name: str) -> list[str]:
    """Validate a caller-supplied dotted name and split it.

    Args:
        dotted_name: Dotted path supplied by an agent.

    Returns:
        The validated segments.

    Raises:
        ValueError: If the name is malformed, contains a private,
            keyword or non-identifier segment, or is not rooted at
            ``synthesizer``. Messages never quote the input.
    """
    if not isinstance(dotted_name, str):
        raise ValueError("dotted name must be a string")
    if not dotted_name:
        raise ValueError("dotted name is empty")
    if len(dotted_name) > MAX_NAME_CHARS:
        raise ValueError("dotted name is too long")
    if "\x00" in dotted_name:
        raise ValueError("dotted name contains a null byte")

    segments = dotted_name.split(".")
    if len(segments) > MAX_SEGMENTS:
        raise ValueError("dotted name has too many segments")

    for segment in segments:
        # fullmatch, never "^...$" with match: "$" also matches before a
        # trailing newline, so "synthesizer\nos" would pass.
        if _IDENTIFIER.fullmatch(segment) is None:
            raise ValueError("dotted name segment is not an identifier")
        if segment.startswith("_"):
            raise ValueError(
                "dotted name segment is private; use inspect_environment "
                "for the version"
            )
        if keyword.iskeyword(segment):
            raise ValueError("dotted name segment is a Python keyword")

    if segments[0] != ROOT:
        raise ValueError(f"dotted name must start with {ROOT!r}")
    return segments


def _source_location(obj: object) -> str | None:
    """Return ``path:lineno`` for an object, or None if unavailable."""
    path = inspect.getsourcefile(obj)
    if path is None:
        return None
    return f"{path}:{inspect.getsourcelines(obj)[1]}"


def _safe(extract):
    """Run a zero-argument extraction, degrading any failure to None."""
    try:
        return extract()
    except Exception:
        return None


def _signature(obj: object) -> str:
    """Return a useful signature, seeing through ``__new__`` factories.

    Eight premade emission models (``UnifiedAGN``, ``TotalEmission``,
    ``PacmanEmission`` and friends) build themselves in ``__new__`` and
    inherit an uninformative ``(*args, **kwargs)`` ``__init__``. Reporting
    that tells the caller nothing and sends them into the source, so fall
    back to ``__new__`` when it is the more specific of the two.

    Args:
        obj: The already-resolved object to describe.

    Returns:
        The signature, annotated when it came from ``__new__``.
    """
    rendered = str(inspect.signature(obj))
    if not isinstance(obj, type) or rendered not in {
        "(*args, **kwargs)",
        "(*args, **kwds)",
    }:
        return rendered
    factory = inspect.getattr_static(obj, "__new__", None)
    if factory is None:
        return rendered
    try:
        from_new = str(inspect.signature(factory))
    except (TypeError, ValueError):
        return rendered
    if from_new in {"(*args, **kwargs)", "(*args, **kwds)"}:
        return rendered
    return f"{from_new}  # from __new__; cls is not passed by the caller"


def _text_attr(obj: object, name: str) -> str | None:
    """Read a string metadata attribute, or None if it is not one.

    ``getattr_static`` returns the underlying descriptor rather than the
    value for slot-backed attributes such as a function's
    ``__qualname__``, so these two well-known fields are read normally
    and anything that is not a plain string is discarded.

    Args:
        obj: Object resolved inside the installed Synthesizer.
        name: Attribute name to read.

    Returns:
        The attribute value if it is a string, otherwise None.
    """
    value = _safe(lambda: getattr(obj, name, None))
    return value if isinstance(value, str) else None


def _module_origin(module) -> Path | None:
    """Return the resolved file a module was loaded from, if any."""
    origin = getattr(getattr(module, "__spec__", None), "origin", None)
    if origin is None:
        origin = getattr(module, "__file__", None)
    return Path(origin).resolve() if origin else None


def _find_installed_init() -> Path:
    """Locate the installed Synthesizer package without importing it.

    :func:`importlib.util.find_spec` consults ``sys.modules`` before the
    finders, so a poisoned entry answers for itself. Asking the
    ``sys.meta_path`` finders directly cannot be short-circuited that
    way. The answer is cached once an import has been verified against
    it, so a later ``sys.path`` change cannot re-point resolution.

    Returns:
        The resolved path of the installed ``synthesizer/__init__.py``.

    Raises:
        ValueError: If Synthesizer is not installed, or if what is on
            ``sys.path`` is a bare ``synthesizer.py`` or a namespace
            directory rather than the installed package.
    """
    if _verified_init is not None:
        return _verified_init

    spec = None
    for finder in sys.meta_path:
        find = getattr(finder, "find_spec", None)
        if find is None:
            continue
        try:
            spec = find(ROOT, None)
        except Exception:
            spec = None
        if spec is not None:
            break

    if spec is None or not spec.origin:
        raise ValueError("synthesizer is not installed")

    origin = Path(spec.origin).resolve()
    # The installed Synthesizer is a package. A bare synthesizer.py
    # earlier on sys.path is a shadow, and is refused here, before an
    # import could execute it.
    if spec.submodule_search_locations is None or origin.name != (
        "__init__.py"
    ):
        raise ValueError("synthesizer on sys.path is not a package")
    return origin


def installed_version(root) -> tuple[str | None, str | None]:
    """Return the Synthesizer version and which source reported it.

    The module attribute and the distribution metadata genuinely
    disagree in an editable checkout, so the source is labelled.

    Args:
        root: The imported ``synthesizer`` module.

    Returns:
        The version string and its source label, either or both None.
    """
    reported = inspect.getattr_static(root, "__version__", None)
    if isinstance(reported, str):
        return reported, f"{ROOT}.__version__"
    try:
        return version(DISTRIBUTION), f"importlib.metadata:{DISTRIBUTION}"
    except PackageNotFoundError:
        return None, None


def inspect_environment() -> dict[str, object]:
    """Report Python and Synthesizer environment facts.

    Synthesizer is never imported here, so this is cheap and has no side
    effects. The price is being honest about what was checked:
    ``synthesizer_installed`` means only that a module spec with a real
    file origin was found. It is not proof that Synthesizer imports, and
    a broken C extension, the most common real failure mode for this
    package, is invisible to a spec lookup. ``import_error`` is
    therefore always None here; only :func:`inspect_synthesizer_api`,
    which does import, can populate it.

    Returns:
        A mapping with ``python_version``, ``platform``,
        the ``executable`` and ``environment`` whose Synthesizer is
        being reported on, ``synthesizer_installed``,
        ``synthesizer_version`` with the ``version_source`` that
        reported it,
        ``synthesizer_path``, ``import_error`` (always None) and
        ``synthesizer_env_vars``. Synthesizer resolves its directories
        as environment variable else platformdirs default, so only the
        ``SYNTHESIZER_*`` variables that are actually set are reported;
        resolving the defaults would mean importing the package.
    """
    try:
        spec = find_spec(ROOT)
    except (ImportError, ValueError):
        # ValueError: sys.modules["synthesizer"].__spec__ is None.
        spec = None

    # A bare directory named "synthesizer" on sys.path yields a
    # namespace spec with no origin. That is not an installation.
    installed = spec is not None and spec.origin is not None

    # Reporting the version without importing Synthesizer means reading
    # distribution metadata, which lags synthesizer.__version__ in an
    # editable checkout. inspect_synthesizer_api reports the imported
    # value instead, so the source is labelled to keep the two honest.
    try:
        synthesizer_version = version(DISTRIBUTION)
        version_source = f"importlib.metadata:{DISTRIBUTION}"
    except PackageNotFoundError:
        synthesizer_version = None
        version_source = None

    return {
        "python_version": python_version(),
        # Synthesizer is imported in this process, so this interpreter
        # decides which Synthesizer every tool reports on. Naming it
        # makes a wrong-environment installation diagnosable instead of
        # silently reporting that Synthesizer is absent.
        "executable": sys.executable,
        "environment": sys.prefix,
        "platform": platform(),
        "synthesizer_installed": installed,
        "synthesizer_version": synthesizer_version,
        "version_source": version_source,
        "synthesizer_path": spec.origin if installed else None,
        "import_error": None,
        "synthesizer_env_vars": {
            name: value
            for name, value in os.environ.items()
            if name.startswith("SYNTHESIZER_")
        },
    }


def inspect_synthesizer_api(dotted_name: str) -> dict[str, object]:
    """Look up a public Synthesizer object by dotted name.

    Resolves a name such as ``synthesizer.grid.Grid`` in the installed
    Synthesizer and reports its signature, docstring, source location
    and the installed version. The object is never called and never
    repr'd, and source bodies are never returned, only locations.

    Side effects: this imports Synthesizer. The first call in a process
    takes roughly 1.7-2.0 seconds and runs ``synth_initialise()``, which
    creates the Synthesizer ``base``, ``data``, ``grids``,
    ``instrument_cache`` and ``svo_filter_cache`` directories and writes
    or merges ``default_units.yml`` under the user's data directory. It
    is idempotent and silent when those already exist. Later calls reuse
    the cached import.

    Names are restricted: at most 200 characters and 8 dot-separated
    segments, every segment a plain identifier that is neither a Python
    keyword nor prefixed with an underscore, and the first segment
    exactly ``synthesizer``. The installed package is located before it
    is imported, so a ``synthesizer.py`` shadowing it on ``sys.path`` is
    refused rather than executed. Traversal reads attributes statically,
    so anything created lazily by a module ``__getattr__`` or by a
    property is invisible to this tool.

    Args:
        dotted_name: Public dotted path rooted at ``synthesizer``.

    Returns:
        On success a mapping with ``dotted_name``, ``module`` (the
        module prefix that was imported), ``object_type``,
        ``defining_module``, ``qualname``, ``signature``, ``doc`` (an
        untrusted-content envelope, or None), ``source`` as
        ``path:lineno``, ``version`` and ``version_source``. Any
        extraction that fails degrades to None. On rejection or import
        failure, a mapping with an ``error`` key, plus ``import_error``
        when an import raised.
    """
    try:
        segments = _split_name(dotted_name)
    except ValueError as error:
        return {"error": str(error)}

    # Locate the package before importing: this is the gate, not a
    # post-mortem. Deriving it from the imported module would compare
    # the module against itself and could never fail.
    try:
        expected_init = _find_installed_init()
    except ValueError as error:
        return {"error": str(error)}

    try:
        root = import_module(ROOT)
    except Exception as error:
        return {
            "error": "could not import synthesizer",
            "import_error": _detail(error),
        }

    # A hand-built module planted in sys.modules has no __spec__, and a
    # real one must have been loaded from the file located above.
    if getattr(root, "__spec__", None) is None or (
        _module_origin(root) != expected_init
    ):
        return {"error": "imported synthesizer is not the installed package"}

    global _verified_init
    _verified_init = expected_init
    package_dir = expected_init.parent

    # Import the longest importable module prefix, longest first.
    module = root
    imported = 1
    for stop in range(len(segments), 1, -1):
        try:
            module = import_module(".".join(segments[:stop]))
        except ImportError:
            continue
        except Exception as error:
            return {
                "error": "importing the named module failed",
                "import_error": _detail(error),
            }
        imported = stop
        break

    # The imported submodule must live inside the verified package.
    module_file = _module_origin(module)
    if module_file is None or not module_file.is_relative_to(package_dir):
        return {"error": "resolved module is outside installed synthesizer"}

    obj: object = module
    for segment in segments[imported:]:
        try:
            # getattr_static reads __dict__ and the MRO only, so no
            # descriptor, property or module __getattr__ ever runs.
            obj = inspect.getattr_static(obj, segment)
        except Exception:
            return {"error": "no such attribute on the resolved object"}

    doc = _safe(lambda: inspect.getdoc(obj))
    synthesizer_version, version_source = installed_version(root)
    return {
        "dotted_name": ".".join(segments),
        "module": module.__name__,
        "object_type": type(obj).__name__,
        "defining_module": _text_attr(obj, "__module__"),
        "qualname": _text_attr(obj, "__qualname__"),
        # Synthesizer's unit decorators set __wrapped__, so following
        # it is what recovers the real parameters. It is a plain
        # attribute read on an already-verified object.
        "signature": _safe(lambda: _signature(obj)),
        "doc": untrusted(doc, ".".join(segments)) if doc else None,
        "source": _safe(lambda: _source_location(obj)),
        "version": synthesizer_version,
        "version_source": version_source,
    }
