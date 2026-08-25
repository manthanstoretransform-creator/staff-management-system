import os
from pathlib import Path
from dotenv import load_dotenv

# Locate and load the desktop .env file
# This resolves to c:\staff-management-system\desktop
desktop_dir = Path(__file__).resolve().parent.parent
env_path = desktop_dir / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

class Config:
    """Desktop Configuration Layer."""
    SMS_API_BASE_URL: str = os.getenv("SMS_API_BASE_URL", "http://localhost:8000")

settings = Config()
