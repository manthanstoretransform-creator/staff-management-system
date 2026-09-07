"""
screenshot.store — The private daily cache holding screenshots before upload.

Files live under the Monitra data directory resolved by `core.paths.data_dir()`
— never in Desktop, Documents or Downloads, and never at a hardcoded OS path.
`core.paths` is the single place in this application that answers "where may we
write", so the screenshot cache, the SQLite database and the logs cannot
disagree about it, and a packaged build never tries to write inside its own
read-only installation directory.

    <data dir>/screenshot-cache/
        2026-09-07/
            ss_<client_screenshot_id>.webp

The day folder is created on demand, so crossing midnight while tracking
starts writing into the new day's folder with no restart and no timer.

This location is not a security boundary and is not treated as one: the
directory is readable by the account that runs Monitra, exactly as the local
SQLite database is. Its purpose is durable temporary storage between capture
and a confirmed upload, which is what makes an offline capture survive.
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from background_services.screenshot import config
from core.logging_setup import get_logger
from core.paths import data_dir

log = get_logger("screenshot.store")


def root_dir() -> Path:
    """The screenshot cache root, created if missing."""
    path = data_dir() / config.CACHE_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def day_folder_name(when: Optional[datetime] = None) -> str:
    """`YYYY-MM-DD` for the local calendar day of `when` (default: now)."""
    return (when or datetime.now()).strftime("%Y-%m-%d")


def day_dir(when: Optional[datetime] = None) -> Path:
    """Today's folder, created if missing."""
    path = root_dir() / day_folder_name(when)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_screenshot(client_screenshot_id: str, data: bytes,
                     when: Optional[datetime] = None) -> Optional[Path]:
    """
    Write one screenshot to today's folder.

    Written to a temporary name and then renamed, so a crash mid-write cannot
    leave a truncated `.webp` that the uploader would later send as a valid
    image. The rename is atomic on both supported platforms.

    :return: the final path, or None if it could not be written.
    """
    target = day_dir(when) / f"ss_{client_screenshot_id}.webp"
    temp = target.with_suffix(".webp.part")
    try:
        with open(temp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    except OSError:
        log.exception("could not write screenshot to %s", target)
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        return None
    return target


def delete_screenshot(path: str) -> bool:
    """Remove one uploaded screenshot. Missing is success — the goal is absence."""
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        log.warning("could not delete uploaded screenshot %s", path, exc_info=True)
        return False
    return True


def prune_orphans(known_paths: Iterable[str], min_age_seconds: float = 3600.0) -> int:
    """
    Delete cached images that no queue row references.

    A file can outlive its row: a process killed between the write and the
    insert, a queue cleared at logout while the disk still held the images, or
    a run whose database was elsewhere. Nothing else would ever reclaim those
    — `prune_empty_day_folders` only removes folders that are already empty —
    so without this the cache grows forever on a long-lived install.

    Two guards keep this from deleting live work:

    * only files absent from `known_paths` are considered, and the caller
      passes the whole queue including failed rows;
    * only files older than `min_age_seconds` are removed, so a capture written
      moments ago whose row is still being inserted is never eligible.

    :return: how many files were removed.
    """
    known = {str(Path(p).resolve()) for p in known_paths}
    cutoff = time.time() - min_age_seconds
    removed = 0
    try:
        day_folders = [p for p in root_dir().iterdir() if p.is_dir()]
    except OSError:
        log.warning("could not list the screenshot cache", exc_info=True)
        return 0

    for folder in day_folders:
        try:
            entries = list(folder.iterdir())
        except OSError:
            continue
        for path in entries:
            if not path.is_file():
                continue
            if str(path.resolve()) in known:
                continue
            try:
                if path.stat().st_mtime > cutoff:
                    continue
                path.unlink()
            except OSError:
                continue
            removed += 1
    if removed:
        log.info("removed %d orphaned screenshot file(s) from the cache", removed)
    return removed


def prune_empty_day_folders(protected: Iterable[str] = ()) -> int:
    """
    Remove day folders that hold no files.

    A folder is only removed once every screenshot in it has been uploaded and
    deleted, which is what makes this safe: the caller passes the paths still
    referenced by the upload queue as `protected`, so a folder containing a
    pending, uploading or retrying screenshot is never touched even if a stray
    file was removed by hand.

    :return: how many folders were removed.
    """
    protected_dirs = {str(Path(p).parent) for p in protected}
    removed = 0
    try:
        candidates = sorted(root_dir().iterdir())
    except OSError:
        log.warning("could not list the screenshot cache", exc_info=True)
        return 0

    for folder in candidates:
        if not folder.is_dir() or str(folder) in protected_dirs:
            continue
        try:
            if any(folder.iterdir()):
                continue
            folder.rmdir()
        except OSError:
            continue
        removed += 1
    if removed:
        log.info("removed %d fully-synced screenshot day folder(s)", removed)
    return removed
