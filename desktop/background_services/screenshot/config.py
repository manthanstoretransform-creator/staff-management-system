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

#: --- Fallback compression -------------------------------------------------
#:
#: The primary search above stops at `WEBP_QUALITY_MIN` on purpose: that floor
#: is what keeps a screenshot readable, and readability is the whole point of
#: capturing one. But it means a genuinely dense screen can finish the primary
#: pass still over `FALLBACK_TRIGGER_BYTES`. The fallback exists for exactly
#: that case and no other — a capture already inside the threshold is kept
#: byte-for-byte, so on a normal desktop this code never runs.
#:
#: When it does run it aims to remove `FALLBACK_REDUCTION_PERCENT` of the
#: primary result's size, stepping quality down from the primary's quality
#: towards `FALLBACK_QUALITY_MIN` in at most `FALLBACK_MAX_ATTEMPTS` encodes.
#: The attempt cap is what makes this bounded work on the task pool rather than
#: an open-ended loop.
FALLBACK_ENABLED = True

#: Size above which the fallback engages. Deliberately lower than
#: `TARGET_FILE_BYTES`: the primary pass is content to stop at 120 KB, but a
#: screenshot every ten minutes per user adds up in Drive, so anything over
#: 60 KB is worth a second look. The two figures answer different questions —
#: "when may the primary stop trying" and "when is the result worth
#: recompressing" — and are independent on purpose.
FALLBACK_TRIGGER_BYTES = 60 * 1024

#: How much of the primary-compressed size the fallback tries to remove.
#: 40 means "aim for 60% of the primary size".
FALLBACK_REDUCTION_PERCENT = 40

#: Hard ceiling on re-encodes. Each one is a full WebP encode of a 1000x1000
#: image, so this bounds the CPU one capture can cost.
FALLBACK_MAX_ATTEMPTS = 5

#: The floor the fallback may compress to. Below `WEBP_QUALITY_MIN` by design —
#: that is the point of a fallback — but still a floor, because an unreadable
#: screenshot is a lost screenshot no matter how small it is.
FALLBACK_QUALITY_MIN = 20

#: Fallback encodes use the slowest, smallest setting. It costs more CPU than
#: `WEBP_METHOD`, which is affordable precisely because this path is rare.
FALLBACK_WEBP_METHOD = 6

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


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() not in ("0", "false", "no")


def fallback_enabled() -> bool:
    """Whether the fallback pass may run at all."""
    return _bool_env("MONITRA_SCREENSHOT_FALLBACK", FALLBACK_ENABLED)


def fallback_trigger_bytes() -> int:
    """Size above which a primary-compressed screenshot gets a second pass."""
    return _int_env("MONITRA_SCREENSHOT_FALLBACK_TRIGGER_BYTES",
                    FALLBACK_TRIGGER_BYTES, minimum=1024)


def fallback_reduction_percent() -> int:
    """
    Percentage of the primary size the fallback aims to remove.

    Clamped to 1..90: 0 would ask for no reduction at all and anything near 100
    asks for a file the encoder cannot produce without destroying the image.
    """
    value = _int_env("MONITRA_SCREENSHOT_FALLBACK_REDUCTION_PERCENT",
                     FALLBACK_REDUCTION_PERCENT)
    return max(1, min(90, value))


def fallback_max_attempts() -> int:
    """Hard cap on fallback re-encodes for one capture."""
    return _int_env("MONITRA_SCREENSHOT_FALLBACK_MAX_ATTEMPTS", FALLBACK_MAX_ATTEMPTS)


def fallback_quality_min() -> int:
    """The lowest WebP quality the fallback may encode at."""
    return _int_env("MONITRA_SCREENSHOT_FALLBACK_MIN_QUALITY",
                    FALLBACK_QUALITY_MIN, minimum=1)
