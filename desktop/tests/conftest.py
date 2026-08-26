"""
Shared pytest fixtures for the Monitra desktop test suite.

Tests run headless. Every fixture that touches storage uses a temporary
database so a test can never mutate the developer's real ~/.monitra/cache.db.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# The desktop package is the import root.
DESKTOP_ROOT = Path(__file__).resolve().parent.parent
if str(DESKTOP_ROOT) not in sys.path:
    sys.path.insert(0, str(DESKTOP_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MONITRA_LOG_LEVEL", "WARNING")


@pytest.fixture(scope="session")
def qapp():
    """A single QApplication for the whole session."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def storage(tmp_path):
    """A StorageManager backed by a throwaway database."""
    from storage.manager import StorageManager

    manager = StorageManager(str(tmp_path / "test-cache.db"))
    yield manager
    manager.close()


@pytest.fixture
def cache(storage):
    from sync.local_cache import LocalCache

    return LocalCache(storage=storage)


@pytest.fixture
def runtime(qapp, tmp_path, monkeypatch):
    """
    A fully constructed ApplicationRuntime on a temporary database, with
    services started and torn down around the test.
    """
    from core.runtime import ApplicationRuntime
    from storage.manager import StorageManager

    manager = StorageManager(str(tmp_path / "runtime-cache.db"))
    rt = ApplicationRuntime(storage=manager)
    yield rt
    rt.shutdown(timeout_ms=2000)
