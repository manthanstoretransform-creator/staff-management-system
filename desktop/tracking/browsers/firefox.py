from tracking.browsers.base import BaseBrowserAdapter


class FirefoxAdapter(BaseBrowserAdapter):
    """Firefox.

    Gecko only exposes its URL bar to UI Automation when accessibility
    services are active, so the address-bar read genuinely does fail on some
    installations. That case is reported as `UrlSource.UNAVAILABLE` and the
    browser's own usage is still recorded -- it is never papered over with a
    guessed URL.
    """

    browser_name = "Mozilla Firefox"

    SUPPORTED_PROCESSES = frozenset({"firefox", "firefox.exe"})

    TITLE_SUFFIXES = (" — Mozilla Firefox", " - Mozilla Firefox", " - Firefox")

    EMPTY_TITLES = frozenset({"new tab", "mozilla firefox"})
