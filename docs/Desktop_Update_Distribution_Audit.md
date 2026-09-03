# Desktop Application Update & Distribution Audit

**Scope:** Monitra desktop client (`desktop/`) — Windows and macOS.
**Purpose:** a single, repeatable procedure for shipping updates to staff who
already have Monitra installed, plus an honest audit of what already exists
in this repository versus what is still missing.
**Status:** audit + procedure document. No application code was changed to
produce this; recommendations that would touch `desktop/` runtime code are
flagged for explicit sign-off per `CLAUDE.md` §3 before anyone implements
them.

**Companion documents** — this file is the *process* layer; the *mechanics*
already exist and are documented in detail in:
- `desktop/BUILD.md` — how to actually build each artifact, prerequisites,
  troubleshooting.
- `desktop/version.py` — the single source of truth for the version number.
- `.github/workflows/desktop-release.yml` — the build/package/release CI job.
- `.github/workflows/desktop-stability.yml` — the correctness gate (tests +
  architecture checker) that runs on every push.

Nothing below duplicates BUILD.md's build instructions; it references them
and adds the process this repo does not yet have written down: what to do
*around* a build when real users already have a prior version installed.

---

## 1. Executive summary

**The packaging and CI machinery for shipping a Monitra release already
exists and is more complete than a typical first pass** — versioning has one
source of truth, both installers upgrade in place, user data is
provably kept outside the install directory (so an upgrade cannot destroy
unsynced tracked time), and CI builds, tests, smoke-tests and drafts a
release automatically from a git tag.

**What is genuinely missing, confirmed by reading the code rather than
assumed:**

| Gap | Current state | Risk if unaddressed |
|---|---|---|
| Auto-update | None. `BUILD.md` §17 states this explicitly. | Every update is a manual re-download; adoption lags, old clients linger. |
| Code signing | All artifacts unsigned (`BUILD.md` §11). | SmartScreen/Gatekeeper warnings train staff to click through security prompts. |
| Staged/pilot rollout | No process exists; releases go from CI to a single GitHub draft release. | A bad build reaches everyone at once. |
| Fleet visibility | Nothing records which version each installed client is running. | Support cannot tell who is out of date; no way to know a bad release is spreading before users report it. |
| Rollback runbook | Not written down. Artifact retention is 30 days (CI default). | A bad release is hard to walk back once CI artifacts expire. |
| Checksums | Not generated or published. | Users/IT cannot verify a downloaded installer wasn't tampered with or corrupted. |
| Changelog | No `CHANGELOG.md` anywhere in the repo. | Release notes are auto-generated from commit titles only (`generate_release_notes: true`), which is not the same as a curated "what changed for you" note. |
| macOS on real hardware | Never built or run on physical hardware — `BUILD.md` §17 states this. | The macOS release path is exercised only in CI; the first real-world macOS install is also the first real test. |

This document turns those into a procedure with explicit owners and gates,
and lists what still needs a decision from you before it gets built (§16).

---

## 2. Versioning strategy

Already implemented and correct — this section documents it, it does not
propose it.

- **Single source of truth:** `desktop/version.py`, `VERSION = "1.0.0"`.
  Every artifact (the .exe's VERSIONINFO resource, the Windows installer,
  the macOS `Info.plist`, the DMG volume name, the artifact filenames, the
  Qt app object, the window title, and the `User-Agent` header the desktop
  client sends on every API call) reads from this one constant.
  `desktop/tests/test_packaging.py` fails the build if any of those places
  hardcodes a version literal instead — so two artifacts disagreeing about
  their own version is a caught bug, not a possible support incident.
