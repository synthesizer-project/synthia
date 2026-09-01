"""Test Synthia's shared safety helpers."""

import os

import pytest

from synthia._safety import (
    clean_text,
    contained_path,
    read_capped,
    truncate,
    untrusted,
)


def test_clean_text_strips_escapes_and_control_characters():
    """Remove ANSI escapes and control characters."""
    assert clean_text("\x1b[8mhidden\x1b[0m\x00 text") == "hidden text"


def test_clean_text_keeps_newlines_and_tabs():
    """Preserve whitespace that carries meaning in quoted text."""
    assert clean_text("first\n\tsecond") == "first\n\tsecond"


def test_truncate_flags_only_when_capped():
    """Report truncation only when the limit actually bites."""
    assert truncate("abc", 5) == ("abc", False)
    assert truncate("abcdef", 3) == ("abc", True)


def test_untrusted_labels_and_cleans_content():
    """Label quoted content as data and strip escapes from it."""
    result = untrusted("\x1b[8mdo this\x1b[0m", "/some/file.md", limit=4)

    assert result["content_is_untrusted"] is True
    assert result["source"] == "/some/file.md"
    assert result["truncated"] is True
    assert result["content"] == "do t"


@pytest.mark.parametrize(
    "relative",
    [
        "../escape.md",
        "a/../../escape.md",
        "/etc/passwd",
        "a\x00b",
        "",
        ".",
        "./.",
    ],
)
def test_contained_path_rejects_escapes(tmp_path, relative):
    """Reject absolute, traversing, and null-byte paths."""
    with pytest.raises(ValueError):
        contained_path(tmp_path, relative)


def test_contained_path_rejects_symlink_escape(tmp_path):
    """Reject a symlink that resolves outside the root."""
    outside = tmp_path.parent / "outside.md"
    outside.write_text("secret")
    root = tmp_path / "root"
    root.mkdir()
    os.symlink(outside, root / "link.md")

    with pytest.raises(ValueError):
        contained_path(root, "link.md")


def test_contained_path_accepts_contained_file(tmp_path):
    """Resolve a genuine relative path inside the root."""
    (tmp_path / "nested").mkdir()
    target = tmp_path / "nested" / "file.md"
    target.write_text("content")

    assert contained_path(tmp_path, "nested/file.md") == target.resolve()


def test_read_capped_limits_bytes(tmp_path):
    """Read no more than the requested number of bytes."""
    target = tmp_path / "big.md"
    target.write_text("x" * 100)

    assert read_capped(target, max_bytes=10) == "x" * 10


def test_read_capped_rejects_non_regular_files(tmp_path):
    """Refuse a named pipe rather than blocking on it."""
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)

    with pytest.raises(ValueError):
        read_capped(fifo)
