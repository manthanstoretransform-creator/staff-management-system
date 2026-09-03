"""Desktop update check and fleet version visibility.

Unit tests in the style of the rest of this suite: the session and the
repository are mocked, so the policy is exercised without a database. What
they pin down is the part a client must not be trusted with -- whether an
update actually exists, and what counts as "newer".
"""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.desktop_release import (
    DesktopReleaseService, parse_client_version, version_tuple,
)

SVC = "app.services.desktop_release"


class ParseClientVersionTests(unittest.TestCase):

    def test_reads_the_version_the_desktop_sends(self):
        self.assertEqual(parse_client_version("Monitra/1.2.3"), "1.2.3")

    def test_ignores_clients_that_are_not_monitra(self):
        # The React frontend and any browser hit the same API. Recording their
        # User-Agent as a desktop version would make the fleet view fiction.
        self.assertIsNone(parse_client_version("Mozilla/5.0 (Windows NT 10.0)"))
        self.assertIsNone(parse_client_version("MonitraFake/1.0.0"))
        self.assertIsNone(parse_client_version(None))
        self.assertIsNone(parse_client_version(""))

    def test_rejects_a_non_numeric_version(self):
        self.assertIsNone(parse_client_version("Monitra/1.0.0-rc1"))


class VersionComparisonTests(unittest.TestCase):

    def test_parses_only_major_minor_patch(self):
        self.assertEqual(version_tuple("1.10.2"), (1, 10, 2))
        for bad in ("1.0", "1.0.0.0", "v1.0.0", "1.0.0-rc1", "", None):
            self.assertIsNone(version_tuple(bad), bad)

    def test_update_available_only_when_strictly_newer(self):
        available = DesktopReleaseService.is_update_available
        self.assertTrue(available("1.0.0", "1.0.1"))
        self.assertTrue(available("1.9.0", "1.10.0"))  # not string comparison
        self.assertFalse(available("1.0.1", "1.0.1"))
        self.assertFalse(available("1.2.0", "1.0.1"))  # never prompt downgrades

    def test_unknown_versions_never_prompt(self):
        # An unidentified client is not evidence that it is out of date, and a
        # deployment that does not know its latest release must not guess.
        available = DesktopReleaseService.is_update_available
        self.assertFalse(available(None, "1.0.1"))
        self.assertFalse(available("1.0.0", None))
        self.assertFalse(available("garbage", "1.0.1"))


class ConfiguredLatestVersionTests(unittest.TestCase):

    def test_unset_means_unknown_not_zero(self):
        with patch(f"{SVC}.settings") as settings:
            settings.DESKTOP_LATEST_VERSION = ""
            self.assertIsNone(DesktopReleaseService.configured_latest_version())

    def test_a_misconfigured_value_is_refused_rather_than_served(self):
        with patch(f"{SVC}.settings") as settings:
            settings.DESKTOP_LATEST_VERSION = "latest"
            self.assertIsNone(DesktopReleaseService.configured_latest_version())


class LatestVersionResponseTests(unittest.TestCase):

    def _user(self):
        user = MagicMock()
        user.id = 7
        user.organization_id = 1
        return user

    def test_no_configured_release_returns_an_honest_empty_answer(self):
        with patch(f"{SVC}.settings") as settings, \
                patch(f"{SVC}.DesktopClientVersionRepository") as repo:
            settings.DESKTOP_LATEST_VERSION = ""
            settings.DESKTOP_DOWNLOAD_URL = "https://example.invalid/download"
            result = DesktopReleaseService.latest_version(
                MagicMock(), self._user(), "1.0.0", "win32"
            )
        self.assertIsNone(result.latest_version)
        # No version means no download link either: a link on its own would
        # invite a prompt for a release that does not exist.
        self.assertIsNone(result.download_url)
        self.assertFalse(result.update_available)
        # The client's version is still recorded -- fleet visibility does not
        # depend on there being a newer release.
        repo.upsert.assert_called_once()

    def test_a_newer_release_is_offered_with_its_download_url(self):
        with patch(f"{SVC}.settings") as settings, \
                patch(f"{SVC}.DesktopClientVersionRepository"):
            settings.DESKTOP_LATEST_VERSION = "1.1.0"
            settings.DESKTOP_DOWNLOAD_URL = "https://example.invalid/releases"
            settings.DESKTOP_RELEASE_NOTES_URL = "https://example.invalid/notes"
            result = DesktopReleaseService.latest_version(
                MagicMock(), self._user(), "1.0.1", "darwin"
            )
        self.assertEqual(result.latest_version, "1.1.0")
        self.assertEqual(result.download_url, "https://example.invalid/releases")
        self.assertTrue(result.update_available)
        self.assertEqual(result.client_version, "1.0.1")

    def test_recording_a_version_never_fails_the_request(self):
        # Version visibility is diagnostics. Failing the update check because
        # a diagnostics write failed would be the worse outcome.
        db = MagicMock()
        with patch(f"{SVC}.settings") as settings, \
                patch(f"{SVC}.DesktopClientVersionRepository") as repo:
            settings.DESKTOP_LATEST_VERSION = "1.1.0"
            settings.DESKTOP_DOWNLOAD_URL = ""
            settings.DESKTOP_RELEASE_NOTES_URL = ""
            repo.upsert.side_effect = RuntimeError("database is down")
            result = DesktopReleaseService.latest_version(
                db, self._user(), "1.0.0", "win32"
            )
        self.assertTrue(result.update_available)
        db.rollback.assert_called_once()

    def test_an_unidentified_client_is_not_recorded(self):
        with patch(f"{SVC}.settings") as settings, \
                patch(f"{SVC}.DesktopClientVersionRepository") as repo:
            settings.DESKTOP_LATEST_VERSION = "1.1.0"
            settings.DESKTOP_DOWNLOAD_URL = ""
            settings.DESKTOP_RELEASE_NOTES_URL = ""
            DesktopReleaseService.latest_version(MagicMock(), self._user(), None, None)
        repo.upsert.assert_not_called()


class FleetVersionsTests(unittest.TestCase):

    def test_counts_users_per_version(self):
        user = MagicMock()
        user.organization_id = 1
        now = datetime.now(timezone.utc)
        rows = [
            SimpleNamespace(
                user_id=index, app_version=version, platform="win32",
                first_seen_at=now, last_seen_at=now,
            )
            for index, version in enumerate(("1.0.0", "1.0.0", "1.1.0"))
        ]

        with patch(f"{SVC}.settings") as settings, \
                patch(f"{SVC}.DesktopClientVersionRepository") as repo:
            settings.DESKTOP_LATEST_VERSION = "1.1.0"
            repo.list_for_organization.return_value = rows
            result = DesktopReleaseService.fleet_versions(MagicMock(), user)

        self.assertEqual(result.counts, {"1.0.0": 2, "1.1.0": 1})
        self.assertEqual(result.latest_version, "1.1.0")
        self.assertEqual(len(result.clients), 3)


if __name__ == "__main__":
    unittest.main()
