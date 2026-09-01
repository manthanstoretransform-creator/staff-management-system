# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for the Monitra desktop client.

Usage (from desktop/, after `pip install pyinstaller` and
`python tools/generate_app_icon.py` -- see BUILD.md for the full,
step-by-step procedure):

    pyinstaller packaging/monitra.spec --distpath dist --workpath build/work --noconfirm

Output: dist/Monitra/Monitra.exe (plus its supporting files in the same
folder -- see BUILD.md for why this "onedir" layout is the default over a
single self-extracting .exe).

What "lightweight" means here: this app only ever imports PySide6.QtCore,
QtGui, QtWidgets, QtSvg, and QtSvgWidgets (confirmed via
`grep -rhoE "from PySide6\.[A-Za-z0-9_.]+" --include="*.py" .` from
desktop/) -- no WebEngine, Qml/Quick, Multimedia, Charts, Sql, Pdf,
Bluetooth, 3D, or any of PySide6's other ~25 submodules, each of which
ships by default and adds tens of MB. EXCLUDED_PYSIDE6_MODULES below
excludes exactly those unused modules from the build; that list is the
single biggest lever on the final size, bigger than onefile/onedir or UPX.
"""
from pathlib import Path

DESKTOP_ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 -- SPECPATH is injected by PyInstaller

APP_NAME = "Monitra"
ICON_PATH = DESKTOP_ROOT / "build" / "monitra.ico"

# Every PySide6 submodule this codebase does NOT import anywhere. Update
# this list (and the grep above) if a future change adds a genuinely new
# Qt submodule import -- an unnecessary exclude for a module nothing
# imports is harmless, but excluding one that IS used breaks the build
# loudly at import time, not silently.
EXCLUDED_PYSIDE6_MODULES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQuickControls2",
    "PySide6.QtQuick3D", "PySide6.QtQuick3DRuntimeRender",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtMultimediaQuick",
    "PySide6.QtNetwork", "PySide6.QtNetworkAuth",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtSerialBus",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic", "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs", "PySide6.QtGraphsWidgets",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtUiTools", "PySide6.QtHelp",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtStateMachine",
    "PySide6.QtTextToSpeech", "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtWebView",
    "PySide6.QtXml", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtPrintSupport",
    "PySide6.QtSpatialAudio", "PySide6.QtLocation", "PySide6.QtHttpServer",
    "PySide6.QtVirtualKeyboard", "PySide6.QtAxContainer",
]

a = Analysis(  # noqa: F821 -- injected by PyInstaller's exec environment
    [str(DESKTOP_ROOT / "main.py")],
    pathex=[str(DESKTOP_ROOT)],
    binaries=[],
    # No datas: every icon/asset this app uses is drawn in code (vendored
    # SVG path data / QPainter), not loaded from a bundled file. The one
    # genuinely external file, .env, is deliberately NOT bundled -- it is
    # read next to the .exe at runtime (see app/config.py) so a deployed
    # build can still be pointed at a different backend without a rebuild.
    datas=[],
    hiddenimports=[],
    excludes=EXCLUDED_PYSIDE6_MODULES,
    noarchive=False,
)

# `excludes` above only stops PyInstaller from following *Python* imports
# into those submodules. PySide6's own PyInstaller hook still bundles the
# underlying Qt *.dll files it thinks the app might need, independent of
# which Python wrapper modules got imported -- so Qt6Quick.dll, Qt6Qml.dll,
# Qt6Pdf.dll, and Qt6VirtualKeyboard.dll all showed up in a real build here
# despite QtQml/QtQuick/QtPdf/QtVirtualKeyboard being excluded above.
# opengl32sw.dll (Qt's software OpenGL rasterizer, ~20MB) is also pulled in
# by default; every real Windows desktop already has a hardware OpenGL/
# ANGLE driver, so the software fallback is dead weight for this app.
# These are stripped from the binary list directly -- verified by actually
# launching the resulting Monitra.exe after this filter (see BUILD.md),
# not assumed safe.
_DROP_BINARY_PREFIXES = (
    "opengl32sw",
    "Qt6Quick", "Qt6Qml",
    "Qt6Pdf",
    "Qt6VirtualKeyboard",
)
a.binaries = [
    entry for entry in a.binaries
    if not Path(entry[0]).name.startswith(_DROP_BINARY_PREFIXES)
]

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    icon=str(ICON_PATH),
    console=False,   # windowed GUI app -- no terminal window
    upx=True,        # no-op if the upx binary isn't installed; see BUILD.md
    strip=False,
)

# onedir layout: dist/Monitra/Monitra.exe + its supporting files alongside
# it in the same folder. Faster to launch than a single self-extracting
# .exe (nothing to unpack into a temp dir on every run) and no larger on
# disk -- see BUILD.md for the one-line switch to a true single-file .exe
# if a single shareable file matters more than launch speed.
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    upx=True,
    name=APP_NAME,
)
