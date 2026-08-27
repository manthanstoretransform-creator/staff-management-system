"""
icon_manager — Async favicon and application icon loader & cacher.

Provides thread-safe, non-blocking icon resolution for desktop Activity views.
Favicons and app icons are fetched/extracted off the GUI thread and cached in memory.
"""
from __future__ import annotations

import os
import sys
import urllib.request
from typing import Dict, Optional
import concurrent.futures

from PySide6.QtCore import QObject, Signal, QUrl, QFileInfo
from PySide6.QtGui import QPixmap, QImage, QIcon, QDesktopServices
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

        # Common Windows application executable search locations
        self._common_app_paths = {
            "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "microsoft edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "mozilla firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
            "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
            "visual studio code": os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
            "vs code": os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
            "slack": os.path.expandvars(r"%LOCALAPPDATA%\slack\slack.exe"),
            "figma": os.path.expandvars(r"%LOCALAPPDATA%\Figma\Figma.exe"),
            "spotify": os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
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

    def get_app_icon(self, app_name: str) -> Optional[QPixmap]:
        if not app_name:
            return None

        key = app_name.lower().strip()
        if key in self._app_icon_cache:
            return self._app_icon_cache[key]

        # Trigger async extraction
        self._executor.submit(self._extract_app_icon_worker, key, app_name)
        return None

    def _extract_app_icon_worker(self, key: str, app_name: str) -> None:
        exe_path = self._common_app_paths.get(key)
        if not exe_path or not os.path.exists(exe_path):
            # Check if app_name itself is an existing file path
            if os.path.exists(app_name):
                exe_path = app_name

        if exe_path and os.path.exists(exe_path):
            try:
                provider = QFileIconProvider()
                icon = provider.icon(QFileInfo(exe_path))
                if not icon.isNull():
                    pixmap = icon.pixmap(48, 48)
                    if not pixmap.isNull():
                        self._app_icon_cache[key] = pixmap
                        self.app_icon_ready.emit(key, pixmap)
                        return
            except Exception:
                pass

        self._app_icon_cache[key] = None


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
