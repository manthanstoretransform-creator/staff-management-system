# Building the Monitra desktop `.exe`

This is the packaging procedure for the PySide6 desktop client. Follow it
top to bottom the first time; after that, steps 1–2 are one-time setup and
steps 3–6 are what you repeat for every new build.

Everything here was run and verified against a real build on 2026-08-31:
a clean venv, a stripped ~77MB `dist/Monitra/` folder, and a launch of the
resulting `Monitra.exe` that reached the real dashboard against the live
backend.

---

## Why a clean virtualenv is not optional

PyInstaller bundles whatever is *importable in the environment it runs in*
if any code path references it — including inside a `try/except
ImportError`. Building from a developer machine's everyday Python
environment (which tends to accumulate unrelated packages from other
projects) silently drags those in too.

Concretely: building this app from an environment that also happened to
have `numpy`, `Pillow`, and `psutil` installed (none of which
`desktop/requirements.txt` lists, and none of which this app imports)
produced a 160MB `dist/Monitra/`. The exact same build from a venv
containing only `requirements.txt` + `pyinstaller` produced 114MB with
identical functionality. **Always build from a venv containing only this
app's own dependencies.**

## Why `.exe` size is dominated by Qt, and how this build shrinks it

`PySide6` ships ~30 Qt submodules (WebEngine, Qml/Quick, Multimedia,
Charts, Pdf, Bluetooth, 3D, SerialPort, …). This app only ever imports
five of them:

```bash
# from desktop/ -- the actual, current list this build's excludes are based on
grep -rhoE "from PySide6\.[A-Za-z0-9_.]+" --include="*.py" . | sort -u
```
```
from PySide6.QtCore
from PySide6.QtGui
from PySide6.QtSvg
from PySide6.QtSvgWidgets
from PySide6.QtWidgets
```

`packaging/monitra.spec` excludes every other PySide6 submodule
(`EXCLUDED_PYSIDE6_MODULES`). That alone took the clean-venv build from
114MB to well under it, but two more things needed a second pass:

- Excluding a *Python* module (e.g. `PySide6.QtQml`) does not stop
  PySide6's own PyInstaller hook from bundling the underlying **Qt DLL**
  it thinks the app might need. A real build here still shipped
  `Qt6Quick.dll`, `Qt6Qml.dll`, `Qt6Pdf.dll`, and
  `Qt6VirtualKeyboard.dll` despite every one of those Python modules
  being excluded.
- `opengl32sw.dll`, Qt's software OpenGL rasterizer, is ~20MB on its own
  and is dead weight on any real Windows desktop (which already has a
  hardware or ANGLE GL driver).

`packaging/monitra.spec` strips these specific `.dll` files out of
`a.binaries` directly, after `Analysis()` runs (see
`_DROP_BINARY_PREFIXES` in the spec). This took the build from 114MB to
**77MB**, verified by actually launching the result (step 5 below) rather
than assumed safe.

If a future change to this app starts genuinely using one of the excluded
Qt submodules (e.g. adding real network requests through `QtNetwork`
instead of `httpx`), **both** lists in the spec need updating, or the
build will fail loudly at import time (a missing Python module) or subtly
at runtime (a missing DLL an already-imported module needed). Re-run the
`grep` above and diff it against `EXCLUDED_PYSIDE6_MODULES` /
`_DROP_BINARY_PREFIXES` whenever `requirements.txt` or the app's Qt usage
changes.

---

## One-time setup

### 1. Create a clean build venv

From `desktop/`:

```powershell
python -m venv .venv-build
.venv-build\Scripts\pip install -r requirements.txt pyinstaller
```

`.venv-build/` is covered by its own `.gitignore` entry — if you name it
something else, add that name too; a build venv must never be committed.

### 2. Icon

`build/monitra.ico` is a generated artifact (`build/` is gitignored) —
regenerate it once, and again any time the in-app icon artwork in
`background_services/notifications/notification_service.py`
(`_paint_app_icon`) changes:

```powershell
.venv-build\Scripts\python tools\generate_app_icon.py
```

This renders the exact same programmatic gradient-checkmark artwork the
running app uses for its window/tray icon, at 256px, into
`build/monitra.ico`.

---

## Every build

### 3. Build

From `desktop/`:

```powershell
.venv-build\Scripts\pyinstaller packaging\monitra.spec --distpath dist --workpath build\work --noconfirm
```

Output: `dist/Monitra/Monitra.exe` plus its supporting files in
`dist/Monitra/_internal/`. Both `dist/` and `build/` are gitignored —
nothing here belongs in version control; this whole procedure exists so
the build is reproducible from source instead.

### 4. Place `.env` next to the `.exe` (only if you need to override the backend)

`app/config.py` looks for `.env` next to the running executable (it
checks `sys.frozen` and resolves relative to `sys.executable` when
frozen, `__file__` otherwise — this only matters for a packaged build;
running from source is unaffected). Without one, the app defaults to the
live production backend (`LIVE_API_BASE_URL` in `app/config.py`), which is
correct for a normal staff install. Only copy a `.env` next to
`Monitra.exe` if this particular build needs to point at a different
backend (e.g. `SMS_API_BASE_URL=http://localhost:8000` for internal
testing):

```powershell
copy .env dist\Monitra\.env
```

### 5. Verify — launch it

Don't ship a build you haven't actually run:

```powershell
dist\Monitra\Monitra.exe
```

Confirm the window opens, the icon shows correctly in the titlebar and
taskbar, login/dashboard render, and (if you have a test account) the
task list and timer work. Close it before the next step.

### 6. Distribute

Zip the whole `dist/Monitra/` folder (not just the `.exe` — it needs
`_internal/` alongside it) and share that. `Monitra.exe` inside is the
one users double-click; nothing else in the folder needs explaining to
them.

---

## Troubleshooting

- **Antivirus flags the `.exe` / SmartScreen blocks it on first run.**
  Expected for an unsigned PyInstaller build — this procedure does not
  cover code-signing. If distribution needs to avoid the SmartScreen
  prompt, that requires a purchased code-signing certificate and
  `signtool.exe`, out of scope here.
- **Build succeeds but the `.exe` fails to launch, or launches with a
  missing-DLL error.** Almost always `_DROP_BINARY_PREFIXES` in
  `packaging/monitra.spec` dropped something actually needed after an app
  change. Remove the newest addition to that list, rebuild, and retest;
  narrow it down entry by entry rather than reverting the whole list.
- **Build is much larger than ~80MB again.** You built from an
  environment with extra packages installed — rebuild from a clean venv
  (step 1).
- **Want a single shareable `.exe` file instead of a folder** (slower to
  launch — everything unpacks to a temp dir on every run — but easier to
  email/share as one file): in `packaging/monitra.spec`, remove
  `exclude_binaries=True` from the `EXE(...)` call, add `a.binaries,
  a.datas,` as extra positional arguments to that same `EXE(...)` call
  (matching what `COLLECT(...)` currently passes), and delete the
  `COLLECT(...)` block entirely. PyInstaller's own docs cover this
  onefile-vs-onedir spec shape in more detail if needed.
- **A future Python upgrade breaks the build.** PyInstaller pins
  Windows-64bit-intel bootloaders per Python version; if `pip install
  pyinstaller` in the new venv doesn't have one for the new interpreter,
  wait for a PyInstaller release that does, or build with the previous
  Python version in the meantime.
