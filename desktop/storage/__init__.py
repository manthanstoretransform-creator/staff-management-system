"""
storage — The single controlled access layer for Monitra's local SQLite database.

No module outside this package may open, share or close a sqlite3 connection.
Features and services reach the database through repository APIs that are
themselves built on `storage.manager.StorageManager`.
"""
from storage.manager import StorageManager, get_storage_manager, db_path

__all__ = ["StorageManager", "get_storage_manager", "db_path"]
