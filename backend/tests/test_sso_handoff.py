"""The desktop → web single sign-on handoff.

The desktop client holds a local session, not a provider token, so it cannot
use the portal's `?token=` path directly. It asks for a handoff token and opens
the web client with it. Two properties are worth defending here, because losing
either turns a convenience into a credential:

* a handoff token is redeemable exactly once, and only before it expires;
* a provider token is never matched against local rows, and a handoff token is
  never sent to the provider.
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.core.config import settings
from app.core.security import hash_token
from app.services.auth import HANDOFF_TOKEN_PREFIX, AuthService


def _user(**overrides):
    user = MagicMock()
    user.id = 77
    user.is_active = True
    user.status = "active"
    for key, value in overrides.items():
        setattr(user, key, value)
    return user


class _FakeSession:
    """Enough Session to drive minting and redemption, and no more.

    `claimed_user_id` stands in for the conditional UPDATE ... RETURNING that
    claims the row: None means no unspent, unexpired row matched.
    """

    def __init__(self, claimed_user_id=None):
        self._claimed_user_id = claimed_user_id
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.statements = []

    def add(self, obj):
        self.added.append(obj)

    def execute(self, statement):
        self.statements.append(statement)
        result = MagicMock()
        result.scalar.return_value = self._claimed_user_id
        # Redemption claims the row; a second attempt finds nothing to claim.
        self._claimed_user_id = None
        return result

    def scalar(self, _statement):
        return None

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class TestIssueHandoffToken(unittest.TestCase):
    def test_token_is_prefixed_stored_hashed_and_short_lived(self):
        db = _FakeSession()

        token, expires_at = AuthService.issue_handoff_token(db, _user())

        self.assertTrue(token.startswith(HANDOFF_TOKEN_PREFIX))
        row = db.added[0]
        # Only the hash is persisted: a database dump must not hand anyone a
        # usable sign-in link.
        self.assertEqual(row.token_hash, hash_token(token))
        self.assertNotIn(token, (row.token_hash,))
        self.assertEqual(row.user_id, 77)
        self.assertLessEqual(
            expires_at - datetime.now(timezone.utc),
            timedelta(seconds=settings.SSO_HANDOFF_TOKEN_EXPIRE_SECONDS + 1),
        )

    def test_every_token_is_distinct(self):
        db = _FakeSession()
        first, _ = AuthService.issue_handoff_token(db, _user())
        second, _ = AuthService.issue_handoff_token(db, _user())
        self.assertNotEqual(first, second)


class TestRedeemHandoffToken(unittest.IsolatedAsyncioTestCase):
    async def test_a_valid_handoff_signs_the_user_in_without_the_provider(self):
        db = _FakeSession(claimed_user_id=77)
        with patch("app.services.auth.UserRepository.get_by_id", return_value=_user()), \
             patch("app.services.auth.AuthService._issue_token_pair", return_value="pair") as issue, \
             patch("app.services.auth.ExternalAuthService.authenticate_token") as provider:
            result = await AuthService.sso_exchange(db, f"{HANDOFF_TOKEN_PREFIX}abc")

        self.assertEqual(result, "pair")
        issue.assert_called_once()
        # The provider never issued this token, so it is never asked about it.
        provider.assert_not_called()

    async def test_a_handoff_cannot_be_redeemed_twice(self):
        db = _FakeSession(claimed_user_id=77)
        with patch("app.services.auth.UserRepository.get_by_id", return_value=_user()), \
             patch("app.services.auth.AuthService._issue_token_pair", return_value="pair"), \
             patch("app.services.auth.ExternalAuthService.authenticate_token"):
            await AuthService.sso_exchange(db, f"{HANDOFF_TOKEN_PREFIX}abc")

            with self.assertRaises(HTTPException) as caught:
                await AuthService.sso_exchange(db, f"{HANDOFF_TOKEN_PREFIX}abc")

        self.assertEqual(caught.exception.status_code, 401)

    async def test_an_unknown_or_expired_handoff_is_refused(self):
        db = _FakeSession(claimed_user_id=None)
        with patch("app.services.auth.ExternalAuthService.authenticate_token") as provider:
            with self.assertRaises(HTTPException) as caught:
                await AuthService.sso_exchange(db, f"{HANDOFF_TOKEN_PREFIX}gone")

        self.assertEqual(caught.exception.status_code, 401)
        provider.assert_not_called()

    async def test_an_inactive_account_cannot_be_handed_off_to(self):
        db = _FakeSession(claimed_user_id=77)
        with patch("app.services.auth.UserRepository.get_by_id", return_value=_user(status="disabled")):
            with self.assertRaises(HTTPException) as caught:
                await AuthService.sso_exchange(db, f"{HANDOFF_TOKEN_PREFIX}abc")

        self.assertEqual(caught.exception.status_code, 403)

    async def test_a_provider_token_still_goes_to_the_provider(self):
        """The portal path must be untouched by the desktop path existing."""
        db = _FakeSession(claimed_user_id=77)
        with patch("app.services.auth.ExternalAuthService.authenticate_token") as provider:
            provider.return_value = {"email": "ada@example.com", "display_name": "Ada"}
            with patch("app.services.auth.UserRepository.get_by_normalized_email", return_value=_user()), \
                 patch("app.services.auth.AuthService._issue_token_pair", return_value="pair"):
                result = await AuthService.sso_exchange(db, "eyJhbGciOiJIUzI1NiJ9.portal")

        self.assertEqual(result, "pair")
        provider.assert_called_once()


if __name__ == "__main__":
    unittest.main()
