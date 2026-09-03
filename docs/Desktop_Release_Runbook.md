# Desktop Release Runbook

**Scope:** cutting, piloting, publishing, announcing and — when it goes wrong —
withdrawing a Monitra desktop release.

This is the *process* layer. The mechanics live elsewhere and are not repeated
here:

- `desktop/BUILD.md` — how each artifact is built, prerequisites,
  troubleshooting, and the clean-machine checklist.
- `desktop/version.py` — the single source of truth for the version number.
- `desktop/CHANGELOG.md` — the hand-written release note, one entry per version.
- `.github/workflows/desktop-release.yml` — build, test, package, checksum,
  draft release.
- `.github/workflows/desktop-stability.yml` — the correctness gate on every push.
- `docs/Desktop_Update_Distribution_Decisions.md` — the approvals this
  procedure implements.

---

## 1. Cutting a release

1. **Decide the version bump.** `major.minor.patch`, semver as `version.py`
   describes. Edit `VERSION` in `desktop/version.py`. Work on a branch.
2. **Write the changelog entry.** Add a `## [<version>]` section to
   `desktop/CHANGELOG.md` describing what changed *for the person installing
   it*. This is enforced: `tools/check_changelog.py` runs in CI and fails the
   build if the version in `version.py` has no entry. Auto-generated commit
   titles are not a substitute — they answer a different question.
3. **Run the full local gate**, from `desktop/`:

   ```bash
   python -m pytest tests/ -q
   python tools/check_architecture.py
   python tools/check_changelog.py
   python tests/soak/run_launch_cycles.py --cycles 10
   python tests/soak/run_soak.py --duration 60
   ```

   All five must pass before tagging.
4. **Merge to `main`**, then tag: `git tag v<version> && git push origin v<version>`.
5. **CI builds it.** Windows and both macOS architectures, each re-running the
   architecture check, the changelog check and the test suite *on that
   platform*, then packaging, smoke-testing the real binary, and computing a
   SHA-256 sidecar per artifact.
6. **A draft release opens automatically** with every artifact and checksum
   attached. Nothing is public yet, and this gate stays — a human publishes.

## 2. The pilot ring — mandatory before publishing

**No release goes to the whole team without a pilot.** This is the cheapest
defence available and it is pure process: no code, no infrastructure.

- Install **the CI-built artifacts**, not a local rebuild. The thing being
  tested is the thing being shipped.
- Pilot group: the engineering team, **plus at least one Windows and one macOS
  user who did not build the release**. A build only ever tested by its author
  has not been tested by a user.
- Run the clean-machine checklist in `BUILD.md` §14 — installing without admin
  rights, version metadata, login, tracking, offline and reconnect, uninstall,
  reinstall over the top, sleep/wake, force-kill recovery, and on macOS the
  permission grant/deny paths.
- Soak for **at least one full working day**, covering a real start-of-day
  login, a normal working session and a normal end-of-day shutdown. Most of
  what a pilot catches is not visible in the first ten minutes.
- Verify the checksum of at least one downloaded artifact, so the published
  sidecars are known to be correct rather than assumed to be.

Only when the pilot signs off does the draft get published.

## 3. Publishing and announcing

1. Publish the draft GitHub release.
2. **Point the in-app update notice at it.** Set on the backend deployment:

   | Variable | Value |
   |---|---|
   | `DESKTOP_LATEST_VERSION` | the version just published, e.g. `1.1.0` |
   | `DESKTOP_DOWNLOAD_URL` | the release page URL |
   | `DESKTOP_RELEASE_NOTES_URL` | optional, the notes for that version |

   These are set **only after the release is actually published** — never from
   the tag. A tag exists before anyone has decided the build is good. While
   `DESKTOP_LATEST_VERSION` is empty the endpoint answers an honest "unknown"
   and no user is prompted.
3. **Announce it**, naming three distinct downloads — Windows, macOS Apple
   Silicon, macOS Intel. macOS ships one build per architecture, deliberately
   (see `BUILD.md` §6), so an announcement that says "the Mac build" will
   generate support traffic.
4. Until code signing is in place, say plainly in the announcement that the
   installer is unsigned and what warning to expect. Training staff to click
   past a security warning without explanation is its own risk.

## 4. Retention policy

**A published GitHub release is never deleted.** Not after it is superseded,
not to tidy the list. Published release assets are the rollback inventory —
they are the only way to put a previous version back on someone's machine.

This is distinct from the 30-day `actions/upload-artifact` retention in CI,
which only covers unpublished runs. Publishing is what makes an artifact
permanent.

## 5. Withdrawing a bad release

1. **Stop the in-app prompt first.** Clear `DESKTOP_LATEST_VERSION` on the
   backend (or set it to the previous good version). The update notice stops
   recommending the bad build immediately, on every client, without shipping
   anything. This is the fastest lever available and it is why the endpoint
   reads configuration rather than the newest tag.
2. **Un-publish or clearly mark the GitHub release** so nobody downloads it.
3. **Tell affected users to install the previous version.** Both installers
   accept installing an older version over a newer one — there is no downgrade
   guard — so this works with no new code. On macOS, drag the older `Monitra.app`
   over the current one.
4. **User data is safe in both directions.** `~/.monitra` (the local database,
   the durable sync queue, the logs) lives outside the installation directory
   and is untouched by an install, an upgrade or a downgrade.
5. **Check who actually moved.** `GET /desktop/client-versions` shows the
   last-seen desktop version per user, so "did everyone come off the bad
   build" is answerable rather than assumed.
6. **Fix forward.** Cut a new patch version. Never re-publish a different build
   under a version number that has already shipped — a version must identify
   exactly one build, or every support report becomes untrustworthy.

## 6. What is still missing

Honest list, so nobody assumes otherwise:

- **Code signing.** Nothing is signed. macOS CI is wired for it and needs only
  the credentials; the Windows job has no signing step yet. Approved as a
  production-release requirement.
- **Auto-update (Phase 1).** Not built. Approved for the future as a *prompted*
  update, after Phase 0 has proven itself and signing is in place.
- **macOS on real hardware.** Every macOS build so far has been produced and
  smoke-tested in CI only. The first real-world macOS install will also be the
  first real test — the pilot ring matters more, not less, for that platform.
