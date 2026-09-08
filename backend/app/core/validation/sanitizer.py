"""Safe normalisation — the small, meaning-preserving changes we *do* make.

The project's position on cleaning input is deliberate and worth stating
plainly, because the tempting alternative is worse:

**We reject invalid input. We do not strip the dangerous part and continue.**

Silently removing ``<script>`` from a message and storing the remainder changes
what the user said. If someone pastes a bug report containing markup, storing a
quietly-edited version of it is a data-integrity problem dressed up as a
security control. So the functions here only do things that cannot change
meaning: trimming surrounding whitespace, normalising Unicode to a single
canonical spelling, and making line endings consistent.

The one true sanitiser in this module is :func:`escape_like_wildcards`, and it
is not about meaning at all — it is about making a user's ``%`` behave as the
literal percent sign they typed.
"""
from __future__ import annotations

import unicodedata
from typing import Optional


def normalize_unicode(value: str) -> str:
    """Return *value* in Unicode NFC form.

    Composed and decomposed spellings of the same accented character look
    identical on screen but compare unequal and hash differently. Normalising on
    the way in means "José" typed on a Mac and "José" typed on Windows are the
    same project name, and a uniqueness check behaves the way a person expects.

    NFC is the composing form, which is what the web platform and most
    databases already assume.
    """
    return unicodedata.normalize("NFC", value)


def normalize_newlines(value: str) -> str:
    """Collapse CRLF and bare CR line endings to ``\\n``.

    Desktop (Windows) and web clients disagree about line endings, and a stored
    description should not depend on which one submitted it. Character counts
    stay comparable across clients too, which matters because both ends enforce
    the same maximum length.
    """
    return value.replace("\r\n", "\n").replace("\r", "\n")


def strip_control_characters(value: str) -> str:
    """Remove C0 control characters, keeping tab and newline.

    A NUL byte truncates a C string, and terminal control codes can rewrite a
    log line to say something other than what happened. Neither has any place
    in a field a human typed, and removing them cannot change legitimate text.
    """
    return "".join(
        character
        for character in value
        if character in "\t\n" or not _is_stripped_control(character)
    )


def _is_stripped_control(character: str) -> bool:
    codepoint = ord(character)
    return codepoint < 0x20 or codepoint == 0x7F


def normalize_text(value: str, *, allow_newlines: bool = False) -> str:
    """Apply the full safe-normalisation pass used before validating text.

    Order matters. Unicode is composed first, then line endings are converted,
    and only then are control characters removed — a bare carriage return is a
    line ending on the way in and a control character on the way out, so
    stripping first would delete it and silently join two lines into one. The
    outer trim runs last, so a value of nothing but whitespace and control
    codes cannot still look non-empty.

    When *allow_newlines* is false, every remaining newline becomes a space, so
    a single-line field cannot be smuggled a second line.
    """
    text = normalize_unicode(value)
    text = normalize_newlines(text)
    text = strip_control_characters(text)
    if not allow_newlines:
        text = text.replace("\n", " ")
    return text.strip()


def escape_like_wildcards(term: str, *, escape_character: str = "\\") -> str:
    """Escape ``%``, ``_`` and the escape character itself for a SQL ``LIKE``.

    Search terms in this codebase are interpolated into ``ILIKE`` patterns as
    ``f"%{term}%"``. Without this, a user searching for ``100%`` matches every
    row, and ``_`` matches any single character — the term stops meaning what
    was typed. A lone ``%`` submitted deliberately turns a filtered query into
    a full-table scan, so this is a load control as much as a correctness one.

    This is *not* SQL-injection protection: the parameters are already bound by
    SQLAlchemy. It makes the pattern's own metacharacters literal.

    Call it with the matching ``escape=`` on the SQLAlchemy side::

        column.ilike(f"%{escape_like_wildcards(term)}%", escape="\\\\")
    """
    escaped = term.replace(escape_character, escape_character * 2)
    escaped = escaped.replace("%", f"{escape_character}%")
    return escaped.replace("_", f"{escape_character}_")


#: The escape character paired with every ``LIKE``/``ILIKE`` built here. Pass
#: it as ``escape=LIKE_ESCAPE_CHARACTER`` at the query site — an escaped pattern
#: without a declared escape character is worse than no escaping at all,
#: because the backslashes then match literally and the search finds nothing.
LIKE_ESCAPE_CHARACTER = "\\"


def like_pattern(term: str, *, contains: bool = True) -> str:
    """Build a ``LIKE`` pattern from a user's search term, wildcards escaped.

    This is the one function every search in the codebase should use. Written
    by hand, the same expression appears as ``f"%{search.strip()}%"`` in a
    dozen repositories and services, none of which escaped anything — so a user
    searching for ``100%`` matched every row, and ``_`` matched any single
    character.

    Always pair it with the escape character::

        column.ilike(like_pattern(term), escape=LIKE_ESCAPE_CHARACTER)

    Set *contains* to ``False`` for a prefix-anchored match.
    """
    escaped = escape_like_wildcards(term.strip(), escape_character=LIKE_ESCAPE_CHARACTER)
    return f"%{escaped}%" if contains else f"{escaped}%"


def collapse_whitespace(value: str) -> str:
    """Squeeze runs of spaces and tabs into one space, preserving newlines.

    Used for names, where "Acme   Corp" and "Acme Corp" are the same project
    and storing both makes duplicate detection useless.
    """
    lines = normalize_newlines(value).split("\n")
    return "\n".join(" ".join(line.split()) for line in lines)


def normalize_email(value: str) -> str:
    """Trim an address and lower-case its domain.

    The local part is left exactly as typed: RFC 5321 says it is
    case-sensitive, and while nearly every provider treats it case-insensitively
    that is the provider's choice to make, not ours. The domain genuinely is
    case-insensitive, so folding it prevents ``a@Example.com`` and
    ``a@example.com`` registering as two accounts.
    """
    trimmed = normalize_text(value)
    if "@" not in trimmed:
        return trimmed
    local_part, _, domain = trimmed.rpartition("@")
    return f"{local_part}@{domain.lower()}"


def normalize_optional(value: Optional[str], *, allow_newlines: bool = False) -> Optional[str]:
    """Normalise an optional field, mapping a now-empty value to ``None``.

    A form that submits an untouched textbox sends ``""``. Storing that as an
    empty string rather than ``NULL`` means two spellings of "the user did not
    fill this in", and every later query has to test for both.
    """
    if value is None:
        return None
    normalized = normalize_text(value, allow_newlines=allow_newlines)
    return normalized or None


__all__ = [
    "LIKE_ESCAPE_CHARACTER",
    "like_pattern",
    "normalize_unicode",
    "normalize_newlines",
    "strip_control_characters",
    "normalize_text",
    "escape_like_wildcards",
    "collapse_whitespace",
    "normalize_email",
    "normalize_optional",
]
