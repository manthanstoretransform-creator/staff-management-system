import re
from typing import List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

from tracking.browsers.base import BaseBrowserAdapter
from tracking.browsers.chrome import ChromeAdapter
from tracking.browsers.edge import EdgeAdapter
from tracking.browsers.firefox import FirefoxAdapter

KNOWN_SITE_DOMAINS = {
    "github": "github.com",
    "stackoverflow": "stackoverflow.com",
    "stack overflow": "stackoverflow.com",
    "google": "google.com",
    "youtube": "youtube.com",
    "figma": "figma.com",
    "gitlab": "gitlab.com",
    "linear": "linear.app",
    "notion": "notion.so",
    "jira": "atlassian.net",
    "confluence": "atlassian.net",
    "slack": "slack.com",
    "reddit": "reddit.com",
    "twitter": "twitter.com",
    "x": "x.com",
    "linkedin": "linkedin.com",
}

def normalize_domain_and_url(url_str: Optional[str], window_title: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """
    Extracts lowercased domain and normalized URL from URL string or window title.
    """
    if url_str and url_str.strip():
        clean_url = url_str.strip()
        try:
            parsed = urlparse(clean_url)
            if not parsed.scheme or not parsed.netloc:
                parsed = urlparse(f"https://{clean_url}")
            
            domain = parsed.hostname.lower() if parsed.hostname else ""
            path = parsed.path
            if len(path) > 1 and path.endswith('/'):
                path = path.rstrip('/')

            norm_url = urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            if domain:
                return domain, norm_url
        except Exception:
            pass

    # Fallback to domain extraction from title if URL parsing produced no domain
    if window_title:
        title = window_title.strip().lower()
        # Look for explicit domain patterns in title e.g. "docs.python.org"
        domain_match = re.search(r'([a-zA-Z0-9-]+\.(?:com|org|net|io|dev|edu|gov|co|in|app|ai|info|me|ca|uk|us|de|fr))[^\w]*', title)
        if domain_match:
            dom = domain_match.group(1).lower()
            return dom, f"https://{dom}"

        # Look for known site keywords in title e.g. "GitHub" -> "github.com"
        for kw, dom in KNOWN_SITE_DOMAINS.items():
            if kw in title:
                return dom, f"https://{dom}"

    # Default fallback
    return "unknown-domain", url_str


class BrowserManager:
    """Coordinates browser detection and URL extraction across registered adapters."""

    def __init__(self, adapters: Optional[List[BaseBrowserAdapter]] = None) -> None:
        self.adapters: List[BaseBrowserAdapter] = adapters or [
            ChromeAdapter(),
            EdgeAdapter(),
            FirefoxAdapter(),
        ]

    def get_adapter(self, app_name: str) -> Optional[BaseBrowserAdapter]:
        if not app_name:
            return None
        for adapter in self.adapters:
            if adapter.is_supported_app(app_name):
                return adapter
        return None

    def is_browser_app(self, app_name: str) -> bool:
        return self.get_adapter(app_name) is not None

    def extract_browser_info(
        self,
        app_name: str,
        window_title: str,
        hwnd: int = 0
    ) -> Optional[Tuple[str, str, Optional[str], Optional[str]]]:
        """
        Extracts browser usage info if app_name is a supported browser.
        Returns Tuple: (browser_name, domain, url, page_title) or None if app is not a browser.
        """
        adapter = self.get_adapter(app_name)
        if not adapter:
            return None

        browser_name, raw_url, page_title = adapter.extract_url_info(hwnd, window_title)
        domain, normalized_url = normalize_domain_and_url(raw_url, page_title or window_title)

        return browser_name, domain, normalized_url, page_title or window_title


_instance: Optional[BrowserManager] = None

def get_browser_manager() -> BrowserManager:
    global _instance
    if _instance is None:
        _instance = BrowserManager()
    return _instance
