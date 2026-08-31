# Monitra Desktop — Setup & Running (Windows + macOS)

This is the from-source setup and run procedure, for either platform. For
packaging a distributable Windows `.exe`, see [BUILD.md](BUILD.md) instead
— that document doesn't apply to macOS (see its note at the bottom of
this file).

## Requirements

- **Python 3.10+**, any platform build.
- **Windows**: no extra system packages.
- **macOS**: Xcode Command Line Tools (`xcode-select --install` if not
  already present) — only needed if pip has to compile `pyobjc` from
  source rather than use a prebuilt wheel for your exact Python version;
  most common versions have one.

Every dependency is declared in [requirements.txt](requirements.txt):
PySide6, httpx, and python-dotenv install identically on both platforms;
`pyobjc-framework-Cocoa` and `pyobjc-framework-Quartz` are macOS-only and
`pip` skips them automatically on Windows (they're marked
`; sys_platform == "darwin"`) — one requirements file, no per-OS variant
needed.

## Setup

From `desktop/`:

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

**macOS (bash/zsh):**
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

**Windows:**
```powershell
.venv\Scripts\python main.py
```

**macOS:**
```bash
.venv/bin/python main.py
```

Both platforms store their local cache database and logs at
`~/.monitra/` (via `Path.home()`, so this resolves correctly on either
OS) — nothing else needs configuring for a first run. By default the app
talks to the live production backend; only if you need to point a
particular run at a different one, copy `.env.example` to `.env` in
`desktop/` and set `SMS_API_BASE_URL`.

## What's platform-specific, and what to expect on macOS

Reviewed and made cross-platform in this pass — see the code comments at
each for the full detail:

| Feature | Windows | macOS |
|---|---|---|
| Login, tasks, timer, manual time entries, sync | ✅ | ✅ |
| Activity summary (reading percentages already stored on the backend) | ✅ | ✅ |
| App-usage tracking (which application is focused) | ✅ (`tracking/active_window.py`) | ✅, via `pyobjc` (`NSWorkspace`) |
| Browser URL tracking (which site is open) | ✅ | ✅, via the same `pyobjc` window-title lookup |
| App-icon lookup for the Activity tabs | ✅ | ✅ (Qt's own cross-platform `QFileIconProvider`, plus known `/Applications/*.app` paths) |
| Windows taskbar toast identity (`set_windows_app_identity`) | ✅ | not applicable — macOS notification identity comes from the app bundle, not a runtime call |

**macOS Screen Recording permission**: the window-title half of app-usage
and URL tracking (`_macos_active_window_details` in
`tracking/active_window.py`) uses `CGWindowListCopyWindowInfo`, which only
returns real window titles once this app has been granted **Screen
Recording** permission (System Settings → Privacy & Security → Screen
Recording). Without it, the call still succeeds — it just silently omits
window names, so app-usage tracking still records *which app* was used,
but URL tracking (which needs the window/tab title to read a browser's
current page) won't see anything to parse until permission is granted.
This is a one-time, per-machine grant; the app cannot request it
automatically.

**Not verified on real macOS hardware**: the `pyobjc`-based code in
`tracking/active_window.py` was written and unit-tested against mocked
`AppKit`/`Quartz` objects (see
`tests/test_active_window_cross_platform.py`), matching the documented
pyobjc API shape, but this development environment has no macOS machine
to actually run it on. Test it for real on a Mac before relying on it,
the same way any new feature would be — if `NSWorkspace.frontmostApplication()`
or `CGWindowListCopyWindowInfo`'s exact calling convention differs from
what's coded here, this is the first place to look.

## Packaging a `.exe` (Windows) vs. a macOS build

[BUILD.md](BUILD.md) documents producing `dist/Monitra/Monitra.exe`, a
Windows-only binary — PyInstaller doesn't cross-compile, so that exact
procedure only produces a Windows build, and only when run on Windows.
`packaging/monitra.spec` is the same spec PyInstaller would use to build a
macOS `.app` bundle instead, but only if run *from* a Mac; that path is
untested here for the same reason as the tracking code above (no macOS
machine in this environment) and would need someone with mac access to
verify.
