"""
Coverage for app/config.py's .env resolution across a normal source
checkout and a PyInstaller-frozen build.

__file__ inside a frozen build points into the temporary extraction
directory (sys._MEIPASS), not next to the real .exe -- so a .env placed
beside the executable would silently be ignored unless config.py checks
sys.frozen and resolves relative to sys.executable instead.
"""
import importlib
import sys

import app.config as config_module


def _reload_config():
    return importlib.reload(config_module)


def test_desktop_dir_resolves_next_to_main_py_when_not_frozen():
    assert not getattr(sys, "frozen", False)
    reloaded = _reload_config()
    # main.py lives directly in desktop/, one level up from app/config.py.
    assert (reloaded.desktop_dir / "main.py").exists()


def test_desktop_dir_resolves_next_to_the_exe_when_frozen(monkeypatch, tmp_path):
    fake_exe = tmp_path / "Monitra.exe"
    fake_exe.touch()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    try:
        reloaded = _reload_config()
        assert reloaded.desktop_dir == tmp_path
    finally:
        monkeypatch.delattr(sys, "frozen", raising=False)
        _reload_config()  # restore the un-frozen module state for later tests
