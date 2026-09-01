import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Locate and load the desktop .env file.
#
# In source checkouts this resolves next to main.py (__file__'s parent.parent).
# In a PyInstaller build, __file__ instead points inside the temporary
# extraction directory (sys._MEIPASS), so a .env placed next to the real
# .exe would be silently ignored. sys.frozen is PyInstaller's own flag for
# "this is a frozen build"; when set, look next to the executable instead.
if getattr(sys, "frozen", False):
    desktop_dir = Path(sys.executable).resolve().parent
else:
    desktop_dir = Path(__file__).resolve().parent.parent
env_path = desktop_dir / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

#: The deployed backend. This is the default because the desktop client is
#: installed on staff machines, where no local backend exists -- defaulting to
#: localhost meant a fresh install could never reach anything and reported
#: itself unreachable with a perfectly good internet connection.
#:
#: Note there is no /api/v1 suffix: backend/app/main.py registers the routers
#: the desktop uses at the bare paths as well as under the prefix, and the
#: desktop calls /auth/me, /projects, /time-entries directly.
LIVE_API_BASE_URL = "https://staffmanagementsystembackend.vercel.app"


class Config:
    """Desktop Configuration Layer."""

    #: Override with SMS_API_BASE_URL in desktop/.env to point at a local
    #: backend during development, e.g. http://localhost:8000
    SMS_API_BASE_URL: str = os.getenv("SMS_API_BASE_URL", LIVE_API_BASE_URL)

settings = Config()
