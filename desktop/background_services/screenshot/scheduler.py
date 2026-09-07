"""
screenshot.scheduler — Which instants inside a window get captured.

Pure functions over timestamps, with no Qt, no I/O and no clock of their own,
so the rule can be tested exhaustively rather than observed over ten minutes.

The model:

* The timeline is divided into fixed windows of `window_seconds` aligned to the
  UNIX epoch, so every client in the fleet agrees on where a window starts and
  the backend can group by the same arithmetic without storing a window column.
* A window's plan is `n` distinct random instants inside `[start, end)`.
* When tracking begins mid-window, instants already in the past are dropped —
  a window that is half over cannot retroactively be captured — so the count
  for a partial window is at most the configured one, never more.
* `already_captured` is subtracted from the plan so a restart inside a window
  cannot take a second screenshot the window's budget has already spent.
"""
from __future__ import annotations

import random
from typing import List


def window_index(now: float, window_seconds: int) -> int:
    """The epoch-aligned index of the window containing `now`."""
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")
    return int(now // window_seconds)


def window_bounds(index: int, window_seconds: int) -> tuple[float, float]:
    """`(start, end)` epoch seconds of the window with this index."""
    start = float(index * window_seconds)
    return start, start + window_seconds


def plan_window(
    index: int,
    window_seconds: int,
    per_window: int,
    now: float,
    *,
    already_captured: int = 0,
    rng: random.Random | None = None,
) -> List[float]:
    """
    Capture instants for one window, in ascending order.

    :param index: window index from `window_index()`.
    :param per_window: the configured captures per window.
    :param now: the current instant; anything at or before it is unschedulable.
    :param already_captured: captures this window has already spent, e.g.
        before a restart. Subtracted from the budget.
    :return: 0..(per_window - already_captured) instants, all strictly in the
        future and all inside the window.
    """
    budget = max(0, per_window - max(0, already_captured))
    if budget == 0:
        return []

    start, end = window_bounds(index, window_seconds)
    # Only the part of the window that has not happened yet is schedulable.
    lower = max(start, now)
    # A capture must land strictly inside the window; leave a second of margin
    # so a scheduled instant cannot round onto the next window's start.
    upper = end - 1.0
    if upper <= lower:
        return []

    generator = rng or random
    chosen: set[int] = set()
    span = int(upper - lower)
    if span <= 0:
        return [lower]

    # Sample whole seconds so two captures in the same window can never be
    # sub-second apart, which would be two pictures of the same screen.
    attempts = 0
    while len(chosen) < min(budget, span) and attempts < budget * 20:
        chosen.add(generator.randrange(span))
        attempts += 1

    return sorted(lower + offset for offset in chosen)
