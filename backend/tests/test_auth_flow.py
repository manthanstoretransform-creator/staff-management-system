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


class FakeSsoClient:
    """Provider double for the two calls the SSO exchange makes."""

    def __init__(self, validate_response, profile_response=None):
        self.validate_response = validate_response
        self.profile_response = profile_response
        self.post_args = None
        self.post_kwargs = None
        self.get_args = None
        self.get_kwargs = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        self.post_args = args
        self.post_kwargs = kwargs
        return self.validate_response

    async def get(self, *args, **kwargs):
        self.get_args = args
        self.get_kwargs = kwargs
        return self.profile_response


def _valid_validation_response():
    response = MagicMock(status_code=200)
    response.json.return_value = {"code": "jwt_auth_valid_token", "data": {"status": 200}}
    return response


def _profile_response(**overrides):
    payload = {
        "user_id": 1,
        "username": "st-performance",
        "email": "sanjay@example.com",
        "display_name": "Sanjay",
        "first_name": "Sanjay",
        "last_name": "Mandaviya",
        "roles": ["leader"],
    }
    payload.update(overrides)
    response = MagicMock(status_code=200)
    response.json.return_value = {"status": "success", "code": 200, "data": payload}
    return response


class SsoTokenExchangeTests(unittest.IsolatedAsyncioTestCase):
    def test_provider_sso_urls_point_at_the_configured_site(self):
        self.assertEqual(
            settings.WORDPRESS_TOKEN_VALIDATE_URL,
            "https://dev-st-performance.pantheonsite.io/wp-json/jwt-auth/v1/token/validate",
        )
        self.assertEqual(
            settings.WORDPRESS_PROFILE_URL,
            "https://dev-st-performance.pantheonsite.io/wp-json/st-performance/v1/user/profile",
        )

    async def test_token_is_verified_with_the_provider_before_any_local_lookup(self):
        rejected = MagicMock(status_code=403)
        client = FakeSsoClient(rejected)
        db = MagicMock()

        with patch("app.services.external_auth_service.httpx.AsyncClient", return_value=client):
            with self.assertRaises(HTTPException) as error:
                await AuthService.sso_exchange(db, "forged.token.value")

        self.assertEqual(error.exception.status_code, 401)
        self.assertEqual(client.post_args, (settings.WORDPRESS_TOKEN_VALIDATE_URL,))
        self.assertEqual(
            client.post_kwargs["headers"]["Authorization"], "Bearer forged.token.value"
        )
        # The forged token must never reach the database.
        db.scalar.assert_not_called()

    async def test_a_token_the_provider_reports_as_invalid_is_rejected(self):
        invalid = MagicMock(status_code=200)
        invalid.json.return_value = {"code": "jwt_auth_invalid_token", "data": {"status": 403}}
        db = MagicMock()

        with patch("app.services.external_auth_service.httpx.AsyncClient", return_value=FakeSsoClient(invalid)):
            with self.assertRaises(HTTPException) as error:
                await AuthService.sso_exchange(db, "expired.token.value")

        self.assertEqual(error.exception.status_code, 401)
        db.scalar.assert_not_called()

    async def test_valid_token_issues_a_local_session_for_the_matching_user(self):
        client = FakeSsoClient(_valid_validation_response(), _profile_response())
        user = MagicMock(id=7, organization_id=1, role_name="leader", permissions={}, is_active=True)
        user.status = "active"
        db = MagicMock()

        with patch("app.services.external_auth_service.httpx.AsyncClient", return_value=client),              patch("app.services.auth.UserRepository.get_by_normalized_email", return_value=user) as lookup,              patch("app.services.auth.UserRepository.create") as create_user,              patch("app.services.auth.create_access_token", return_value="sms-token"),              patch("app.services.auth.UserRead") as user_read,              patch("app.services.auth.TokenPair", return_value="token-pair"):
            user_read.model_validate.return_value = "user-read"
            result = await AuthService.sso_exchange(db, "provider.token.value")

        self.assertEqual(result, "token-pair")
        lookup.assert_called_once()
        self.assertEqual(lookup.call_args[0][1], "sanjay@example.com")
        create_user.assert_not_called()
        self.assertEqual(client.get_args, (settings.WORDPRESS_PROFILE_URL,))

    async def test_unknown_identity_with_an_unmapped_role_is_refused_not_invented(self):
        client = FakeSsoClient(_valid_validation_response(), _profile_response())
        db = MagicMock()

        with patch("app.services.external_auth_service.httpx.AsyncClient", return_value=client),              patch("app.services.auth.UserRepository.get_by_normalized_email", return_value=None),              patch("app.services.auth.UserRepository.create") as create_user:
            with self.assertRaises(HTTPException) as error:
                await AuthService.sso_exchange(db, "provider.token.value")

        self.assertEqual(error.exception.status_code, 403)
        create_user.assert_not_called()

    async def test_deactivated_local_account_cannot_sign_in_through_sso(self):
        client = FakeSsoClient(_valid_validation_response(), _profile_response())
        user = MagicMock(id=7, organization_id=1, role_name="employee", permissions={}, is_active=False)
        user.status = "inactive"
        db = MagicMock()

        with patch("app.services.external_auth_service.httpx.AsyncClient", return_value=client),              patch("app.services.auth.UserRepository.get_by_normalized_email", return_value=user):
            with self.assertRaises(HTTPException) as error:
                await AuthService.sso_exchange(db, "provider.token.value")

        self.assertEqual(error.exception.status_code, 403)
        db.add.assert_not_called()


if __name__ == "__main__":
    unittest.main()
