"""
icon_manager — Async favicon and application icon loader & cacher.

Provides thread-safe, non-blocking icon resolution for desktop Activity views.
Supports Win32 HICON extraction directly from running top-level windows (HWND).
"""
from __future__ import annotations

import os
import sys
import urllib.request
import concurrent.futures
from typing import Dict, Optional

from PySide6.QtCore import QObject, Signal, QUrl, QFileInfo
from PySide6.QtGui import QPixmap, QImage, QDesktopServices
from PySide6.QtWidgets import QFileIconProvider


def _hicon_to_pixmap(hicon: int) -> Optional[QPixmap]:
    """Converts a Windows HICON handle to a PySide6 QPixmap via Win32 GDI."""
    if not hicon or sys.platform != "win32":
        return None
    try:
        import ctypes
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, 32, 32)
        hbmp_old = gdi32.SelectObject(hdc_mem, hbmp)

        # Draw icon onto GDI bitmap
        user32.DrawIconEx(hdc_mem, 0, 0, hicon, 32, 32, 0, 0, 3)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.c_uint32),
                ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16),
                ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32),
                ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32),
                ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32),
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = 32
        bmi.biHeight = -32  # Top-down bitmap
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buf = ctypes.create_string_buffer(32 * 32 * 4)
        gdi32.GetDIBits(hdc_mem, hbmp, 0, 32, buf, ctypes.byref(bmi), 0)

        gdi32.SelectObject(hdc_mem, hbmp_old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)

        img = QImage(buf.raw, 32, 32, QImage.Format.Format_ARGB32)
        if not img.isNull():
            pixmap = QPixmap.fromImage(img)
            if not pixmap.isNull() and pixmap.width() > 1:
                return pixmap
    except Exception:
        pass
    return None


def _get_window_hicon(hwnd: int) -> int:
    """Queries top-level window HWND for WM_GETICON or GCLP_HICON."""
    if not hwnd or sys.platform != "win32":
        return 0
    try:
        import ctypes
        user32 = ctypes.windll.user32
        WM_GETICON = 0x007F
        res = ctypes.c_size_t()

        for icon_type in (1, 2, 0):  # BIG, SMALL2, SMALL
            if user32.SendMessageTimeoutW(hwnd, WM_GETICON, icon_type, 0, 0x0002, 100, ctypes.byref(res)) and res.value:
                return res.value

        hicon = user32.GetClassLongPtrW(hwnd, -14) or user32.GetClassLongPtrW(hwnd, -34)
        if hicon:
            return hicon
    except Exception:
        pass
    return 0


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

            "msedge": "edge",
            "msedge.exe": "edge",
            "microsoft edge": "edge",

            "chrome": "chrome",
            "chrome.exe": "chrome",
            "google chrome": "chrome",

            "firefox": "firefox",
            "firefox.exe": "firefox",
            "mozilla firefox": "firefox",

            "python": "python",
            "python.exe": "python",

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
            "monitra": "monitra",
            "hubstaff": "hubstaff",
            "searchhost": "searchhost",
        }

        # Known installation paths
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
            ],
            "vscode": [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
                r"C:\Program Files\Microsoft VS Code\Code.exe",
            ],
            "notepadplusplus": [
                r"C:\Program Files\Notepad++\notepad++.exe",
            ],
            "snippingtool": [
                r"C:\Windows\System32\SnippingTool.exe",
            ],
            "teams": [
                os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Teams\current\Teams.exe"),
            ],
            "chatgpt": [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\ChatGPT\ChatGPT.exe"),
            ],
        }

    @classmethod
    def instance(cls) -> IconManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Favicon Loader ────────────────────────────────────────────────────────

    def get_favicon(self, domain: str, title: str = "") -> Optional[QPixmap]:
        if not domain or domain == "unknown-domain":
            # Attempt domain extraction from title if unknown
            if title:
                t_lower = title.lower()
                if "edge" in t_lower:
                    domain = "microsoft.com"
                elif "chrome" in t_lower:
                    domain = "google.com"
                elif "firefox" in t_lower:
                    domain = "mozilla.org"

        if not domain or domain == "unknown-domain":
            return None

        clean_dom = domain.lower().strip()
        if clean_dom in self._favicon_cache:
            return self._favicon_cache[clean_dom]

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

    def get_app_icon(self, app_name: str, exe_path: Optional[str] = None, hwnd: Optional[int] = None) -> Optional[QPixmap]:
        if not app_name and not exe_path and not hwnd:
            return None

        cache_key = (exe_path or app_name).lower().strip()
        if cache_key in self._app_icon_cache:
            return self._app_icon_cache[cache_key]

        self._executor.submit(self._extract_app_icon_worker, cache_key, app_name, exe_path, hwnd)
        return None

    def _extract_app_icon_worker(self, cache_key: str, app_name: str, exe_path: Optional[str], hwnd: Optional[int]) -> None:
        norm_name = app_name.lower().strip()
        if norm_name in ("monitra", "python", "python.exe", "main.py"):
            try:
                from background_services.public_api import create_app_icon
                pixmap = create_app_icon().pixmap(48, 48)
                if pixmap and not pixmap.isNull():
                    self._app_icon_cache[cache_key] = pixmap
                    self.app_icon_ready.emit(cache_key, pixmap)
                    return
            except Exception:
                pass

        # 1. Try Win32 HICON from active window handle (HWND)
        if hwnd:
            hicon = _get_window_hicon(hwnd)
            if hicon:
                pix = _hicon_to_pixmap(hicon)
                if pix and not pix.isNull():
                    self._app_icon_cache[cache_key] = pix
                    self.app_icon_ready.emit(cache_key, pix)
                    return

        # 2. Try direct exe_path extraction via QFileIconProvider
        target_path = exe_path if (exe_path and os.path.exists(exe_path)) else None

        # 3. Check known paths via alias map
        if not target_path:
            norm_name = app_name.lower().strip()
            alias = self._app_alias_map.get(norm_name, norm_name)
            candidate_paths = self._common_app_paths.get(alias, [])
            for p in candidate_paths:
                if os.path.exists(p):
                    target_path = p
                    break

        if target_path:
            try:
                icon = self._file_icon_provider.icon(QFileInfo(target_path))
                if not icon.isNull():
                    pixmap = icon.pixmap(48, 48)
                    if not pixmap.isNull() and pixmap.width() > 8:
                        self._app_icon_cache[cache_key] = pixmap
                        self.app_icon_ready.emit(cache_key, pixmap)
                        return
            except Exception:
                pass

        self._app_icon_cache[cache_key] = None


def get_icon_manager() -> IconManager:
    return IconManager.instance()


def safe_open_url(url_str: str) -> bool:
    if not url_str or not isinstance(url_str, str):
        return False

    clean_url = url_str.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = f"https://{clean_url}"

    qurl = QUrl(clean_url)
    if qurl.isValid() and qurl.scheme().lower() in ("http", "https"):
        return QDesktopServices.openUrl(qurl)

    return False
