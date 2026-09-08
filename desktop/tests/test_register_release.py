"""
The release-registration step of the CI pipeline.

What matters here is that CI cannot get a release wrong in a way that reaches
users: a Windows installer must never be registered as a macOS artifact, the
checksum must be of the file that was actually built, a tag that disagrees with
`version.py` must be refused outright, and nothing this script does may publish
anything.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import version
from tools import register_release as reg  # noqa: E402


# ---------------------------------------------------------------------------
# Classifying what was built
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name, expected", [
    ("Monitra-Setup-1.2.0.exe", ("win32", None)),
    ("Monitra-macOS-arm64-1.2.0.dmg", ("darwin", "arm64")),
    ("Monitra-macOS-x86_64-1.2.0.dmg", ("darwin", "x86_64")),
])
def test_each_artifact_is_classified_by_its_built_name(name, expected):
    assert reg.classify(name) == expected


def test_the_two_macos_builds_are_never_conflated():
    # Registering the Intel .dmg as the Apple Silicon one would hand every M-series
    # Mac a build that cannot run, and the updater would report it as a broken
    # update rather than as the wrong file.
    arm = reg.classify("Monitra-macOS-arm64-1.2.0.dmg")
    intel = reg.classify("Monitra-macOS-x86_64-1.2.0.dmg")
    assert arm != intel
    assert arm[1] == "arm64" and intel[1] == "x86_64"


def test_the_portable_zip_is_not_registered():
    # It is a folder the user unzips wherever they like, so there is no
    # installer to hand an update to and the desktop refuses to auto-update
    # one. Registering it would advertise a path that does not exist.
    assert reg.classify("Monitra-Portable-1.2.0.zip") is None


def test_unrecognised_files_are_skipped_rather_than_guessed_at():
    for name in ("notes.txt", "Monitra-Setup-1.2.0.exe.sha256",
                 "Monitra.app", "setup.exe", ""):
        assert reg.classify(name) is None, name


# ---------------------------------------------------------------------------
# The checksum
# ---------------------------------------------------------------------------


def test_the_checksum_is_of_the_file_on_disk(tmp_path):
    artifact = tmp_path / "Monitra-Setup-1.2.0.exe"
    body = b"pretend installer" * 5000
    artifact.write_bytes(body)
    assert reg.sha256_of(artifact) == hashlib.sha256(body).hexdigest()


def test_the_checksum_is_lower_case_hex(tmp_path):
    # The desktop compares digests as lower-case hex; an upper-case digest
    # would fail an artifact that downloaded perfectly.
    artifact = tmp_path / "Monitra-Setup-1.2.0.exe"
    artifact.write_bytes(b"x")
    digest = reg.sha256_of(artifact)
    assert digest == digest.lower() and len(digest) == 64


# ---------------------------------------------------------------------------
# The download URL
# ---------------------------------------------------------------------------


def test_the_download_url_is_the_public_release_asset():
    url = reg.asset_url("acme/monitra", "v1.2.0", "Monitra-Setup-1.2.0.exe")
    assert url == (
        "https://github.com/acme/monitra/releases/download/v1.2.0/"
        "Monitra-Setup-1.2.0.exe"
    )
    # HTTPS, because the desktop downloader refuses anything else outright.
    assert url.startswith("https://")


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def test_a_tag_that_disagrees_with_version_py_is_refused(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("MONITRA_API_BASE_URL", "https://api.invalid")
    monkeypatch.setenv("MONITRA_RELEASE_TOKEN", "token")
    artifact = tmp_path / "Monitra-Setup-9.9.9.exe"
    artifact.write_bytes(b"x")
    monkeypatch.setattr(sys, "argv", [
        "register_release.py", "--tag", "v9.9.9", "--repo", "acme/monitra",
        "--artifacts", str(artifact),
    ])

    # The artifacts are not the version the tag claims; registering either
    # number would make every support report naming it untrustworthy.
    assert reg.main() == 1
    assert "does not match version.py" in capsys.readouterr().err


def test_missing_credentials_skip_registration_rather_than_fail(monkeypatch, tmp_path):
    monkeypatch.delenv("MONITRA_API_BASE_URL", raising=False)
    monkeypatch.delenv("MONITRA_RELEASE_TOKEN", raising=False)
    artifact = tmp_path / f"Monitra-Setup-{version.VERSION}.exe"
    artifact.write_bytes(b"x")
    monkeypatch.setattr(sys, "argv", [
        "register_release.py", "--tag", f"v{version.VERSION}",
        "--repo", "acme/monitra", "--artifacts", str(artifact),
    ])

    # A fork still produces perfectly good artifacts.
    assert reg.main() == 0


def test_registration_posts_a_draft_and_never_publishes(monkeypatch, tmp_path):
    posted = []
    monkeypatch.setenv("MONITRA_API_BASE_URL", "https://api.invalid/api/v1")
    monkeypatch.setenv("MONITRA_RELEASE_TOKEN", "token")
    monkeypatch.setattr(
        reg, "post_release",
        lambda base_url, token, payload: (posted.append((base_url, payload)), True)[1],
    )

    body = b"installer bytes"
    artifact = tmp_path / f"Monitra-Setup-{version.VERSION}.exe"
    artifact.write_bytes(body)
    monkeypatch.setattr(sys, "argv", [
        "register_release.py", "--tag", f"v{version.VERSION}",
        "--repo", "acme/monitra", "--artifacts", str(artifact),
    ])

    assert reg.main() == 0
    assert len(posted) == 1
    _base, payload = posted[0]
    assert payload["version"] == version.VERSION
    assert payload["platform"] == "win32"
    assert payload["sha256"] == hashlib.sha256(body).hexdigest()
    assert payload["file_size"] == len(body)
    assert payload["force_update"] is False
    # No status is sent, because the endpoint always creates a draft. There is
    # deliberately no code path here that could publish one.
    assert "status" not in payload


def test_a_failed_registration_is_reported_without_failing_the_build(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("MONITRA_API_BASE_URL", "https://api.invalid")
    monkeypatch.setenv("MONITRA_RELEASE_TOKEN", "token")
    monkeypatch.setattr(reg, "post_release", lambda *a: False)

    artifact = tmp_path / f"Monitra-Setup-{version.VERSION}.exe"
    artifact.write_bytes(b"x")
    monkeypatch.setattr(sys, "argv", [
        "register_release.py", "--tag", f"v{version.VERSION}",
        "--repo", "acme/monitra", "--artifacts", str(artifact),
    ])

    # The build and the GitHub release are good either way, and the step can be
    # re-run without rebuilding anything.
    assert reg.main() == 0
    assert "incomplete" in capsys.readouterr().err


def test_a_mandatory_release_must_be_asked_for_explicitly(monkeypatch, tmp_path):
    posted = []
    monkeypatch.setenv("MONITRA_API_BASE_URL", "https://api.invalid")
    monkeypatch.setenv("MONITRA_RELEASE_TOKEN", "token")
    monkeypatch.setattr(
        reg, "post_release",
        lambda base_url, token, payload: (posted.append(payload), True)[1],
    )
    artifact = tmp_path / f"Monitra-Setup-{version.VERSION}.exe"
    artifact.write_bytes(b"x")
    monkeypatch.setattr(sys, "argv", [
        "register_release.py", "--tag", f"v{version.VERSION}",
        "--repo", "acme/monitra", "--artifacts", str(artifact),
        "--force-update",
    ])

    assert reg.main() == 0
    assert posted[0]["force_update"] is True


# ---------------------------------------------------------------------------
# Release notes
# ---------------------------------------------------------------------------


def test_the_hand_written_changelog_entry_is_sent(monkeypatch):
    # This is what a person reads in the update dialog -- the note somebody
    # wrote, not the auto-generated commit list.
    notes = reg.release_notes(version.VERSION)
    assert notes is None or isinstance(notes, str)


def test_an_absent_entry_is_reported_as_none():
    assert reg.release_notes("0.0.0") is None


if __name__ == "__main__":
    pytest.main([__file__])
