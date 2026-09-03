"""Agent tools for the Synthesizer Python package."""

try:
    # Written at build time from the git tag, as in Synthesizer.
    from synthia._version import __version__
except ImportError:
    # Importable from an unbuilt checkout; there is no tag to report.
    __version__ = "0.0.0.dev0+source"

__all__ = [
    "__version__",
]
