import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL_DEV: str
    DATABASE_URL: str
    EXTERNAL_AUTH_BASE_URL: str = "https://dev-st-performance.pantheonsite.io"
    EXTERNAL_AUTH_LOGIN_PATH: str = "/wp-json/st-performance/v1/auth/hubstaff/login"
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

    ENV: str = "development"

    JWT_SECRET_KEY: str = "super-secret-key-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30    
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "..", "..", ".env"), 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()
