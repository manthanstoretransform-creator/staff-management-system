"""
sync — Local persistence repository.

`SyncQueue` and `NetworkMonitor` were removed from this package; their
replacements are `background_services.sync.SyncService` and
`background_services.network.NetworkService`, both owned by the
ApplicationRuntime. What remains is the repository API over local storage.
"""
from sync.local_cache import LocalCache

__all__ = ["LocalCache"]
