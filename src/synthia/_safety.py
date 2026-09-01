"""Shared safety helpers for Synthia's MCP tools.

Content returned by Synthia's tools frequently originates in files the
user did not write, such as third-party docstrings or grid metadata. The
helpers here cap response sizes, strip control characters, and label
quoted content as untrusted data rather than as instructions.
"""

import os
import re
import stat
from functools import wraps
from pathlib import Path, PurePosixPath

MAX_DOCSTRING_CHARS = 4096
MAX_SNIPPET_CHARS = 500
MAX_FILE_BYTES = 1024 * 1024
MAX_EXAMPLE_BYTES = 32 * 1024

_CONTROL = re.compile(
    r"\x1b\[[0-9;]*[A-Za-z]|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
)


def clean_text(text: str) -> str:
    """Remove ANSI escape sequences and control characters.

    Args:
        text: Text read from a file or object docstring.

    Returns:
        The text without escape sequences that could corrupt an agent
        transcript or hide content from a human reviewer.
    """
    return _CONTROL.sub("", text)


def truncate(text: str, limit: int) -> tuple[str, bool]:
    """Cap text at a character limit.

    Args:
        text: Text to cap.
        limit: Maximum number of characters to keep.

    Returns:
        The capped text and whether truncation occurred.
    """
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def untrusted(
    content: str,
    source: str,
    limit: int = MAX_DOCSTRING_CHARS,
) -> dict[str, object]:
    """Wrap file-derived content in an envelope marking it as data.

    Args:
        content: Text originating outside Synthia.
        source: Path or dotted name the content came from.
        limit: Maximum number of characters to return.

    Returns:
        A mapping recording the source, whether the content was
        truncated, and the cleaned content itself.
    """
    text, truncated = truncate(clean_text(content), limit)
    return {
        "content_is_untrusted": True,
        "source": source,
        "truncated": truncated,
        "content": text,
    }


def contained_path(root: Path, relative: str) -> Path:
    """Resolve a relative path inside a root directory.

    Args:
        root: Directory the result must stay within.
        relative: Relative POSIX-style path supplied by a caller.

    Returns:
        The resolved path.

    Raises:
        ValueError: If the path is empty, absolute, traverses upwards,
            contains a null byte, or resolves outside ``root``.
    """
    if "\x00" in relative:
        raise ValueError("path contains a null byte")
    parts = PurePosixPath(relative)
    if not parts.parts:
        raise ValueError("path is empty")
    if parts.is_absolute() or parts.drive or ".." in parts.parts:
        raise ValueError(f"path is absolute or traverses upwards: {relative}")
    resolved_root = root.resolve()
    target = (resolved_root / parts).resolve()
    if not target.is_relative_to(resolved_root):
        raise ValueError(f"path escapes {root}: {relative}")
    return target


def read_capped(path: Path, max_bytes: int = MAX_FILE_BYTES) -> str:
    """Read at most ``max_bytes`` from a regular file.

    Opening without blocking and checking the file descriptor rather
    than the path prevents a named pipe or character device from
    stalling the server.

    Args:
        path: File to read.
        max_bytes: Maximum number of bytes to read.

    Returns:
        The decoded file contents, replacing undecodable bytes.

    Raises:
        ValueError: If the path is not a regular file.
    """
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"not a regular file: {path}")
        os.set_blocking(descriptor, True)
        data = os.read(descriptor, max_bytes)
    finally:
        os.close(descriptor)
    return data.decode("utf-8", errors="replace")


def describe(error: BaseException) -> str:
    """Describe an exception as a single cleaned, capped line.

    Args:
        error: Exception to describe.

    Returns:
        The exception type and message, stripped of escape sequences so
        a hostile file path cannot inject text into an agent transcript.
    """
    text, _ = truncate(
        clean_text(f"{type(error).__name__}: {error}"), MAX_SNIPPET_CHARS
    )
    return text


def safe_tool(function):
    """Stop any exception escaping a tool through the MCP boundary.

    A tool that raises gives the agent an opaque protocol error instead
    of a usable answer, so every failure is reported as structured data.
    Tools remain responsible for their own expected failure modes; this
    is the backstop for the unexpected ones.

    Args:
        function: Tool function to wrap.

    Returns:
        The wrapped function.
    """

    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception as error:  # noqa: BLE001 - MCP boundary backstop
            # Distinct from a tool's own ``ok: False``, which reports a
            # domain answer such as "this script has errors". A crash
            # must never be mistaken for one.
            return {
                "ok": False,
                "error": "the tool failed unexpectedly",
                "internal_error": describe(error),
            }

    return guarded
