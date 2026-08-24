import logging
import ssl
import uuid
import certifi
import httpx
import urllib3.util.ssl_
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

class ExternalAuthService:
    @staticmethod
    def _create_ssl_context() -> ssl.SSLContext:
        """Create a custom SSL context using urllib3 configuration to avoid JA3 blocks."""
        context = urllib3.util.ssl_.create_urllib3_context()
        context.load_verify_locations(cafile=certifi.where())
        return context

    @classmethod
    async def authenticate(cls, username: str, password: str) -> dict:
        """
        Authenticate credentials against the external Pantheon service.
        Returns the user data dict on success.
        Raises HTTPException for controlled outcomes.
        """
        normalized_username = username.strip()
        logger.info("AUTH_LOGIN_STARTED: Initiating login exchange for user: %s", normalized_username)
        
        url = settings.WORDPRESS_LOGIN_URL
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "User-Agent": settings.WORDPRESS_LOGIN_USER_AGENT,
            "Cache-Control": "no-cache",
            "Postman-Token": str(uuid.uuid4()),
            "Accept-Encoding": "gzip, deflate, br",
        }
        payload = {"username": normalized_username, "password": password}
        
        ssl_ctx = cls._create_ssl_context()
        
        logger.info("AUTH_PROVIDER_REQUEST_STARTED: Outbound request to provider url: %s", url)
        
        # Configure connection and read timeouts from settings
        timeout = httpx.Timeout(
            timeout=15.0,
            connect=settings.EXTERNAL_AUTH_CONNECT_TIMEOUT,
            read=settings.EXTERNAL_AUTH_READ_TIMEOUT
        )
        
        try:
            async with httpx.AsyncClient(verify=ssl_ctx, http2=False) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=timeout
                )
        except httpx.TimeoutException as e:
            logger.error("AUTH_PROVIDER_TIMEOUT: Outbound request timed out: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is temporarily unavailable"
            )
        except (httpx.ConnectError, httpx.NetworkError) as e:
            logger.error("AUTH_PROVIDER_CONNECTION_FAILED: Connection to provider failed: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is temporarily unavailable"
            )
        except httpx.HTTPError as e:
            logger.error("AUTH_PROVIDER_REQUEST_FAILED: Outbound request failed: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is temporarily unavailable"
            )
            
        logger.info(
            "AUTH_PROVIDER_RESPONSE_RECEIVED: Received response status: %s, Content-Type: %s",
            response.status_code,
            response.headers.get("content-type", "")
        )
        
        if response.status_code == 403:
            logger.error("AUTH_PROVIDER_FORBIDDEN: External provider returned 403 Forbidden")
            # If it's a WAF block (HTML), raise 502 with client-safe message
            if "application/json" not in response.headers.get("content-type", "").lower():
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Authentication service is temporarily unavailable"
                )
            # Otherwise, treat as invalid credentials
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
            
        if response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
            
        if response.status_code >= 500:
            logger.error("AUTH_PROVIDER_SERVER_ERROR: Provider returned status: %d", response.status_code)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is temporarily unavailable"
            )
            
        if response.status_code != 200:
            logger.error("AUTH_PROVIDER_UNEXPECTED_STATUS: Provider returned status: %d", response.status_code)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Authentication service is temporarily unavailable"
            )
            
        try:
            data = response.json()
        except (ValueError, TypeError) as e:
            logger.error("AUTH_PROVIDER_INVALID_RESPONSE: Malformed JSON received: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Authentication service is temporarily unavailable"
            )
            
        if not isinstance(data, dict) or data.get("status") == "failed" or "user" not in data:
            logger.error("AUTH_PROVIDER_INVALID_RESPONSE: Response layout invalid or login failed status")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
            
        user_data = data["user"]
        if not isinstance(user_data, dict):
            logger.error("AUTH_PROVIDER_INVALID_RESPONSE: Response 'user' field is not an object")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Authentication service is temporarily unavailable"
            )
            
        return user_data
