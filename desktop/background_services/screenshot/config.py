"""
screenshot.config — Every tunable of the screenshot pipeline, in one place.

The capture rule is expressed as *windows*, not as delays: the tracked day is
divided into fixed `WINDOW_DURATION_MINUTES` windows aligned to the epoch, and
each window gets exactly `SCREENSHOTS_PER_WINDOW` captures at random instants
inside it. Raising `SCREENSHOTS_PER_WINDOW` to 3 or 5 is the only change
required to capture three or five per window — the scheduler, the queue, the
upload path, the backend and the timeline grouping are all written against the
configured count rather than against "one".

A "capture, then sleep a random amount, then capture again" design was
deliberately not used: it cannot guarantee a per-window count, it drifts, and
it produces two captures seconds apart across a window boundary.

Environment overrides exist so a support engineer can reproduce a report
without a rebuild. They are read once per process, like every other setting
here.
"""
from __future__ import annotations

import os

#: Length of one scheduling window. The timeline API groups by the same value.
WINDOW_DURATION_MINUTES = 10

#: How many screenshots are captured in each window. Production is 1 today;
#: 3 and 5 are supported by construction (see the module docstring).
SCREENSHOTS_PER_WINDOW = 1

#: Final image geometry. Every stored screenshot is exactly this, so the grid
#: and timeline can lay out without measuring each file.
IMAGE_SIZE = 1000

#: WebP quality bounds for the adaptive compressor. It starts at
#: `WEBP_QUALITY_START` and steps down by `WEBP_QUALITY_STEP` while the encoded
#: image is larger than `TARGET_FILE_BYTES`, never going below
#: `WEBP_QUALITY_MIN` — the floor is what keeps "aggressive" from becoming
#: "unreadable", which would make the feature worthless for its actual purpose.
WEBP_QUALITY_START = 72
WEBP_QUALITY_MIN = 45
WEBP_QUALITY_STEP = 9
WEBP_METHOD = 5  # 0 (fast) .. 6 (slowest, smallest)

#: Size the compressor aims for. Not a hard cap: if the floor quality is still
#: larger than this, the larger file is kept rather than the image destroyed.
TARGET_FILE_BYTES = 120 * 1024

#: Padding colour for the letterboxed canvas. Neutral dark grey reads as
#: "canvas", not as part of the captured desktop.
PAD_COLOR = (24, 24, 27)

#: Directory (under the Monitra data directory) holding the day folders.
CACHE_DIR_NAME = "screenshot-cache"

#: How many upload attempts a queued screenshot gets before it is parked as
#: `failed`. At the shared 50–150% jittered exponential backoff this spans
#: several hours, which covers an overnight outage.
MAX_UPLOAD_RETRIES = 12

#: Cap on one upload's HTTP timeout. A screenshot is ~100 KB, but a queued
#: backlog uploads over whatever link the user has.
UPLOAD_TIMEOUT_SECONDS = 30.0


def _int_env(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


def window_seconds() -> int:
    """Window length in seconds, honouring `MONITRA_SCREENSHOT_WINDOW_MINUTES`."""
    return _int_env("MONITRA_SCREENSHOT_WINDOW_MINUTES", WINDOW_DURATION_MINUTES) * 60


def screenshots_per_window() -> int:
    """Captures per window, honouring `MONITRA_SCREENSHOTS_PER_WINDOW`."""
    return _int_env("MONITRA_SCREENSHOTS_PER_WINDOW", SCREENSHOTS_PER_WINDOW)


def enabled() -> bool:
    """Whether capture runs at all. Set `MONITRA_SCREENSHOTS=0` to disable."""
    return os.getenv("MONITRA_SCREENSHOTS", "1").strip().lower() not in ("0", "false", "no")