- **Format:** plain `major.minor.patch`, no suffix. This is a hard
  constraint, not a style choice — Windows' `VERSIONINFO` resource and
  macOS' `CFBundleVersion` both require numeric-only components. Recommended
  convention going forward, standard semver semantics:
  - **patch** (`1.0.0` → `1.0.1`) — bug fixes, no behavior or schema change
    a user would need to know about.
  - **minor** (`1.0.x` → `1.1.0`) — new features, additive backend/desktop
    contract changes, non-breaking.
  - **major** (`1.x.x` → `2.0.0`) — breaking change to the desktop↔backend
    contract, a data-directory migration, or a change requiring every user
    to re-grant a permission (e.g. changing `BUNDLE_ID`, which `version.py`
    already documents as "treat as fixed" for exactly this reason).
- **Git tag convention:** `v<version>` (e.g. `v1.0.1`), matching what
  `desktop-release.yml` already triggers on (`push: tags: ["v*"]`).
- **Pre-release identity** (rc/beta builds) belongs in the *artifact
  filename* the build scripts derive, never in `VERSION` itself — `BUILD.md`
  §10 already states this constraint; there is currently no scripted way to
  produce an rc build, which is a gap addressed in §11 below.

---

## 3. Packaging the updated application

This is fully built and documented — see `desktop/BUILD.md` §§1–6 for the
authoritative, step-by-step instructions. Summary of what each platform
produces:

| Platform | Artifact | Built by | Requires |
|---|---|---|---|
| Windows | `Monitra-Setup-<version>.exe` (installer) | `scripts/build_installer.ps1` | Inno Setup 6 |
| Windows | `Monitra-Portable-<version>.zip` (no install) | `scripts/build_portable.ps1` | — |
| macOS | `Monitra-macOS-<arch>-<version>.dmg` (×2, arm64 + x86_64) | `scripts/build_macos.sh` | must run on macOS |

Both platforms build from the same `packaging/monitra.spec` (PyInstaller,
onedir). Neither requires the end user to have Python installed — everything
needed is inside the package. This has not changed and needs no rework; the
only genuine action item here is **code signing** (§7) before any of this
goes to staff outside the team that builds it.

---

## 4. Distributing updates to existing users

### 4.1 What already works today (manual distribution)

Both installers **upgrade in place** — this is deliberate, existing
behavior, not something to build:

- **Windows:** the Inno Setup script (`packaging/windows/monitra.iss`) pins
  `AppId` to a fixed GUID that must never change. Running a newer
  `Monitra-Setup-<version>.exe` over an existing install replaces it rather
  than installing a second, parallel copy. The installer refuses to run
  while Monitra is running (it checks the same named mutex
  `core/single_instance.py` uses), so a staff member has to quit the tray
  app first — this is intentional friction, not a bug, because a running
  process holds its own `.exe` and DLLs open.
- **macOS:** the DMG is a drag-to-Applications layout. Dragging a new
  `Monitra.app` over the old one in `/Applications` replaces it. There is no
  installer script enforcing this — it's the standard macOS convention —
  which also means there is no automated *refusal* if Monitra is running
  during the drag, unlike Windows. This is a real, currently-undocumented
  gap: recommend adding a same-pattern running-instance check to
  `scripts/build_macos.sh`'s DMG or to a first-run check in `main.py`,
  flagged in §16 for sign-off since it touches startup behavior.
