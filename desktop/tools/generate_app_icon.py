"""
Generate build/monitra.ico from the same programmatic gradient checkmark
artwork the running app uses for its window/tray icon
(background_services.notifications.notification_service.create_app_icon).

Run once whenever the artwork changes, or as part of the packaging
procedure -- see desktop/BUILD.md. Requires a QApplication (QPixmap/
QPainter need one, even headless), so this is not importable as a plain
module; run it as a script.

Usage (from desktop/):
    python tools/generate_app_icon.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

from background_services.notifications.notification_service import create_app_icon

#: PySide6's QImageWriter exposes no multi-frame ICO write, only a single
#: image per file -- so this ships one high-resolution frame rather than
#: the several-sizes-in-one-file a hand-built .ico could have. Windows
#: downscales a single 256px frame cleanly for the taskbar/titlebar/
#: shortcut sizes it actually needs, and this is still a strict
#: improvement over the 64px pixmap the app icon used before this script
#: existed.
ICON_SIZE = 256

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "build" / "monitra.ico"


def main() -> None:
    app = QApplication(sys.argv)
    icon = create_app_icon(sizes=[ICON_SIZE])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    image = icon.pixmap(ICON_SIZE, ICON_SIZE).toImage()
    if not image.save(str(OUTPUT_PATH), "ico"):
        raise SystemExit(f"failed to write {OUTPUT_PATH}")

    print(f"wrote {OUTPUT_PATH} ({ICON_SIZE}px)")
    app.quit()


if __name__ == "__main__":
    main()
