"""
The single-instance guard, on both platforms.

Two Monitra processes at once is the packaged-build form of the duplicate
background implementation DO_NOT_DO.md records: two timers deriving elapsed
time, two sync services draining the same durable queue, two activity trackers
writing overlapping windows, and two writers on one SQLite database.

Windows holds a named mutex; macOS and Linux hold an `flock()` on a file in
the data directory. The Windows side is already covered by
`test_packaging.py` (the installer's `CheckForMutexes` name must match the
one the app takes). This file covers the POSIX side — the macOS guard — which
had no test of its own.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import single_instance


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Point the data directory at a throwaway path for the lock file."""
    from core import paths

    monkeypatch.setenv("MONITRA_DATA_DIR", str(tmp_path))
    paths.reset_cache()
    yield tmp_path
    paths.reset_cache()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX flock path")
def test_a_second_instance_is_refused_on_posix(data_dir):
    first = single_instance._acquire_posix()
    assert first is not None, "the first instance must get the lock"
    try:
        # The second copy — a user double-clicking the .app while it is
        # already running in the menu bar — must not start tracking.
        assert single_instance._acquire_posix() is None
    finally:
        first.close()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX flock path")
def test_the_lock_is_released_when_the_holder_exits(data_dir):
    # flock is released by the OS when the file handle goes, including on a
    # crash or a kill. That is why there is no stale-lock cleanup to get
    # wrong: a leftover lock *file* is harmless, because the lock itself is
    # what is tested, not the file's existence.
    first = single_instance._acquire_posix()
    assert first is not None
    first.close()

    second = single_instance._acquire_posix()
    assert second is not None
    second.close()


def test_macos_uses_the_posix_lock(monkeypatch):
    """`acquire()` must route macOS to the flock path, not skip the guard."""
    called = {}

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(
        single_instance, "_acquire_posix",
        lambda: called.setdefault("posix", True) and "handle",
    )
    monkeypatch.setattr(
        single_instance, "_acquire_windows",
        lambda: pytest.fail("macOS must not take the Windows mutex path"),
    )

    assert single_instance.acquire() is True
    assert called.get("posix") is True


def test_a_lock_that_cannot_be_evaluated_still_lets_the_app_start(monkeypatch):
    # Refusing to launch because the *lock* failed would be a worse failure
    # than the duplicate it guards against.
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(
        single_instance, "_acquire_posix",
        lambda: (_ for _ in ()).throw(OSError("read-only data directory")),
    )

    assert single_instance.acquire() is True


if __name__ == "__main__":
    pytest.main([__file__])
