"""
tracking — OS-level introspection helpers.

The tracking *lifecycle* (sessions, sub-trackers, elapsed time) now belongs to
`background_services.timer.TimerService`. What remains here is the platform
query used by the app-usage service.

`TrackingManager` and `AppUsageTracker` were removed: they duplicated the
timer's state and ran their sampling timers on the GUI thread. See
DO_NOT_DO.md.
"""
from tracking.active_window import get_active_window_info

__all__ = ["get_active_window_info"]