- **User data survives an upgrade on both platforms.** This is the
  precondition that makes any update story safe at all:
  `core/paths.py` resolves the writable data directory to `~/.monitra`
  (or `<portable dir>/data`), which is **never** inside the installation
  directory. The installer/DMG replace the installation directory wholesale;
  they never touch `~/.monitra`. `cache.db` (tracked time, the durable sync
  queue) and `logs/` are therefore untouched by an update. This is verified
  by `tests/test_packaging.py` and exercised in the clean-machine checklist
  (`BUILD.md` §14 — "Reinstall over the top: existing local data still
  present").

### 4.2 How staff actually get the new installer today

There is a GitHub Releases draft with the artifacts attached
(`desktop-release.yml`'s `release` job). Today, "distributing an update"
means: a human publishes the draft release, and every staff member has to
notice a new release exists and manually download and run the installer.
**There is no notification path inside the app telling a user an update is
available.** That is the single highest-leverage gap to close before
auto-update, and it's cheap:

**Recommended near-term addition (Phase 0, before real auto-update):**
an in-app, passive version check — on startup (or on a low-frequency timer,
reusing the existing `LoopService` pattern already owned by
`background_services/`), the desktop client calls a backend endpoint that
returns the latest published version, compares it to `version.VERSION`, and
if newer, shows a dismissible notification via the existing
`background_services/notifications/` owner ("A new version of Monitra is
available — download it from <link>"). No download, no install, no
elevation — just visibility. This requires:
- one new, trivial backend endpoint (e.g. `GET /desktop/latest-version`)
  returning `{"version": "1.2.0", "download_url": "..."}`, sourced from
  GitHub Releases or a value the release process sets — a services/
  repository/route addition following the existing api → services →
  repositories layering,
- one new desktop background check reusing `LoopService` and
  `BackgroundApi`/notifications — no new thread, no new timer mechanism,
  going through the owners CLAUDE.md §3.1 already defines.

This is a scoped, low-risk feature. **It is still a decision for you to
approve before anyone builds it** — see §16, item 1.

### 4.3 Real auto-update (Phase 1 — do we build this at all?)

Genuine auto-update (the app downloads and installs a new version itself,
with no staff action beyond "click restart when ready") is **not
implemented and not started**. It is a materially bigger commitment than
Phase 0, and it is exactly the kind of change CLAUDE.md §3 says to stop and
ask about before touching, because it adds new background behavior
(download, verify, silently invoke an installer) to a stability-critical
runtime. Two credible approaches, for you to choose between if you want this
built at all:

| Approach | Windows | macOS | Effort | Notes |
|---|---|---|---|---|
| **A. Squirrel-style silent update** | [Squirrel.Windows](https://github.com/Squirrel/Squirrel.Windows) or a hand-rolled "download installer, run it silently, relaunch" flow | [Sparkle](https://sparkle-project.org/) (the de facto standard for non-Mac-App-Store apps) | High | Real "no click" auto-update; both tools want their own signing/manifest format (an "appcast" for Sparkle) — this is new infrastructure, not an extension of the existing installer. |
| **B. Prompted self-update** | App detects a new version (Phase 0's check), downloads the new `Setup.exe` to a temp path, and launches it (still requires the running instance to quit — same constraint the manual installer already enforces) | App detects a new version, downloads the new `.dmg`, and opens it in Finder for the user to drag over — *not* a silent replace, because macOS offers no unprivileged way to replace a running `.app` from inside itself as cleanly as Sparkle's own relauncher does | Medium | Reuses the existing installer/DMG artifacts unchanged; no new signing pipeline; still requires one click from the user ("Restart to update"). |

**Recommendation: build Phase 0 now (cheap, safe, immediately useful);
defer Phase 1 until code signing (§7) is in place.** An auto-updater that
silently downloads and runs an *unsigned* installer is a worse security
posture than what exists today — it teaches the OS-level warning to be
ignored programmatically, and it's a real supply-chain risk if the download
channel (wherever "latest version" is served from) is ever compromised.
Signing is the prerequisite, not an optional hardening step, for Phase 1.

---

## 5. Windows — end-to-end update handling

1. Release process (§8) produces a signed (once §7 is done) or unsigned
   `Monitra-Setup-<version>.exe`.
2. Staff either sees the Phase 0 in-app notice (once built) or is told
   directly (Slack/email) that a release is out.
3. Staff downloads and runs the new installer. It:
   - refuses to proceed if Monitra is running (existing `InitializeSetup`
     check in `monitra.iss`, backed by the same named mutex the app itself
     takes),
   - installs to the same `%LOCALAPPDATA%\Programs\Monitra`, no admin rights
     needed (`PrivilegesRequired=lowest` — deliberate, documented in
     `monitra.iss`),
   - replaces the previous `_internal\` tree (`[UninstallDelete]` +
     `ignoreversion recursesubdirs createallsubdirs` in `[Files]`),
   - leaves `%USERPROFILE%\.monitra` (the database, sync queue, logs)
     completely untouched.
4. First launch after update: the app starts normally against the same
   data directory: tracked time and the pending sync queue are exactly as
   they were before the update.

No portable-build update story exists beyond "download the new zip and
replace the folder" — acceptable for a niche distribution path, not the
primary one; not worth automating unless portable becomes a primary
deployment method.

---

## 6. macOS — end-to-end update handling

1. Release process (§8) produces (once real hardware is used, §7/§13 gap)
   two signed+notarized `.dmg`s, one per architecture.
2. Staff is told a release is out (same notice path as Windows, once Phase 0
   exists).
3. Staff downloads the DMG matching their Mac's architecture, opens it, and
   drags `Monitra.app` onto `/Applications`, replacing the old bundle.
   **There is currently no check preventing this while Monitra is running**
   (§4.1) — flag to staff in the release note until that gap is closed.
4. `~/.monitra` is untouched, for the same reason as Windows (§4.1).
5. **Permissions are not re-requested on a normal update.** `BUNDLE_ID`
   (`com.monitra.desktop`) is fixed specifically so TCC (Screen
   Recording / Input Monitoring) grants survive an update — `version.py`
   documents this and calls changing it a breaking change requiring
   everyone to re-grant permissions (which is why it belongs in the
   "major version" bucket in §2 if it ever has to change).

**Distribution split by architecture is a real, deliberate limitation**,
not an oversight: `BUILD.md` §6 explains why this project ships
`arm64`/`x86_64` separately instead of a `universal2` binary (PySide6 ships
per-architecture wheels; an untested "universal" claim would be exactly the
kind of unverified claim this project's rules forbid). **This means every
release note or download page must tell an Apple Silicon Mac from an Intel
Mac apart** — a real support cost worth being explicit about in the release
announcement template (§9).

---

## 7. Code signing and security requirements

**Current state: nothing is signed. This is the single largest blocker to
distributing outside the immediate engineering team**, and is called out as
such in `BUILD.md` §11 and §17.

### Windows
- Needs a code-signing certificate. An **EV (Extended Validation)**
  certificate gets Microsoft SmartScreen reputation immediately; an
  **OV (Organization Validation)** certificate is cheaper but accumulates
  SmartScreen reputation slowly, based on download volume — meaning early
  OV-signed releases can still warn.
- Both `Monitra.exe` *and* the installer must be signed (two separate
  `signtool sign` invocations — `BUILD.md` §11 has the exact commands).
- Timestamping (`/tr http://timestamp.digicert.com`) is not optional —
  without it, every signature stops validating the day the certificate
  expires, silently re-breaking every previously-shipped installer's
  perceived trust.
- CI is already wired for this via secrets the workflow reads
  (`MACOS_CERTIFICATE*` exist for macOS; **Windows signing secrets are not
  yet wired into `desktop-release.yml`** — the Windows job in that workflow
  has no signing step at all today. That's a gap: add a `signtool`
  step analogous to the macOS "Import signing certificate" step once a
  Windows certificate exists.)

### macOS
- Needs an Apple Developer ID Application certificate (Apple Developer
  Program membership, $99/year) plus notarization credentials
  (`xcrun notarytool store-credentials`).
- `scripts/build_macos.sh` and `desktop-release.yml`'s `macos` job are
  **already fully wired** for this — signing, hardened runtime, and
  notarization all happen automatically the moment these repository secrets
  are populated: `MACOS_CERTIFICATE`, `MACOS_CERTIFICATE_PASSWORD`,
  `MACOS_KEYCHAIN_PASSWORD`, `MACOS_CODESIGN_IDENTITY`,
  `MACOS_NOTARY_PROFILE`. No code work is needed here — only obtaining and
  adding the credentials.
- `packaging/macos/entitlements.plist` is deliberately minimal (library
  validation disabled — the one entitlement a PyInstaller bundle cannot
  launch without; no `allow-jit`; App Sandbox not used because it would
  silently break the global input-monitoring this app exists to do). This
  reasoning is already documented in `BUILD.md` §11 and should not be
  revisited casually — it reflects a real constraint, not an oversight.

### Checksums (gap — not currently produced)
Neither build produces a published SHA-256 checksum. **Recommend adding
this to the release job**: after each artifact is built, compute its
SHA-256 and either publish a `.sha256` sidecar file alongside it in the
GitHub release, or list checksums directly in the release body. This is a
few lines in `desktop-release.yml` (`Get-FileHash` on Windows,
`shasum -a 256` on macOS) with no risk to the runtime — safe to add without
further sign-off, since it only touches CI, not `desktop/` application code.

### Secrets hygiene
All of the above are GitHub Actions repository secrets already, consistent
with CLAUDE.md §2 rule 6 (never commit secrets). No certificate, password,
or notary profile should ever be added to a file in this repository —
confirm this stays true as Windows signing is wired up.

---

## 8. Release / build process (the runbook)

This is the procedure to actually follow when cutting a release. It merges
`BUILD.md` §12 with the verification gates from CLAUDE.md §6, made explicit
as a checklist:

1. **Decide the version bump** per §2's semver rules. Edit
   `desktop/version.py` (`VERSION = "..."`). Commit on a branch, not
   directly to `main`.
2. **Write release notes.** See §9's changelog gap — until a real
   `CHANGELOG.md` exists, write a short "what changed for you" summary by
   hand (not just the auto-generated commit list) covering user-visible
   changes, especially anything from CLAUDE.md §5's "known open items" list
   moving from unimplemented to implemented.
3. **Run the full local verification gate** (from `desktop/`, per
   CLAUDE.md §6 and `BUILD.md` §13):
   ```bash
   python -m pytest tests/ -q
   python tools/check_architecture.py
   python tests/soak/run_launch_cycles.py --cycles 10
   python tests/soak/run_soak.py --duration 60
   ```
   All four must pass before tagging. This is not new — it is the existing
   Definition of Done, restated here because a release is exactly the
   moment it matters most.
4. **Merge to `main`**, then tag: `git tag v<version> && git push origin v<version>`.
5. **CI takes over** (`desktop-release.yml`): builds Windows + both macOS
   architectures, **re-running tests and the architecture check on each
   platform** (not trusting the local run — a green Ubuntu/local run does
   not prove a Windows package works, per that workflow's own header
   comment), then smoke-tests each packaged binary for real
   (`scripts/smoke_test_package.ps1`/`.sh`).
6. **A draft GitHub release is opened automatically** with all artifacts
   attached. Nothing is public yet.
7. **Pilot rollout** (§10) — before publishing the draft to everyone,
   install the actual built artifacts (not a local build — the CI output)
   on a small group and run the clean-machine checklist (`BUILD.md` §14).
8. **Publish the release** once the pilot signs off. This is the point
   staff can be told an update exists (today: manually; once Phase 0 exists,
   in-app).
9. **Announce**, using the architecture-split template from §6 (Windows /
   Apple Silicon / Intel — three distinct downloads, say so explicitly).

---

## 9. Update / rollback procedure

**No rollback runbook exists today.** Because both installers only ever
*upgrade forward* (neither installer nor the DMG process checks whether the
version being installed is older than what's present), rollback is
mechanically possible but operationally undocumented. Recommended procedure:

1. **Detect the bad release fast.** This depends on §11 (fleet visibility)
   existing — without it, the earliest signal is user reports. Until that
   exists, treat the pilot ring (§10) as the primary defense, not
   after-the-fact rollback.
2. **Stop the bleed.** Un-publish (or edit to "known issue" in the title of)
   the GitHub release immediately so no one downloads it going forward.
   The in-app Phase 0 update check (§4.2), once it exists, must point at
   "latest **published**, non-flagged" release, not merely "latest tag" —
   otherwise unpublishing the release does not stop the in-app prompt from
   recommending it.
3. **Give affected users the previous installer.** This requires the
   *previous* release's artifacts to still be reachable — GitHub Releases
   keeps published release assets indefinitely (this is **different** from
   the 30-day `actions/upload-artifact` retention window in the CI job,
   which only covers *draft/unpublished* runs). **Action item:** once a
   release is published, never delete it from GitHub Releases, even after
   superseding it — treat every published release as permanent rollback
   inventory. Rolling back is then: staff downloads the prior version's
   `Monitra-Setup-<version>.exe` (Windows) or `.dmg` (macOS) and installs it
   over the current one — both installers accept installing an older
   version over a newer one today (`monitra.iss` has no version-downgrade
   guard), so this works mechanically without any new code.
4. **Data is never at risk during a rollback**, for the same reason an
   upgrade is safe (§4.1) — `~/.monitra` is untouched by either direction.
5. **Fix forward.** Cut a new patch version once the root cause is fixed;
   do not re-publish the same version number under a new build — a version
   number must always identify one build, or support reports become
   untrustworthy (this is the exact reasoning `version.py`'s docstring
   already gives for why the number is a single source of truth).

---

## 10. Testing an update before releasing it to the entire team

Three existing/needed rings, from cheapest to most expensive:

**Ring 0 — automated, already exists, every release:**
`desktop-stability.yml` (every push) + `desktop-release.yml`'s per-platform
test/architecture/smoke-test steps. No action needed here; keep it green.

**Ring 1 — manual clean-machine checklist, already exists, currently
optional:** `BUILD.md` §14's full checklist (installer without admin rights,
correct version metadata, login, tracking, offline/reconnect, uninstall,
reinstall, sleep/wake, force-kill recovery, macOS permission grant/deny
behavior). **Recommend making this checklist a mandatory, signed-off step
before Ring 2**, not an optional nice-to-have — it is the only place that
would catch "the installed app doesn't sync" before real users do.

**Ring 2 — pilot/canary rollout (gap — does not exist as a process today):**
Before publishing a release to the whole team, install the actual CI-built
artifacts (not a local rebuild) on a small, named group — recommend the
engineering team itself plus one or two non-technical volunteers per OS
(so at least one Windows and one macOS pilot user who is *not* the person
who built the release) — and run it for a defined soak period (recommend at
least one full working day, covering a real start-of-day login, a normal
work session, and a normal end-of-day shutdown) before wider publication.
This ring is the actual answer to "how do we test before releasing to the
entire team" — nothing like it exists in this repo today, and it is the
single most valuable process gap to close, because it is pure process (a
checklist and a "wait a day" rule), not code.

**Ring 3 — general availability:** publish the draft release, announce.

---

## 11. Managing already-installed versions across the team (fleet visibility)

**Nothing today records which version a given installed client is
running**, beyond the `User-Agent` header
(`Monitra/<version>`, from `version.user_agent()`) sent on every API
request — which the backend receives but does not currently log or surface
anywhere queryable (confirmed: no backend code stores or reports on this
header today).

**Recommended addition**, scoped small: have the backend log (or store,
keyed by user/org) the `User-Agent` on desktop-authenticated requests, and
add a simple internal view (could be as small as a query against existing
request logs, or a dedicated small table if this needs to be queryable
later) showing "last-seen version per user." This is what makes questions
like "did everyone actually update off the bad 1.2.0 build" and "is anyone
still on a version old enough to be missing the activity-tracking feature"
answerable instead of guessed at. This is a backend-only, additive change —
still needs your sign-off per CLAUDE.md before building (§16, item 3), but
it carries materially less risk than anything touching `desktop/` runtime
code, since it's read-only telemetry on an existing header.

Until that exists, the only way to know who's on what version is to ask.

---

## 12. Required CI/CD pipeline

**Already exists and is well-structured** — two workflows, correctly
separated by purpose:

- **`.github/workflows/desktop-stability.yml`** — correctness gate.
  Runs on every push/PR touching `desktop/`: architecture boundary check +
  full regression suite (headless Qt on Ubuntu). This is the fast,
  always-on guard rail; it is not a release mechanism.
- **`.github/workflows/desktop-release.yml`** — the release pipeline.
  Triggered by a `v*` tag or manual dispatch. Per platform: install deps →
  re-run architecture check + tests **on that platform** → build → (macOS
  only) sign + notarize if secrets are present → smoke-test the actual
  packaged binary → upload artifacts. A final `release` job downloads all
  platform artifacts and opens a **draft** GitHub release with a
  pre-written per-platform download table — a human still has to publish
  it, which is correct and should stay that way (Ring 2/3 in §10 depend on
  that gate existing).

**Recommended additions to the pipeline** (each is small, isolated, and
does not touch `desktop/` application code — see §16 for which need
sign-off regardless):

1. Add a Windows signing step to the `windows` job, mirroring the macOS
   `Import signing certificate` step, once a Windows certificate exists
   (§7).
2. Add a checksum-generation step to both platform jobs, publishing
   `.sha256` sidecars alongside each artifact (§7).
3. Add a "changelog required" check — fail the `release` job (or a
   pre-tag PR check) if `CHANGELOG.md` (§13) has no entry for the version
   in `version.py`, so a release can never ship without a human-written
   note.
4. Consider extending retention beyond `actions/upload-artifact`'s 30-day
   default for the pre-publish artifacts (`retention-days: 30` in the
   workflow) — not strictly required since *published* GitHub Releases are
   permanent (§9), but relevant if the pilot ring (§10) ever needs to
   inspect a specific CI run's artifacts more than a month later.

---

## 13. Required artifacts per release — checklist

| Artifact | Exists today? | Produced by |
|---|---|---|
| `Monitra-Setup-<version>.exe` (Windows installer) | Yes | `scripts/build_installer.ps1` / CI `windows` job |
| `Monitra-Portable-<version>.zip` | Yes | `scripts/build_portable.ps1` / CI `windows` job |
| `Monitra-macOS-arm64-<version>.dmg` | Yes (never run on real hardware — §17 in BUILD.md) | `scripts/build_macos.sh` / CI `macos` job (macos-14) |
| `Monitra-macOS-x86_64-<version>.dmg` | Yes (same caveat) | `scripts/build_macos.sh` / CI `macos` job (macos-13) |
| Release notes | Partial — auto-generated commit list only | `desktop-release.yml`'s `release` job body |
| Curated changelog entry | **Missing** | recommend `desktop/CHANGELOG.md`, hand-written per release |
| SHA-256 checksums | **Missing** | recommend adding to CI (§7, §12) |
| Signed artifacts | **Missing** (macOS pipeline ready, needs credentials; Windows pipeline not yet wired) | §7 |
| Update/config manifest (for Phase 0/1 auto-update) | **Missing** — does not apply until §4.2/§4.3 is built | future |
| This audit / deployment runbook | This document | `docs/Desktop_Update_Distribution_Audit.md` |
| Build/packaging reference | Yes | `desktop/BUILD.md` |

---

## 14. Recommended repository / release structure

**Mostly already correct** — documenting the convention so it stays
consistent as the team grows:

```
desktop/
├── version.py                 # single source of truth for version/identity
├── packaging/
│   ├── monitra.spec           # PyInstaller spec (both platforms)
│   ├── windows/monitra.iss    # Inno Setup installer script
│   └── macos/entitlements.plist
├── scripts/
│   ├── build_windows.ps1      # → dist/Monitra/
│   ├── build_installer.ps1    # → dist/installer/Monitra-Setup-*.exe
│   ├── build_portable.ps1     # → dist/Monitra-Portable-*.zip
│   ├── build_macos.sh         # → dist/Monitra.app, dist/Monitra-macOS-*.dmg
│   ├── smoke_test_package.ps1
│   └── smoke_test_package.sh
├── BUILD.md                   # how to build — mechanics
├── dist/, build/               # gitignored — never commit build output
└── CHANGELOG.md                # recommended addition, see below

.github/workflows/
├── desktop-stability.yml      # correctness gate, every push
└── desktop-release.yml        # tag-triggered build + draft release

docs/
└── Desktop_Update_Distribution_Audit.md   # this file — process layer
```

**Where binaries live: GitHub Releases, never git.** This is already the
convention (`dist/` and `build/` are gitignored) and should stay that way —
release binaries are large, regenerable, and would bloat the repository
with no benefit; GitHub Releases already gives permanent, versioned,
publicly-linkable storage for exactly this purpose (§9's rollback procedure
depends on this).

**Recommended addition: `desktop/CHANGELOG.md`**, one entry per version,
written by hand at release time (§8 step 2), in the common
"Keep a Changelog" style (`### Added` / `### Changed` / `### Fixed` per
version heading). This becomes both the source for a better release-note
body and the CI gate described in §12, item 3.

---

## 15. Gap summary — prioritized action items

Ordered by leverage (impact vs. effort), not by section number:

1. **Pilot/canary ring before general release** (§10, Ring 2). Pure
   process, zero code. Highest leverage, lowest cost — start doing this on
   the next release regardless of anything else in this document.
2. **Never delete a published GitHub release** (§9). A one-line policy
   change with no engineering cost, and it's the entire rollback story.
3. **Checksums in CI** (§7, §12). A few lines in the existing workflow, no
   application-code risk.
4. **`CHANGELOG.md` + changelog-required CI check** (§13, §12). Process +
   a small CI addition.
5. **Windows code signing** (§7). Requires purchasing a certificate — a
   budget/vendor decision, not an engineering one, but blocks the credible
   removal of SmartScreen warnings.
6. **macOS code signing & notarization** (§7). Requires an Apple Developer
   Program membership — the CI pipeline is already built for this; only the
   credentials are missing.
7. **Phase 0 in-app "update available" notice** (§4.2). Small, scoped
   backend + desktop change, reuses existing owners — needs sign-off
   (§16) but is the cheapest way to close the "how do users even find out"
   gap.
8. **Fleet version visibility** (§11). Backend-only, additive — needs
   sign-off (§16) but is low-risk.
9. **A real macOS build on physical hardware** (§14 in `BUILD.md`). Needed
   before any macOS release is called "verified" rather than "should work
   per CI."
10. **Phase 1 real auto-update** (§4.3). Largest effort, most architectural
    risk to the stability-critical runtime — do this last, and only after
    signing (item 5/6) is in place.

---

## 16. Decisions needed from you before anything here gets built

Per CLAUDE.md §7, these are flagged rather than started, because each
either touches the stability-critical `desktop/` runtime, costs money, or
changes user-facing behavior:

1. **Build the Phase 0 in-app update-notice feature (§4.2)?** Small
   backend endpoint + a `LoopService`-based check in `desktop/`. Low risk,
   but it is new runtime behavior in the stability-critical zone.
2. **Pursue real auto-update (Phase 1, §4.3) at all, and if so, which
   approach (A or B)?** This is the biggest-effort item in the whole audit
   and deserves an explicit go/no-go rather than being assumed.
3. **Build fleet version-visibility logging (§11)?** Backend-only, but it's
   new data collection about staff machines — worth an explicit decision
   even though the risk is low.
4. **Approve budget for a Windows code-signing certificate and an Apple
   Developer Program membership (§7)?** Not an engineering decision.
5. **Add a running-instance guard to the macOS update path (§4.1/§6)?**
   Currently nothing stops a staff member from dragging a new `.app` over a
   running one; worth deciding whether this is worth building given macOS
   hasn't shipped to a real user yet regardless.

Everything else in §15 (pilot ring, release-retention policy, checksums,
changelog) is process or CI-only and can proceed without further sign-off —
none of it touches `desktop/` application code or its architecture.
