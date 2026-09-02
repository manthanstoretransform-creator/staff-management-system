"""
app.config — where the desktop client learns which backend to talk to.

A packaged build is installed on a staff machine that has no source
checkout, no virtualenv, and no `desktop/.env`. It therefore has to resolve
its configuration from something that survives installation, and it has to
fail *legibly* when that configuration is wrong rather than silently pointing
at a backend that does not exist.

Resolution order (first hit wins, per key):

    1. The process environment — `MONITRA_ENV`, `SMS_API_BASE_URL`. Always
       wins, so an administrator can override a deployed build without
       editing files, and CI can point a smoke test anywhere.
    2. A config file, the first of these that exists:
         a. `.env` beside the executable (frozen) or `desktop/.env` (source).
            This is the per-build override a deployment drops in.
         b. `<data dir>/monitra.env` — the per-user override, which works
            even when the installation directory is read-only (Program Files,
            or inside Monitra.app). See core/paths.py.
    3. The environment preset's default URL (below).

`MONITRA_ENV` selects a preset: development, staging, or production.
Production is the default, because that is what an installed build is: an
unconfigured install on a staff laptop must reach the real backend, not
localhost. Only `development` defaults to localhost, and only ever when
explicitly selected.

There is deliberately no baked-in staging URL. Inventing one would mean
shipping a hostname nobody verified; selecting `staging` without supplying
`SMS_API_BASE_URL` is a configuration error and is reported as one.

**Nothing secret belongs here or in any file this reads.** The desktop client
authenticates as a user, with a token it obtains at login and stores locally.
It has no API key, no signing key, and no database credential — server-side
secrets must never be compiled into a binary that ships to staff machines.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

#: The deployed backend. This is the production default because the desktop
#: client is installed on staff machines, where no local backend exists --
#: defaulting to localhost meant a fresh install could never reach anything
#: and reported itself unreachable with a perfectly good internet connection.
#:
#: Note there is no /api/v1 suffix: backend/app/main.py registers the routers
#: the desktop uses at the bare paths as well as under the prefix, and the
#: desktop calls /auth/me, /projects, /time-entries directly.
LIVE_API_BASE_URL = "https://staffmanagementsystembackend.vercel.app"

DEVELOPMENT = "development"
STAGING = "staging"
PRODUCTION = "production"

#: Default API base URL per environment. `staging` has no default on purpose
#: -- see the module docstring.
ENVIRONMENT_DEFAULTS = {
    DEVELOPMENT: "http://localhost:8000",
    STAGING: "",
    PRODUCTION: LIVE_API_BASE_URL,
}

#: Filename of the per-user config override inside the data directory.
USER_CONFIG_FILENAME = "monitra.env"


def _app_directory() -> Path:
    """
    Return the directory a build-local `.env` would sit in.

    In source checkouts this is `desktop/` (this file's parent.parent). In a
    PyInstaller build, `__file__` points inside the temporary extraction
    directory (`sys._MEIPASS`), so a `.env` placed next to the real
    executable would be silently ignored; `sys.frozen` is PyInstaller's flag
    for "this is a frozen build", and we resolve against the executable then.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


#: The directory a build-local `.env` sits in. Exposed as a module-level
#: name because it is the value the frozen-vs-source resolution test asserts.
desktop_dir = _app_directory()


def _config_file() -> Optional[Path]:
    """Return the config file to load, or None if there is none."""
    candidates = [desktop_dir / ".env"]
    try:
        from core.paths import data_dir

        candidates.append(data_dir() / USER_CONFIG_FILENAME)
    except Exception:  # pragma: no cover - data dir must never block startup
        pass

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


_loaded_from = _config_file()
if _loaded_from is not None:
    # override=False: the real process environment outranks the file, so an
    # administrator's `set SMS_API_BASE_URL=...` beats a stale bundled file.
    load_dotenv(dotenv_path=_loaded_from, override=False)


def _normalise_environment(raw: str) -> str:
    value = (raw or "").strip().lower()
    aliases = {
        "dev": DEVELOPMENT, "develop": DEVELOPMENT, DEVELOPMENT: DEVELOPMENT,
        "stage": STAGING, STAGING: STAGING,
        "prod": PRODUCTION, PRODUCTION: PRODUCTION,
        "": PRODUCTION,
    }
    return aliases.get(value, PRODUCTION)


class Config:
    """
    Resolved desktop configuration.

    `error` is not raised at import time on purpose. An unconfigured build
    must still reach a window that explains the problem; a traceback on a
    staff laptop with no console attached is invisible. main.py reads `error`
    and shows it. See requirement "first-run experience" in BUILD.md.
    """

    def __init__(self) -> None:
        self.ENVIRONMENT: str = _normalise_environment(os.getenv("MONITRA_ENV", ""))
        self.CONFIG_SOURCE: Optional[Path] = _loaded_from

        self.ENVIRONMENT_WAS_EXPLICIT: bool = bool(os.getenv("MONITRA_ENV", "").strip())

        configured = (os.getenv("SMS_API_BASE_URL") or "").strip()
        default = ENVIRONMENT_DEFAULTS[self.ENVIRONMENT]
        self.SMS_API_BASE_URL: str = (configured or default).rstrip("/")

        # A source checkout pointed at a local backend is a development
        # machine, and saying so is more useful than making every developer
        # set MONITRA_ENV as well. This inference is deliberately *not*
        # applied to a frozen build: a shipped package configured for
        # localhost is a broken deployment, and must be reported as one
        # rather than quietly relabelled.
        if (
            not self.ENVIRONMENT_WAS_EXPLICIT
            and not getattr(sys, "frozen", False)
            and configured
            and _is_loopback(self.SMS_API_BASE_URL)
        ):
            self.ENVIRONMENT = DEVELOPMENT

        self.error: Optional[str] = self._validate()

    #: Alias -- `API_BASE_URL` is the name the packaging docs and the build
    #: scripts use. Both names refer to one value; there is no second setting.
    @property
    def API_BASE_URL(self) -> str:
        return self.SMS_API_BASE_URL

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == PRODUCTION

    def _validate(self) -> Optional[str]:
        url = self.SMS_API_BASE_URL
        if not url:
            return (
                f"No backend URL is configured for the '{self.ENVIRONMENT}' "
                f"environment.\n\nSet SMS_API_BASE_URL in the environment, or in "
                f"a '{USER_CONFIG_FILENAME}' file in the Monitra data directory."
            )
        if not url.startswith(("http://", "https://")):
            return (
                f"The configured backend URL is not a valid HTTP(S) address:\n\n"
                f"  {url}\n\nIt must start with http:// or https://."
            )
        if self.is_production and _is_loopback(url):
            return (
                f"This is a production build, but it is configured to use a "
                f"local backend:\n\n  {url}\n\nA local address cannot work on a "
                f"staff machine. Remove the SMS_API_BASE_URL override, or set "
                f"MONITRA_ENV=development if this is a development machine."
            )
        return None

    def describe(self) -> str:
        """One-line summary for the startup log. Contains no secrets."""
        source = str(self.CONFIG_SOURCE) if self.CONFIG_SOURCE else "defaults"
        return f"environment={self.ENVIRONMENT} api={self.SMS_API_BASE_URL} config={source}"


def _is_loopback(url: str) -> bool:
    host = url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0].strip("[]").lower()
    return host in ("localhost", "127.0.0.1", "::1", "0.0.0.0")


settings = Config()
