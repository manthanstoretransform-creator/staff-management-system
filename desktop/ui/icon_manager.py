"""
icon_manager — Async favicon and application icon loader & cacher.

Provides thread-safe, non-blocking icon resolution for desktop Activity views.
Favicons and app icons are fetched/extracted off the GUI thread and cached in memory.
"""
from __future__ import annotations

import os
import sys
import urllib.request
import concurrent.futures
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QObject, Signal, QUrl, QFileInfo
from PySide6.QtGui import QPixmap, QImage, QIcon, QDesktopServices, QPainter, QColor, QFont
from PySide6.QtWidgets import QFileIconProvider


class IconManager(QObject):
    """Singleton icon manager for loading and caching website favicons and application icons."""

    favicon_ready = Signal(str, QPixmap)  # domain, pixmap
    app_icon_ready = Signal(str, QPixmap)  # app_name, pixmap

    _instance: Optional[IconManager] = None

    def __init__(self) -> None:
        super().__init__()
        self._favicon_cache: Dict[str, Optional[QPixmap]] = {}
        self._app_icon_cache: Dict[str, Optional[QPixmap]] = {}
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self._file_icon_provider = QFileIconProvider()

        # Known application alias map
        self._app_alias_map = {
            "code": "vscode",
            "code.exe": "vscode",
            "visual studio code": "vscode",
            "vscode": "vscode",

            "msedge": "edge",
            "msedge.exe": "edge",
            "microsoft edge": "edge",
            "edge": "edge",

            "chrome": "chrome",
            "chrome.exe": "chrome",
            "google chrome": "chrome",

            "firefox": "firefox",
            "firefox.exe": "firefox",
            "mozilla firefox": "firefox",

            "python": "python",
            "python.exe": "python",
            "pythonw.exe": "python",

            "notepad++": "notepadplusplus",
            "notepad++.exe": "notepadplusplus",

            "snippingtool": "snippingtool",
            "snippingtool.exe": "snippingtool",
            "snipping tool": "snippingtool",

            "teams": "teams",
            "teams.exe": "teams",
            "ms-teams": "teams",
            "microsoft teams": "teams",

            "chatgpt": "chatgpt",
            "chatgpt.exe": "chatgpt",

            "antigravity": "antigravity",
            "postman": "postman",
            "slack": "slack",
            "figma": "figma",
            "spotify": "spotify",
        }

        # Known installation path hints on Windows
        self._common_app_paths = {
            "chrome": [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ],
            "edge": [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ],
            "firefox": [
                r"C:\Program Files\Mozilla Firefox\firefox.exe",
                r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            ],
            "vscode": [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
                r"C:\Program Files\Microsoft VS Code\Code.exe",
            ],
            "python": [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312\python.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311\python.exe"),
                r"C:\Python312\python.exe",
                r"C:\Python311\python.exe",
            ],
            "notepadplusplus": [
                r"C:\Program Files\Notepad++\notepad++.exe",
                r"C:\Program Files (x86)\Notepad++\notepad++.exe",
            ],
            "snippingtool": [
                r"C:\Windows\System32\SnippingTool.exe",
                r"C:\Windows\System32\SnippingTool.exe",
            ],
            "teams": [
                os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Teams\current\Teams.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\ms-teams.exe"),
            ],
            "chatgpt": [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\ChatGPT\ChatGPT.exe"),
            ],
            "slack": [
                os.path.expandvars(r"%LOCALAPPDATA%\slack\slack.exe"),
            ],
            "figma": [
                os.path.expandvars(r"%LOCALAPPDATA%\Figma\Figma.exe"),
            ],
            "spotify": [
                os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
            ],
        }

    @classmethod
    def instance(cls) -> IconManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Favicon Loader ────────────────────────────────────────────────────────

    def get_favicon(self, domain: str) -> Optional[QPixmap]:
        if not domain or domain == "unknown-domain":
            return None

        clean_dom = domain.lower().strip()
        if clean_dom in self._favicon_cache:
            return self._favicon_cache[clean_dom]

        # Trigger async download
        self._executor.submit(self._fetch_favicon_worker, clean_dom)
        return None

    def _fetch_favicon_worker(self, domain: str) -> None:
        url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                data = resp.read()
                if data:
                    image = QImage()
                    if image.loadFromData(data):
                        pixmap = QPixmap.fromImage(image)
                        if not pixmap.isNull() and pixmap.width() > 1 and pixmap.height() > 1:
                            self._favicon_cache[domain] = pixmap
                            self.favicon_ready.emit(domain, pixmap)
                            return
        except Exception:
            pass

        self._favicon_cache[domain] = None

    # ── App Icon Loader ───────────────────────────────────────────────────────

    def get_app_icon(self, app_name: str, exe_path: Optional[str] = None) -> Optional[QPixmap]:
        if not app_name and not exe_path:
            return None

        cache_key = (exe_path or app_name).lower().strip()
        if cache_key in self._app_icon_cache:
            return self._app_icon_cache[cache_key]

        # Trigger async extraction
        self._executor.submit(self._extract_app_icon_worker, cache_key, app_name, exe_path)
        return None

    def _extract_app_icon_worker(self, cache_key: str, app_name: str, exe_path: Optional[str]) -> None:
        # Priority 1: Use provided exe_path if valid
        target_path = exe_path if (exe_path and os.path.exists(exe_path)) else None

        # Priority 2: Use common installation paths via alias map
        if not target_path:
            norm_name = app_name.lower().strip()
            alias = self._app_alias_map.get(norm_name, norm_name)
            candidate_paths = self._common_app_paths.get(alias, [])
            for p in candidate_paths:
                if os.path.exists(p):
                    target_path = p
                    break

        # Priority 3: Check if app_name itself is an existing file path
        if not target_path and os.path.exists(app_name):
            target_path = app_name

        # Priority 4: Try system path lookup via shutil.which
        if not target_path:
            import shutil
            which_path = shutil.which(app_name) or shutil.which(f"{app_name}.exe")
            if which_path and os.path.exists(which_path):
                target_path = which_path

        # Extract icon if valid target_path found
        if target_path:
            try:
                icon = self._file_icon_provider.icon(QFileInfo(target_path))
                if not icon.isNull():
                    pixmap = icon.pixmap(48, 48)
                    if not pixmap.isNull() and pixmap.width() > 8 and pixmap.height() > 8:
                        self._app_icon_cache[cache_key] = pixmap
                        self.app_icon_ready.emit(cache_key, pixmap)
                        return
            except Exception:
                pass

        self._app_icon_cache[cache_key] = None


def get_icon_manager() -> IconManager:
    return IconManager.instance()


def safe_open_url(url_str: str) -> bool:
    """
    Safely opens an HTTP/HTTPS URL in the default browser.
    Validates scheme to prevent arbitrary URI execution.
    """
    if not url_str or not isinstance(url_str, str):
        return False

    clean_url = url_str.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = f"https://{clean_url}"

    qurl = QUrl(clean_url)
    if qurl.isValid() and qurl.scheme().lower() in ("http", "https"):
        return QDesktopServices.openUrl(qurl)

    return False
