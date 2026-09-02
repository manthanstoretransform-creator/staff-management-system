# Brand assets

Drop the Monitra logo here to use it everywhere in the desktop app — the
sidebar mark, the window icon, the system-tray icon and the packaged
`.ico`/`.icns` export.

Accepted filenames (first match wins), see `core/branding.py`:

    monitra_logo.svg
    monitra_logo.png
    monitra-logo.svg
    monitra-logo.png
    logo.svg
    logo.png

Use a square, transparent-background file — SVG for the crispest result at
every size, otherwise a PNG of at least 256×256.

With no file here the app draws the vendored vector mark
(`core/branding.MONITRA_MARK_SVG`) instead. That is a real fallback, not a
placeholder: nothing renders an empty box if the folder stays empty.
