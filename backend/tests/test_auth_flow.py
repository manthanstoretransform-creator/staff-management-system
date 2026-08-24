import unittest
import uuid
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.core.config import settings
from app.services.auth import AuthService


class FakeAsyncClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        return self.response


class CapturingAsyncClient(FakeAsyncClient):
    def __init__(self, response):
        super().__init__(response)
        self.post_args = None
        self.post_kwargs = None

    async def post(self, *args, **kwargs):
        self.post_args = args
        self.post_kwargs = kwargs
        return self.response


class AuthFlowTests(unittest.IsolatedAsyncioTestCase):
    def test_provider_url_is_the_required_hubstaff_login_endpoint(self):
        self.assertEqual(
            settings.WORDPRESS_LOGIN_URL,
            "https://dev-st-performance.pantheonsite.io/wp-json/st-performance/v1/auth/hubstaff/login",
        )

    async def test_provider_receives_the_desktop_login_payload(self):
        response = MagicMock(status_code=401)
        client = CapturingAsyncClient(response)
        db = MagicMock()

        with patch("app.services.external_auth_service.httpx.AsyncClient", return_value=client) as client_factory:
            with self.assertRaises(HTTPException):
                await AuthService.login_exchange(db, "  user@example.com  ", "provider-password")

        client_factory.assert_called_once()
        _, kwargs = client_factory.call_args
        self.assertEqual(kwargs.get("http2"), False)
        self.assertIn("verify", kwargs)
        self.assertEqual(client.post_args, (settings.WORDPRESS_LOGIN_URL,))
        self.assertEqual(
            client.post_kwargs["json"],
            {"username": "user@example.com", "password": "provider-password"},
        )
        headers = client.post_kwargs["headers"]
        self.assertEqual(headers["Accept"], "*/*")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["User-Agent"], settings.WORDPRESS_LOGIN_USER_AGENT)
        self.assertEqual(headers["Cache-Control"], "no-cache")
        self.assertEqual(headers["Accept-Encoding"], "gzip, deflate, br")
        self.assertIsInstance(uuid.UUID(headers["Postman-Token"]), uuid.UUID)
        self.assertEqual(client.post_kwargs["timeout"].connect, settings.EXTERNAL_AUTH_CONNECT_TIMEOUT)
        self.assertEqual(client.post_kwargs["timeout"].read, settings.EXTERNAL_AUTH_READ_TIMEOUT)

    async def test_html_provider_403_is_reported_as_a_provider_block(self):
        response = MagicMock(status_code=403)
        response.headers = {"content-type": "text/html; charset=utf-8"}
        response.text = "<html><title>Access denied</title></html>"
        db = MagicMock()

        with patch("app.services.external_auth_service.httpx.AsyncClient", return_value=FakeAsyncClient(response)):
            with self.assertRaises(HTTPException) as error:
                await AuthService.login_exchange(db, "user@example.com", "provider-password")

        self.assertEqual(error.exception.status_code, 502)
        self.assertIn("unavailable", error.exception.detail)
        db.scalar.assert_not_called()

    async def test_invalid_credentials_are_rejected_by_provider(self):
        response = MagicMock(status_code=401)
        db = MagicMock()

        with patch("app.services.external_auth_service.httpx.AsyncClient", return_value=FakeAsyncClient(response)):
            with self.assertRaises(HTTPException) as error:
                await AuthService.login_exchange(db, "user@example.com", "wrong")

        self.assertEqual(error.exception.status_code, 401)
        db.scalar.assert_not_called()

    async def test_provider_success_can_provision_without_local_lookup_first(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "status": "success",
            "user": {
                "hubstaff_user_id": "new-external-id",
                "email": "new@example.com",
                "name": "New User",
                "hubstaff_designation": "Engineer",
                "permission_schema": {"name": "employee", "permissions": {}},
            },
        }
        db = MagicMock()
        db.scalar.side_effect = [None, None]
        db.execute.return_value.scalar.return_value = 1

        with patch("app.services.external_auth_service.httpx.AsyncClient", return_value=FakeAsyncClient(response)), \
             patch("app.services.auth.UserRepository.create") as create_user, \
             patch("app.services.auth.create_access_token", return_value="sms-token"), \
             patch("app.services.auth.TokenPair", return_value="token-pair"):
            user = MagicMock(id=42, organization_id=1, role_name="employee", permissions={})
            user.username = "new"
            user.email = "new@example.com"
            user.name = "New User"
            user.designation = "Engineer"
            user.wp_capabilities = {}
            user.status = "active"
            user.is_active = True
            user.hubstaff_user_id = "new-external-id"
            user.idle_enabled = True
            user.idle_minutes = 5
            user.capture_frequency = 300
            create_user.return_value = user

            result = await AuthService.login_exchange(db, "new@example.com", "provider-password")

        self.assertEqual(result, "token-pair")
        create_user.assert_called_once()
        self.assertEqual(db.scalar.call_count, 2)


if __name__ == "__main__":
    unittest.main()
