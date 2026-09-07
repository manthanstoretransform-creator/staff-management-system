"""
screenshot.image_processor — Raw capture to a 1000x1000 WebP.

The processing order matters and is fixed:

    scale proportionally to fit  ->  centre on a 1000x1000 canvas  ->  RGB
    ->  encode WebP  ->  step the quality down until the target size is met

Scaling to fit and padding, rather than resizing to 1000x1000 directly, is what
keeps a 16:9 desktop from being squashed into a square. A distorted screenshot
is not a smaller screenshot, it is a wrong one — text in it stops being
legible, which is the entire reason the image is captured.

The quality search is adaptive rather than a single hardcoded number because
screen content varies by two orders of magnitude in entropy: a terminal encodes
to a few kilobytes at quality 72, a photo-editing session does not. A fixed
quality therefore means either bloated text captures or unreadable dense ones.
The search stops at `WEBP_QUALITY_MIN`, and if even that is over target the
larger file is kept — an oversized readable screenshot beats a small useless
one, and the real size is recorded either way.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional

from background_services.screenshot import config
from background_services.screenshot.capture import RawCapture
from core.logging_setup import get_logger

log = get_logger("screenshot.image")

_pil_image = None


@dataclass(frozen=True)
class ProcessedImage:
    """A finished, encodable screenshot."""

    data: bytes
    width: int
    height: int
    quality: int
    mime_type: str = "image/webp"

    @property
    def size_bytes(self) -> int:
        return len(self.data)


def _load_pil():
    global _pil_image
    if _pil_image is None:
        try:
            from PIL import Image  # type: ignore

            _pil_image = Image
        except Exception:  # noqa: BLE001
            log.warning(
                "Pillow is not available; screenshots cannot be processed and "
                "none will be captured",
                exc_info=True,
            )
            _pil_image = False
    return _pil_image or None


def supported() -> bool:
    """Whether a capture can be turned into a stored image on this machine."""
    return _load_pil() is not None


def process(raw: RawCapture, size: Optional[int] = None) -> Optional[ProcessedImage]:
    """
    Turn a raw capture into the stored WebP.

    :return: the processed image, or None if it could not be produced. Never
        raises — a malformed frame must not stop the capture loop.
    """
    Image = _load_pil()
    if Image is None:
        return None

    edge = size or config.IMAGE_SIZE
    try:
        frame = Image.frombytes("RGB", (raw.width, raw.height), raw.pixels, "raw", "BGRX")

        # Fit inside the square, preserving the aspect ratio. `thumbnail` only
        # ever shrinks; a display narrower than the target is scaled up here so
        # the output geometry is always exactly `edge x edge`.
        scale = min(edge / raw.width, edge / raw.height)
        target = (max(1, round(raw.width * scale)), max(1, round(raw.height * scale)))
        frame = frame.resize(target, Image.LANCZOS)

        canvas = Image.new("RGB", (edge, edge), config.PAD_COLOR)
        canvas.paste(frame, ((edge - target[0]) // 2, (edge - target[1]) // 2))

        return _encode(canvas, edge)
    except Exception:  # noqa: BLE001
        log.exception("could not process a %dx%d capture", raw.width, raw.height)
        return None


def _encode(canvas, edge: int) -> ProcessedImage:
    """Encode with the adaptive quality search described in the module docstring."""
    quality = config.WEBP_QUALITY_START
    best: Optional[bytes] = None
    best_quality = quality

    while True:
        buffer = io.BytesIO()
        canvas.save(buffer, format="WEBP", quality=quality, method=config.WEBP_METHOD)
        data = buffer.getvalue()
        best, best_quality = data, quality
        if len(data) <= config.TARGET_FILE_BYTES or quality <= config.WEBP_QUALITY_MIN:
            break
        quality = max(config.WEBP_QUALITY_MIN, quality - config.WEBP_QUALITY_STEP)

    log.debug(
        "encoded screenshot at quality %d (%d bytes)", best_quality, len(best or b"")
    )
    return ProcessedImage(data=best or b"", width=edge, height=edge, quality=best_quality)
