from abc import ABC, abstractmethod
from typing import Optional, Tuple

class BaseBrowserAdapter(ABC):
    """
    Abstract base class for browser URL and title extraction adapters.
    """

    browser_name: str = "Generic Browser"

    @abstractmethod
    def is_supported_app(self, app_name: str) -> bool:
        """Return True if this adapter handles the given process name."""
        pass

    @abstractmethod
    def extract_url_info(
        self,
        hwnd: int,
        window_title: str
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Extract (browser_name, url_or_domain, page_title) from an active window handle or title.
        """
        pass
