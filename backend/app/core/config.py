import os
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    DATABASE_URL_DEV: str = ""
    DATABASE_URL: str = ""
    EXTERNAL_AUTH_BASE_URL: str = "https://nothing.peakworkos.com"
    EXTERNAL_AUTH_LOGIN_PATH: str = "/wp-json/st-performance/v1/auth/hubstaff/login"
    # Single sign-on: the provider signs its own JWT for the browser handoff, so the
    # backend verifies that token with the provider and reads the identity behind it
    # instead of trusting anything the URL carries.
    EXTERNAL_AUTH_TOKEN_VALIDATE_PATH: str = "/wp-json/jwt-auth/v1/token/validate"
    EXTERNAL_AUTH_PROFILE_PATH: str = "/wp-json/st-performance/v1/user/profile"
    EXTERNAL_AUTH_CONNECT_TIMEOUT: float = 10.0
    EXTERNAL_AUTH_READ_TIMEOUT: float = 20.0

    # Some upstream WAFs reject Python's default HTTP user agent even when the
    # credentials and JSON payload are valid. Keep this configurable so the
    # integration can use the same API-client identity as the verified request.
    WORDPRESS_LOGIN_USER_AGENT: str = "PostmanRuntime/7.56.1"
    DEFAULT_ORGANIZATION_ID: int = 1

    @property
    def WORDPRESS_LOGIN_URL(self) -> str:
        return f"{self.EXTERNAL_AUTH_BASE_URL.rstrip('/')}/{self.EXTERNAL_AUTH_LOGIN_PATH.lstrip('/')}"

    @property
    def WORDPRESS_TOKEN_VALIDATE_URL(self) -> str:
        return f"{self.EXTERNAL_AUTH_BASE_URL.rstrip('/')}/{self.EXTERNAL_AUTH_TOKEN_VALIDATE_PATH.lstrip('/')}"

    @property
    def WORDPRESS_PROFILE_URL(self) -> str:
        return f"{self.EXTERNAL_AUTH_BASE_URL.rstrip('/')}/{self.EXTERNAL_AUTH_PROFILE_PATH.lstrip('/')}"

    # ── Desktop releases ──────────────────────────────────────────────────
    # What the desktop client's update check is told. Set by the release
    # process only once a draft GitHub release has actually been published --
    # never from a git tag, because a tag exists before anyone has decided the
    # build is good. Clearing DESKTOP_LATEST_VERSION is how a bad release is
    # withdrawn: the in-app prompt stops recommending it immediately.
    #
    # Left empty, the endpoint answers an honest "unknown" and no user is
    # prompted. Never populate these with a placeholder.
    DESKTOP_LATEST_VERSION: str = ""
    DESKTOP_DOWNLOAD_URL: str = ""
    DESKTOP_RELEASE_NOTES_URL: str = ""

    ENV: str = os.getenv("ENV", "development")

    # JWT_SECRET_KEY must be set in .env for production; development has a default
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "super-secret-key-change-me-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30    
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "..", "..", ".env"), 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Validate required environment variables for production
        if self.ENV == "production":
            if not self.DATABASE_URL:
                logger.error("ERROR: DATABASE_URL is not set in production environment!")
            if self.JWT_SECRET_KEY == "super-secret-key-change-me-in-production":
                logger.warning("WARNING: Using default JWT_SECRET_KEY in production! Set JWT_SECRET_KEY in environment variables.")

        logger.info(f"Settings initialized. Environment: {self.ENV}")

# Create settings instance
try:
    settings = Settings()
except Exception as e:
    logger.error(f"Failed to initialize settings: {str(e)}")
    # Create a fallback settings object
    settings = Settings(DATABASE_URL_DEV="", DATABASE_URL="", ENV="development")

