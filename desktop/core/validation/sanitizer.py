"""Safe normalisation for the desktop client. Mirror of the backend's.

Same position as the backend: we reject invalid input rather than quietly
editing it. The functions here only make changes that cannot alter meaning —
trimming, Unicode composition, line-ending consistency.

Line endings matter more here than on the server. This client runs on Windows,
where a ``QTextEdit`` hands back ``\\r\\n``; the web client sends ``\\n``. If the
desktop counted characters one way and the backend another, a description of
exactly 5000 characters would pass locally and be refused on upload — and it
would be refused *after* the entry was already queued for sync, which is the
worst possible moment to discover it.
"""
from __future__ import annotations

import unicodedata
from typing import Optional


def normalize_unicode(value: str) -> str:
    """Return *value* in Unicode NFC form."""
    return unicodedata.normalize("NFC", value)


def normalize_newlines(value: str) -> str:
    """Collapse CRLF and bare CR line endings to ``\\n``."""
    return value.replace("\r\n", "\n").replace("\r", "\n")


def strip_control_characters(value: str) -> str:
    """Remove C0 control characters, keeping tab and newline."""
    return "".join(
        character
        for character in value
        if character in "\t\n" or not _is_stripped_control(character)
    )


def _is_stripped_control(character: str) -> bool:
    codepoint = ord(character)
    return codepoint < 0x20 or codepoint == 0x7F


def normalize_text(value: str, *, allow_newlines: bool = False) -> str:
    """The full safe-normalisation pass applied before validating text.

    Order matters. Line endings are converted *before* control characters are
    removed, because a bare carriage return is a line ending on the way in and
    a control character on the way out — stripping first would delete it and
    silently join two lines into one.
    """
    text = normalize_unicode(value)
    text = normalize_newlines(text)
    text = strip_control_characters(text)
    if not allow_newlines:
        text = text.replace("\n", " ")
    return text.strip()


def collapse_whitespace(value: str) -> str:
    """Squeeze runs of spaces and tabs into one space, preserving newlines."""
    lines = normalize_newlines(value).split("\n")
    return "\n".join(" ".join(line.split()) for line in lines)


def normalize_email(value: str) -> str:
    """Trim an address and lower-case its domain, never its local part."""
    trimmed = normalize_text(value)
    if "@" not in trimmed:
        return trimmed
    local_part, _, domain = trimmed.rpartition("@")
    return f"{local_part}@{domain.lower()}"


def normalize_optional(value: Optional[str], *, allow_newlines: bool = False) -> Optional[str]:
    """Normalise an optional field, mapping a now-empty value to ``None``."""
    if value is None:
        return None
    normalized = normalize_text(value, allow_newlines=allow_newlines)
    return normalized or None


__all__ = [
    "normalize_unicode",
    "normalize_newlines",
    "strip_control_characters",
    "normalize_text",
    "collapse_whitespace",
    "normalize_email",
    "normalize_optional",
]
