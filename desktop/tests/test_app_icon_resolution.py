"""
Coverage for application-logo resolution in the Activity list.

Two things kept real logos off those rows: the manager announced a resolved
icon under its own cache key (the exe path, when there was one) while each
row compared that key against its app *name*, and resolution itself only
consulted a hand-maintained map of a dozen applications. Everything else got
a coloured initials badge.
"""
import os
import sys
from unittest.mock import MagicMock

import pytest

from ui.activity_section import AppRowWidget
from ui.icon_manager import (
    IconManager, _normalize, _registry_app_path, _running_process_path,
    _start_menu_shortcut,
)


def test_cache_key_prefers_the_exe_path(qapp):
    assert IconManager.app_icon_key("Chrome", r"C:\Apps\chrome.exe") == r"c:\apps\chrome.exe"
    assert IconManager.app_icon_key("Chrome") == "chrome"
    assert IconManager.app_icon_key("") == ""


def test_row_matches_the_managers_key_not_its_app_name(qapp):
    """The regression: a row given an exe_path listened for its app name and
    so never applied the icon that arrived."""
    row = AppRowWidget({"name": "sublime_text", "exe_path": r"C:\Apps\sublime_text.exe",
                        "seconds": 60, "percentage": 5})
    assert row._icon_key == r"c:\apps\sublime_text.exe"

    pixmap = MagicMock()
    pixmap.isNull.return_value = False
    applied = []
    row._apply_pixmap = lambda pm: applied.append(pm)

    row._on_app_icon_ready("sublime_text", pixmap)      # the app name: ignored
    assert applied == []
    row._on_app_icon_ready(r"c:\apps\sublime_text.exe", pixmap)
    assert applied == [pixmap]


def test_row_without_an_exe_path_is_keyed_by_name(qapp):
    row = AppRowWidget({"name": "notepad++", "seconds": 60, "percentage": 5})
    assert row._icon_key == "notepad++"


def test_normalize_matches_executable_names_against_display_names():
    assert _normalize("sublime_text") == _normalize("Sublime Text")
    assert _normalize("notepad++") == _normalize("Notepad++")
    assert _normalize("MS-Teams") == _normalize("ms teams")
    assert _normalize("") == ""


def test_resolvers_return_none_for_an_unknown_application():
    """No fabricated fallback: an application that cannot be resolved gets
    no path, and the row keeps its honest initials badge."""
    bogus = "definitely-not-an-installed-app-9f3c"
    assert _running_process_path(bogus) is None
    assert _registry_app_path(bogus) is None
    assert _start_menu_shortcut(bogus) is None


def test_resolvers_tolerate_empty_input():
    assert _running_process_path("") is None
    assert _registry_app_path("") is None
    assert _start_menu_shortcut("") is None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process lookup")
def test_running_process_lookup_finds_this_very_process():
    """python.exe is running right now, by definition -- resolving it proves
    the snapshot walk and the path query both work on this machine."""
    name = os.path.splitext(os.path.basename(sys.executable))[0]
    path = _running_process_path(name)
    assert path is not None
    assert os.path.exists(path)
    assert _normalize(os.path.splitext(os.path.basename(path))[0]) == _normalize(name)
