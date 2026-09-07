"""Opening the web client from the Profile menu.

Two things are being defended. First, the URL: the token belongs in the query
string the web client reads, and nothing else about the configured URL may be
lost on the way. Second, the failure behaviour: when the handoff cannot be
minted the user must still reach the web client's login screen, and must never
be shown a fabricated signed-in state -- an honest login page is the correct
answer to "we could not prove who you are".
"""

import pytest

from app.api.exceptions import ApiConnectionError, ApiError, ApiHttpError
from app.portal.service import PortalService, build_web_url


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def post(self, path, json_data=None, timeout=None):
        self.calls.append(path)
        if self.error is not None:
            raise self.error
        return self.response


# ── URL shape ────────────────────────────────────────────────────────────────

def test_the_token_is_handed_over_in_the_query_string():
    url = build_web_url("https://app.example.com", "mh_abc123")
    assert url == "https://app.example.com/?token=mh_abc123"


def test_without_a_token_the_plain_web_client_is_opened():
    """The login screen is the honest destination when there is no handoff."""
    assert build_web_url("https://app.example.com") == "https://app.example.com/"


def test_an_existing_path_and_query_survive_the_handoff():
    url = build_web_url("https://app.example.com/portal?ref=desktop", "mh_x")
    assert url == "https://app.example.com/portal?ref=desktop&token=mh_x"


def test_a_token_needing_escaping_is_encoded():
    url = build_web_url("https://app.example.com", "mh_a b&c")
    assert url == "https://app.example.com/?token=mh_a+b%26c"


# ── Minting the token ────────────────────────────────────────────────────────

def test_a_minted_token_is_returned_from_the_backend_response():
    client = _FakeClient(_FakeResponse({"token": "mh_abc", "expires_at": "2026-09-07T00:00:00Z"}))
    assert PortalService(client).create_handoff_token() == "mh_abc"
    assert client.calls == ["/auth/sso/handoff"]


def test_an_expired_session_is_reported_as_one():
    client = _FakeClient(error=ApiHttpError(401, ""))
    with pytest.raises(ApiError) as caught:
        PortalService(client).create_handoff_token()
    assert "sign in" in str(caught.value).lower()


def test_being_offline_is_reported_rather_than_faked():
    client = _FakeClient(error=ApiConnectionError("no route"))
    with pytest.raises(ApiError):
        PortalService(client).create_handoff_token()


def test_a_response_without_a_token_is_a_failure_not_an_empty_url():
    """A blank token would open `?token=` and look like a broken login link."""
    client = _FakeClient(_FakeResponse({"token": "   "}))
    with pytest.raises(ApiError):
        PortalService(client).create_handoff_token()
