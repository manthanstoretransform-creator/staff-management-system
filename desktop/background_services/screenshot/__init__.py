"""Screenshot capture, local cache and upload queueing."""
from background_services.screenshot.screenshot_service import (
    SCREENSHOT_WINDOW_KEY, ScreenshotService,
)

__all__ = ["ScreenshotService", "SCREENSHOT_WINDOW_KEY"]
