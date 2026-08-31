import re
import sys
import os
from typing import Optional, Tuple
from tracking.browsers.base import BaseBrowserAdapter

class EdgeAdapter(BaseBrowserAdapter):
    browser_name = "Microsoft Edge"

    SUPPORTED_PROCESSES = {
        "msedge", "msedge.exe", "edge", "edge.exe",  # Windows
        "microsoft edge",  # macOS: NSWorkspace's localizedName()
    }

    def is_supported_app(self, app_name: str) -> bool:
        if not app_name:
            return False
        clean_name = os.path.basename(app_name).lower()
        if clean_name.endswith(".exe"):
            clean_name = clean_name[:-4]
        return clean_name in self.SUPPORTED_PROCESSES

    def _parse_window_title(self, window_title: str) -> Tuple[Optional[str], Optional[str]]:
        if not window_title:
            return None, None

        title = window_title.strip()

        suffixes = [" - Microsoft Edge", " - Edge", " and 1 more page - Microsoft Edge", " and 2 more pages - Microsoft Edge"]
        for s in suffixes:
            if title.endswith(s):
                title = title[:-len(s)].strip()
                break

        if not title or title.lower() in ("new tab", "start"):
            return None, None

        url_match = re.search(r'(https?://[^\s]+)', title)
        if url_match:
            return url_match.group(1), title

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
        parsed_url, clean_title = self._parse_window_title(window_title)
        return self.browser_name, parsed_url, clean_title or window_title
