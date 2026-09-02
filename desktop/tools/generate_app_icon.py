"""
Generate the platform icon files for the packaged application, from the same
programmatic gradient-checkmark artwork the running app already uses for its
window and tray icon
(background_services.notifications.notification_service.create_app_icon).

Outputs (all into build/, which is gitignored — these are build artifacts,
regenerated from source rather than committed):

    build/monitra.ico      Windows: multi-size .ico for the .exe, the
                           installer, Start Menu, taskbar and Explorer.
    build/monitra.icns     macOS: the .app bundle icon, used in Finder,
                           the Dock, and the DMG.
    build/icon_<n>.png     The individual rendered frames, kept because the
                           DMG background/volume tooling and any future
                           store listing want plain PNGs.

Run once, and again any time `_paint_app_icon` changes. Requires a
QApplication (QPixmap/QPainter need one, even headless), so this is a script
rather than an importable module.

Usage (from desktop/):
    python tools/generate_app_icon.py

Why the file formats are assembled by hand here:

PySide6's QImageWriter exposes no multi-frame ICO writer (only one image per
file) and has no ICNS writer at all. Both formats are, however, trivial
containers around PNG data on every OS version this project supports —
Windows has accepted PNG-compressed frames inside .ico since Vista, and
macOS' .icns has had PNG-based `ic##` block types since 10.7. So each frame
is rendered with Qt, encoded as PNG by Qt, and the few dozen bytes of
container header are written here. That avoids adding Pillow purely as a
build-time dependency, and keeps `requirements.txt` the single, honest list
of what this app needs.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from background_services.notifications.notification_service import (  # noqa: E402
    create_app_icon,
)

BUILD_DIR = Path(__file__).resolve().parent.parent / "build"

#: Frames rendered once and reused by both containers.
SIZES = [16, 32, 48, 64, 128, 256, 512, 1024]

#: Sizes that go into the .ico. Windows never needs more than 256 (the
#: largest size Explorer's "extra large icons" view uses), and every entry
#: past that is dead weight in the .exe.
ICO_SIZES = [16, 32, 48, 64, 128, 256]

#: macOS .icns block types, mapped to the pixel size each one must contain.
#: The `@2x` retina variants are separate block types carrying the same
#: pixels as their larger single-density sibling -- that duplication is how
#: the format works, not a mistake.
ICNS_TYPES: Dict[bytes, int] = {
    b"icp4": 16,     # 16x16
    b"icp5": 32,     # 32x32
    b"ic11": 32,     # 16x16@2x
    b"ic12": 64,     # 32x32@2x
    b"ic07": 128,    # 128x128
    b"ic13": 256,    # 128x128@2x
    b"ic08": 256,    # 256x256
    b"ic14": 512,    # 256x256@2x
    b"ic09": 512,    # 512x512
    b"ic10": 1024,   # 512x512@2x
}


def render_png(size: int) -> bytes:
    """Render the app icon at `size` px and return it as PNG bytes."""
    icon = create_app_icon(sizes=[size])
    image = icon.pixmap(size, size).toImage()

    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise SystemExit(f"failed to encode a {size}px PNG frame")
    buffer.close()
    return bytes(data)


def write_ico(frames: Dict[int, bytes], path: Path) -> None:
    """
    Write a multi-size .ico containing PNG-compressed frames.

    Layout: a 6-byte ICONDIR, then one 16-byte ICONDIRENTRY per frame, then
    the frame payloads. A size of 256 is encoded as 0 in the entry's width/
    height bytes, which are single bytes and so cannot hold 256 itself.
    """
    sizes = sorted(frames)
    header = struct.pack("<HHH", 0, 1, len(sizes))  # reserved, type=icon, count

    offset = len(header) + 16 * len(sizes)
    entries, payloads = b"", b""
    for size in sizes:
        payload = frames[size]
        entries += struct.pack(
            "<BBBBHHII",
            size if size < 256 else 0,   # width
            size if size < 256 else 0,   # height
            0,                           # palette colours (0 = truecolour)
            0,                           # reserved
            1,                           # colour planes
            32,                          # bits per pixel
            len(payload),
            offset,
        )
        payloads += payload
        offset += len(payload)

    path.write_bytes(header + entries + payloads)


def write_icns(frames: Dict[int, bytes], path: Path) -> None:
    """
    Write an .icns containing one PNG-based block per ICNS_TYPES entry.

    Layout: the magic `icns`, the total file length, then blocks of
    [4-byte type][4-byte length including this 8-byte header][PNG data].
    All integers are big-endian, unlike .ico.
    """
    blocks = b""
    for block_type, size in ICNS_TYPES.items():
        payload = frames[size]
        blocks += block_type + struct.pack(">I", len(payload) + 8) + payload

    path.write_bytes(b"icns" + struct.pack(">I", len(blocks) + 8) + blocks)


def main() -> None:
    app = QApplication(sys.argv)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    frames = {size: render_png(size) for size in SIZES}
    for size, payload in frames.items():
        (BUILD_DIR / f"icon_{size}.png").write_bytes(payload)

    ico_path = BUILD_DIR / "monitra.ico"
    icns_path = BUILD_DIR / "monitra.icns"
    write_ico({size: frames[size] for size in ICO_SIZES}, ico_path)
    write_icns(frames, icns_path)

    print(f"wrote {ico_path} ({len(ICO_SIZES)} sizes, {ico_path.stat().st_size} bytes)")
    print(f"wrote {icns_path} ({len(ICNS_TYPES)} blocks, {icns_path.stat().st_size} bytes)")
    print(f"wrote {len(SIZES)} PNG frames into {BUILD_DIR}")
    app.quit()


if __name__ == "__main__":
    main()
