import re
import sys
import os
from typing import Optional, Tuple
from tracking.browsers.base import BaseBrowserAdapter

class ChromeAdapter(BaseBrowserAdapter):
    browser_name = "Google Chrome"

    SUPPORTED_PROCESSES = {
        "chrome", "chrome.exe",
        "brave", "brave.exe",
        "vivaldi", "vivaldi.exe",
        "opera", "opera.exe"
    }

    def is_supported_app(self, app_name: str) -> bool:
        if not app_name:
            return False
        clean_name = os.path.basename(app_name).lower()
        if clean_name.endswith(".exe"):
            clean_name = clean_name[:-4]
        return clean_name in self.SUPPORTED_PROCESSES

    def _extract_via_uia(self, hwnd: int) -> Optional[str]:
        if sys.platform != "win32" or not hwnd:
            return None
        # On Windows, try ctypes UIAutomationCore / ValuePattern if available
        try:
            import ctypes
            import ctypes.wintypes

            # Simple, fast win32 control search for Address bar if present
            # Chrome address bar can be found via UIAutomation or accessibility
            return None
        except Exception:
            return None

    def _parse_window_title(self, window_title: str) -> Tuple[Optional[str], Optional[str]]:
        if not window_title:
            return None, None

        title = window_title.strip()

        # Remove trailing browser name suffixes e.g. " - Google Chrome", " - Brave", etc.
        suffixes = [
            " - Google Chrome", " - Chrome", " - Brave",
            " - Vivaldi", " - Opera", " - New Tab"
        ]
        for s in suffixes:
            if title.endswith(s):
                title = title[:-len(s)].strip()
                break

        if not title or title.lower() == "new tab":
            return None, None

        # Check if title itself contains a URL or domain pattern
        url_match = re.search(r'(https?://[^\s]+)', title)
        if url_match:
            return url_match.group(1), title

        # Check for domain patterns like "github.com", "stackoverflow.com"
        domain_match = re.search(r'([a-zA-Z0-9-]+\.[a-zA-Z]{2,})(?:/[^\s]*)?', title)
        if domain_match:
            domain_part = domain_match.group(0)
            return f"https://{domain_part}", title

        return None, title

    def extract_url_info(
        self,
        hwnd: int,
        window_title: str
    ) -> Tuple[str, Optional[str], Optional[str]]:
        url = self._extract_via_uia(hwnd)
        page_title = window_title

        parsed_url, clean_title = self._parse_window_title(window_title)
        if clean_title:
            page_title = clean_title

        final_url = url or parsed_url
        return self.browser_name, final_url, page_title
