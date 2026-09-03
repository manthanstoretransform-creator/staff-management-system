# Desktop Update & Distribution — Decision Record

**Date:** 2026-09-02
**Decided by:** project owner (projectmanager663@gmail.com)
**Covers:** the five sign-off items raised in §16 of the Desktop Application Update &
Distribution Audit, plus the §15 items that were flagged as needing no sign-off.

This file records *decisions*. The implementation status of each is tracked in the
summary table below; `docs/Desktop_Release_Runbook.md` is the procedure that came out
of it.

> **Note on the companion document:** the audit itself
> (`docs/Desktop_Update_Distribution_Audit.md`) is **not currently checked into this
> repository** — it was reviewed out-of-band. It should be committed alongside this
> record so the reasoning behind these decisions stays available.

---

## Summary

| # | Item | Decision | Status |
|---|---|---|---|
| 1 | Phase 0 — in-app "update available" notice | **Approved** | **Built.** `background_services/update/update_service.py` + `GET /desktop/latest-version` |
| 2 | Phase 1 — real auto-update | **Approved in principle, Approach B (prompted)** | Not started, deliberately — after Phase 0 is proven and signing is in place |
| 3 | Fleet version-visibility logging | **Approved** | **Built.** `User-Agent: Monitra/<version>` on every request; `GET /desktop/client-versions` |
| 4 | Windows code-signing certificate + Apple Developer Program membership | **Approved as a production-release requirement** | Procurement — no engineering work outstanding on macOS; the Windows release job still needs a `signtool` step once a certificate exists |
| 5 | macOS running-instance guard | **Approved** | **Already present** (an `flock()` in `core/single_instance.py`); it had no test, and now does |
| — | §15 process- and CI-only items | **Approved to proceed without further sign-off** | **Done:** changelog + CI gate, artifact checksums, pilot ring and retention policy written down in the release runbook |

---

## 1. Phase 0 — in-app update notification — **approved**

Build the update-notification feature. The desktop client checks for a newer published
version in a lightweight, low-frequency way and tells the user when one is available.

Constraints set by this decision:

- **No automatic download and no automatic install in Phase 0.** The notice is
  informational only, with a link the user follows themselves.
- The check must reuse the existing owners named in `CLAUDE.md` §3.1 — a `LoopService`
  for the periodic check and `background_services/notifications/` for the notice. No new
  thread, timer, or notification mechanism.
- The backend side is a small additive endpoint following the existing
  api → services → repositories layering.
- The endpoint must report the latest **published, non-flagged** release, not merely the
  latest tag, so that un-publishing a bad release actually stops the in-app prompt from
  recommending it.

## 2. Phase 1 — real auto-update — **approved for the future, not now**

Do not start Phase 1 yet. Phase 0 must be completed and proven in real pilot/production
usage first.

When Phase 1 is built, it uses **Approach B — prompted update**: the user is told an
update is available and chooses when to apply it. **Silent automatic updates are
explicitly not to be implemented initially.** Code signing (item 4) is a prerequisite —
an auto-updater that downloads and runs an unsigned installer is a worse security
posture than the manual path it replaces.

## 3. Fleet version-visibility logging — **approved**

The backend should be able to report which version of the Monitra desktop client each
active staff device is running, so that outdated clients and the spread of a bad release
are visible rather than guessed at.

Constraint set by this decision: **keep the collection minimal.** Only what is needed for
version visibility and update management — the desktop client already sends
`Monitra/<version>` in its `User-Agent`, and that is the intended source. No additional
telemetry about staff machines rides along with this change.

## 4. Code signing budget — **approved as a production-release requirement**

A Windows code-signing certificate and an Apple Developer Program membership are to be
obtained before Monitra is released to real production users. This is tracked as a
business/procurement task and **does not block current development**.

The macOS CI pipeline is already wired for signing and notarization and needs only the
credentials. The Windows release job has no signing step yet and will need one added once
a certificate exists.

## 5. macOS running-instance guard — **approved** (it already existed)

Ensure only one instance of Monitra can run at a time on macOS. If Monitra is already
running, a second copy must not start a parallel tracking instance — no duplicate timers,
activity capture, screenshot capture, or competing sync.

Note that this decision is broader than the audit's original framing: the audit asked
only about blocking an in-place `.app` replacement while the app is running. This
approval covers the general single-instance guarantee on macOS.

**On inspection, that guarantee was already implemented.** `core/single_instance.py`
takes a named mutex on Windows and an `flock()` on a file in `~/.monitra` on macOS and
Linux, and `main.py` refuses to start a second copy either way. The lock is released by
the OS on process exit, including a crash or a kill. What was missing was test coverage
of the POSIX half — `tests/test_single_instance.py` now covers it, including that
macOS routes to the flock path rather than skipping the guard.

The audit's narrower ask — refusing a drag-to-Applications replacement *while Monitra
is running*, the way the Windows installer refuses — is still not implemented; macOS
has no installer script to put such a check in. The running copy keeps its own bundle
open, so the practical effect is a copy that must be quit and reopened.

## §15 process and CI items — **approved, proceed now**

Approved to proceed without further sign-off:

- pilot / staged rollout ring before general release,
- release-retention policy (never delete a published GitHub release — it is the rollback
  inventory),
- SHA-256 checksums and file-integrity verification in the release workflow,
- a hand-written `CHANGELOG.md` and the CI check that requires an entry for the version
  being released,
- other process-only or CI-only improvements listed in §15 of the audit.

Standing constraint on all of the above: they must not modify the stability-critical
`desktop/` runtime architecture or introduce runtime risk. These are process and CI
changes only.

---

## What is left

1. **Signing credentials (item 4)** — procurement. A Windows certificate, and an Apple
   Developer Program membership. The macOS release job is already wired for signing and
   notarization and needs only the secrets; the Windows job needs a `signtool` step
   adding once a certificate exists.
2. **A macOS build on real hardware.** Every macOS artifact so far has been produced
   and smoke-tested in CI only.
3. **Phase 1 prompted auto-update (item 2)** — last, and only once 1 and 2 are done and
   Phase 0 has been proven in pilot use.

One correction to the audit worth recording: it stated that the desktop client sent
`Monitra/<version>` as its `User-Agent` on every API call and that the backend simply
did not surface it. That was not the case — `version.user_agent()` existed but nothing
called it, so no version reached the backend at all. Sending the header was part of
building item 3, not merely reading something already being sent.
