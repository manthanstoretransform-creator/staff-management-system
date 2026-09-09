#!/usr/bin/env python
"""
register_release — tell the backend what CI just built.

    python tools/register_release.py --tag v1.2.0 --repo owner/name \\
        --artifacts dist/installer/Monitra-Setup-1.2.0.exe ...

For each artifact it computes the SHA-256 and size, works out which platform
and architecture the file is for, and POSTs it to
``/desktop/releases`` — which always creates a **draft**.

Why a draft, always
-------------------
CI can prove a build compiles, starts and passes its tests. It cannot decide
the build is good. Publishing is therefore a separate, deliberate act by a
person, exactly as the GitHub release itself stays a draft until someone
publishes it. This script has no way to publish and is not given a code path
that could.

Why the URL is derived rather than read back
--------------------------------------------
A draft GitHub release's asset URLs are not publicly reachable, so there is
nothing to read at the moment this runs. The public download URL for a release
asset is entirely predictable from the tag and the filename, and it starts
working the instant the release is published — which is the same moment the
backend release is meant to be published. Deriving it keeps both halves in
step without CI having to publish anything early.

Failure here does not fail the build. The artifacts exist and the GitHub
release exists either way; a backend that was unreachable for a minute should
not turn a good build into a failed one, and the registration can be re-run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

DESKTOP_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DESKTOP_ROOT))

import version  # noqa: E402  - after the path is set up

#: How a built filename maps onto a platform and architecture. Ordered, and
#: matched against the *filename* the build scripts produce -- the names are
#: fixed in `packaging/` and `scripts/`, so this is a contract inside this
#: repository rather than a guess about arbitrary input.
ARTIFACT_PATTERNS = (
    (re.compile(r"^Monitra-Setup-.*\.exe$", re.I), "win32", None),
    (re.compile(r"^Monitra-macOS-arm64-.*\.dmg$", re.I), "darwin", "arm64"),
    (re.compile(r"^Monitra-macOS-x86_64-.*\.dmg$", re.I), "darwin", "x86_64"),
)

#: The portable zip is deliberately *not* registered. It is a folder the user
#: unzips wherever they choose, so there is no installer to hand an update to
#: and `installer.can_install()` refuses to auto-update one. Registering it
#: would advertise an update path that does not exist.
IGNORED_PATTERNS = (re.compile(r"^Monitra-Portable-.*\.zip$", re.I),)

CHUNK = 1024 * 1024


def classify(name: str) -> Optional[Tuple[str, Optional[str]]]:
    """(platform, architecture) for an artifact filename, or None to skip."""
    for pattern in IGNORED_PATTERNS:
        if pattern.match(name):
            return None
    for pattern, platform, arch in ARTIFACT_PATTERNS:
        if pattern.match(name):
            return platform, arch
    return None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def asset_url(repo: str, tag: str, filename: str) -> str:
    """The public download URL a release asset will have once published."""
    return f"https://github.com/{repo}/releases/download/{tag}/{filename}"


def release_notes(version_string: str) -> Optional[str]:
    """This version's section of CHANGELOG.md, as plain text.

    The hand-written note, not the auto-generated commit list: this is what a
    person reads in the update dialog, and `tools/check_changelog.py` has
    already refused the build if it is missing.
    """
    changelog = DESKTOP_ROOT / "CHANGELOG.md"
    if not changelog.is_file():
        return None
    text = changelog.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^##+\s*\[?{re.escape(version_string)}\]?.*?$(.*?)(?=^##+\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None
    body = match.group(1).strip()
    return body or None


def sign_in(base_url: str, email: str, password: str) -> Optional[str]:
    """Exchange the release account's credentials for a short-lived token.

    Why credentials rather than a token in the CI secret: an access token is
    valid for thirty minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`), so one pasted
    into a repository secret is dead long before the next release and every
    registration would fail with a 401 nobody could explain. The credential
    that lives in CI therefore has to be something that does not expire, and
    the token is minted here, used immediately, and never stored.

    The account behind it holds the `release_bot` role -- a single permission,
    `manage_desktop_releases` -- so this credential can register and publish
    releases and do nothing else at all.
    """
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/auth/dev-login",
        data=json.dumps({"email": email, "password": password}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": f"MonitraReleasePipeline/{version.VERSION}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            token = json.loads(response.read().decode("utf-8")).get("access_token")
            if not token:
                print("sign-in succeeded but returned no access token", file=sys.stderr)
                return None
            return token
    except urllib.error.HTTPError as exc:
        # Deliberately does not echo the body: it is an auth failure, and the
        # response to a bad credential is not something to widen in a public
        # build log.
        print(f"sign-in FAILED: HTTP {exc.code}", file=sys.stderr)
        return None
    except urllib.error.URLError as exc:
        print(f"sign-in FAILED: {exc.reason}", file=sys.stderr)
        return None


def post_release(base_url: str, token: str, payload: dict) -> bool:
    """Register one artifact. Returns whether it is now registered."""
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/desktop/releases",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": f"MonitraReleasePipeline/{version.VERSION}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            print(f"  registered ({response.status})")
            return True
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            # Already registered. Re-running the pipeline for the same tag is a
            # normal thing to do, and it must not look like a failure.
            print("  already registered; leaving it alone")
            return True
        body = exc.read().decode("utf-8", "replace")[:400]
        print(f"  FAILED: HTTP {exc.code} {body}", file=sys.stderr)
        return False
    except urllib.error.URLError as exc:
        print(f"  FAILED: {exc.reason}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="Git tag, e.g. v1.2.0")
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--artifacts", nargs="+", required=True)
    parser.add_argument(
        "--force-update", action="store_true",
        help="Mark these artifacts as a mandatory update.",
    )
    parser.add_argument(
        "--min-supported-version", default=None,
        help="Oldest version still allowed to keep working.",
    )
    args = parser.parse_args()

    base_url = os.environ.get("MONITRA_API_BASE_URL", "").strip()
    token = os.environ.get("MONITRA_RELEASE_TOKEN", "").strip()
    email = os.environ.get("MONITRA_RELEASE_EMAIL", "").strip()
    password = os.environ.get("MONITRA_RELEASE_PASSWORD", "")

    if not base_url or not (token or (email and password)):
        # Not configured is not a failure: a fork, or a repository that has not
        # been given the credentials, still produces perfectly good artifacts.
        print(
            "MONITRA_API_BASE_URL and a release credential "
            "(MONITRA_RELEASE_EMAIL + MONITRA_RELEASE_PASSWORD, or "
            "MONITRA_RELEASE_TOKEN) are not set; skipping backend "
            "registration.\nThe artifacts and the GitHub release are "
            "unaffected."
        )
        return 0

    if not token:
        # The normal path. A ready-made token is still accepted so a person can
        # register a build by hand from a session they already have, but it is
        # not what CI uses -- see sign_in().
        token = sign_in(base_url, email, password)
        if not token:
            print(
                "Could not sign in as the release account; nothing was "
                "registered. The artifacts and the GitHub release are "
                "unaffected, and this step can be re-run.",
                file=sys.stderr,
            )
            return 0

    expected = version.VERSION
    if args.tag.lstrip("v") != expected:
        # A tag that disagrees with version.py means the artifacts are not the
        # version the tag claims. Registering either number would make a
        # support report untrustworthy.
        print(
            f"tag {args.tag} does not match version.py ({expected}); refusing "
            "to register.",
            file=sys.stderr,
        )
        return 1

    notes = release_notes(expected)
    failures = 0
    registered = 0

    for raw in args.artifacts:
        path = Path(raw)
        if not path.is_file():
            continue
        classification = classify(path.name)
        if classification is None:
            print(f"{path.name}: not a registrable artifact, skipping")
            continue
        platform, architecture = classification

        print(f"{path.name} -> {platform}/{architecture or 'any'}")
        payload = {
            "version": expected,
            "platform": platform,
            "architecture": architecture,
            "download_url": asset_url(args.repo, args.tag, path.name),
            "sha256": sha256_of(path),
            "file_size": path.stat().st_size,
            "release_notes": notes,
            "force_update": bool(args.force_update),
            "min_supported_version": args.min_supported_version,
        }
        if post_release(base_url, token, payload):
            registered += 1
        else:
            failures += 1

    print(f"\n{registered} artifact(s) registered as drafts, {failures} failed.")
    if failures:
        # Reported, but not fatal: the build and the GitHub release are good,
        # and registration can be re-run without rebuilding anything.
        print(
            "Registration is incomplete. Re-run this step, or register the "
            "remaining artifacts by hand, before publishing the release.",
            file=sys.stderr,
        )
    print(
        "\nNothing is live yet. Publish each release through "
        "POST /desktop/releases/{id}/publish once the build has been piloted."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
