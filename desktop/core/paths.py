"""
core.paths — where the application reads resources from and writes data to.

Two questions have to be answered differently in a source checkout and in a
packaged build, and getting either wrong is a class of bug that only ever
shows up *after* packaging:

1. **Where are read-only resources?** Under PyInstaller, `__file__` points
   inside a temporary extraction directory (`sys._MEIPASS`), not at the
   source tree. `resource_path()` resolves both cases.

2. **Where may we write?** An installed build lives in
   `C:\\Program Files\\Monitra` or inside `Monitra.app`, both of which are
   read-only for a standard user and both of which are *replaced wholesale*
   by the next installer run. Runtime data written there is either refused
   or silently destroyed on update. `data_dir()` always resolves to a
   user-owned location outside the installation.

This module is the only place either question is answered. `storage.manager`
(SQLite) and `core.logging_setup` (log files) both defer to it, so the
database and the logs can never disagree about where "the Monitra data
directory" is.

Resolution order for the data directory:

    1. ``MONITRA_DATA_DIR``            — explicit override; used by tests and
                                         by administrators relocating data.
    2. portable mode                   — a frozen build with a `monitra.portable`
                                         marker file beside the executable keeps
                                         its data in `<exe dir>/data`, so the
                                         whole thing travels on a USB stick.
    3. ``~/.monitra``                  — the default, on both Windows and macOS.

The result is resolved once per process and cached. Re-reading the
environment on every call would let a mid-run change split the SQLite
database and the sync queue across two directories.

`~/.monitra` (rather than `%LOCALAPPDATA%` / `~/Library/Application Support`)
is deliberate: it is the location this application has always used, existing
installs already have a `cache.db` and a populated sync queue there, and it
is user-owned and update-safe on both supported platforms. Moving it would
require a migration whose only benefit is convention.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

#: Marker file the portable build drops beside the executable. Its presence
#: is what makes a build portable; the file's contents are ignored.
PORTABLE_MARKER = "monitra.portable"

_data_dir: Optional[Path] = None


def is_frozen() -> bool:
    """True when running from a PyInstaller build rather than from source."""
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """
    Return the directory the application was launched from.

    Frozen: the directory containing the executable — on macOS that is
    `Monitra.app/Contents/MacOS`. From source: the `desktop/` directory.
    This is a *read-only* location in an installed build; never write here.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """
    Resolve a bundled read-only resource shipped with the application.

    Use this for anything loaded from disk at runtime. Never build such a
    path with `Path(__file__).parent / ".." / "assets"`: that resolves into
    the source tree, which does not exist in a packaged build.
    """
    base = Path(getattr(sys, "_MEIPASS", "")) if is_frozen() else None
    if not base:
        base = Path(__file__).resolve().parent.parent
    return base.joinpath(*parts)


def is_portable() -> bool:
    """True when this build is a portable one (marker file beside the exe)."""
    return is_frozen() and (app_dir() / PORTABLE_MARKER).exists()


def _candidate_data_dir() -> Path:
    override = os.getenv("MONITRA_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if is_portable():
        return app_dir() / "data"
    return Path.home() / ".monitra"


def data_dir() -> Path:
    """
    Return the writable Monitra data directory, creating it if needed.

    Falls back to `~/.monitra` if the preferred location cannot be created —
    a portable build extracted into a read-only directory must still start,
    with data in the user's home, rather than fail at import time.
    """
    global _data_dir
    if _data_dir is not None:
        return _data_dir

    candidate = _candidate_data_dir()
    try:
        candidate.mkdir(parents=True, exist_ok=True)
    except OSError:
        candidate = Path.home() / ".monitra"
        candidate.mkdir(parents=True, exist_ok=True)

    _data_dir = candidate
    return _data_dir


def logs_dir() -> Path:
    """Return the log directory, creating it if needed."""
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def reset_cache() -> None:
    """
    Forget the resolved data directory.

    Only for tests, which need to point `MONITRA_DATA_DIR` at a fresh tmpdir
    between cases. Production code must never call this: relocating the data
    directory mid-run would strand the open SQLite connections.
    """
    global _data_dir
    _data_dir = None
