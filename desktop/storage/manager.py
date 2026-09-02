"""
storage.manager — Controlled SQLite access with a per-thread connection model.

The audit found a single `sqlite3.Connection` opened with
`check_same_thread=False` and shared across the GUI thread, the sync thread,
the network thread and every ad-hoc worker, serialised behind one Python
`threading.Lock`. That design had three production consequences:

  1. Every database call in the process contended on one lock, so a slow write
     on a background thread stalled the GUI thread.
  2. `close()` set `_conn = None` while other threads were mid-statement,
     producing `NoneType` errors that were then swallowed by broad excepts —
     the source of silently degraded cached data.
  3. Interleaved reads and writes on one connection meant a reader could
     observe a partially applied multi-statement update.

The model here is the one SQLite itself recommends:

  * **One connection per thread**, created lazily and never shared.

    Connections are tracked in a dict keyed by `threading.get_ident()`, *not*
    in a `threading.local()`. That distinction is load-bearing here and cost a
    real leak to find: `threading.local` keys its storage on the thread
    *object* returned by `threading.current_thread()`. For a thread Python did
    not create — every Qt thread is one — CPython synthesises a `_DummyThread`
    on demand and lets it be garbage collected, so the next call gets a brand
    new thread object and therefore empty thread-local storage. The result was
    a fresh `sqlite3.connect()` on essentially every database call from a
    service thread: measured at 2,004 connections for 2,000 queued operations,
    climbing without bound. The OS thread id is stable for the life of the
    thread, so keying on it is correct where `threading.local` is not.
  * **WAL journal mode**, so readers never block the writer and vice versa.
  * **`busy_timeout`**, so concurrent writers wait rather than raising
    `database is locked`.
  * **Explicit transactions** via `transaction()`, so a multi-statement update
    is atomic and a reader can never see it half-applied.
  * **Ordered shutdown**: connections are closed by their owning thread, and
    the final close checkpoints the WAL. The 4 MB un-checkpointed WAL found in
    `~/.monitra` was direct evidence that the process was being killed rather
    than shut down.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence

from core.logging_setup import get_logger
from core.paths import data_dir

log = get_logger("storage")


def cache_dir() -> Path:
    """
    Return the Monitra data directory, creating it if needed.

    Delegates to `core.paths.data_dir()` so the database, the sync queue and
    the logs can never disagree about where that directory is — and so a
    packaged build never tries to write inside its own (read-only,
    replaced-on-update) installation directory. See core/paths.py.
    """
    return data_dir()


def db_path() -> Path:
    """Return the path to the local SQLite database."""
    return cache_dir() / "cache.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    data TEXT NOT NULL,
    cached_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    data TEXT NOT NULL,
    cached_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);

CREATE TABLE IF NOT EXISTS task_cache_status (
    project_id INTEGER PRIMARY KEY,
    synced_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS task_statuses (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    color TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS time_entries_today (
    id INTEGER PRIMARY KEY,
    data TEXT NOT NULL,
    target_date TEXT NOT NULL,
    cached_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_date ON time_entries_today(target_date);

CREATE TABLE IF NOT EXISTS pending_actions (
    id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    payload TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 5,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL DEFAULT 0,
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    idempotency_key TEXT,
    error_message TEXT,
    session_generation INTEGER NOT NULL DEFAULT 0,
    defer_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_actions(status, priority, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_idem
    ON pending_actions(idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS session (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_app_usage (
    id TEXT PRIMARY KEY,
    time_entry_id INTEGER NOT NULL,
    application_name TEXT NOT NULL,
    window_title TEXT,
    duration_seconds INTEGER NOT NULL,
    recorded_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at REAL NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_app_usage_status ON pending_app_usage(status);

CREATE TABLE IF NOT EXISTS activity_samples (
    id TEXT PRIMARY KEY,
    time_entry_id INTEGER NOT NULL,
    window_start TEXT NOT NULL,
    window_seconds INTEGER NOT NULL,
    active_seconds INTEGER NOT NULL,
    key_events INTEGER NOT NULL DEFAULT 0,
    mouse_events INTEGER NOT NULL DEFAULT 0,
    keyboard_strokes INTEGER NOT NULL DEFAULT 0,
    mouse_clicks INTEGER NOT NULL DEFAULT 0,
    mouse_movements INTEGER NOT NULL DEFAULT 0,
    activity_percent INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at REAL NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activity_status ON activity_samples(status);
CREATE INDEX IF NOT EXISTS idx_activity_entry ON activity_samples(time_entry_id);

CREATE TABLE IF NOT EXISTS pending_unwanted_activity (
    id TEXT PRIMARY KEY,
    time_entry_id INTEGER NOT NULL,
    activity_type TEXT NOT NULL,
    key_or_action TEXT NOT NULL,
    occurrence_count INTEGER NOT NULL DEFAULT 0,
    alerted INTEGER NOT NULL DEFAULT 0,
    alert_count INTEGER NOT NULL DEFAULT 0,
    recorded_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at REAL NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_unwanted_status ON pending_unwanted_activity(status);

CREATE TABLE IF NOT EXISTS pending_adjustments (
    id TEXT PRIMARY KEY,
    time_entry_id INTEGER NOT NULL,
    adjustment_seconds INTEGER NOT NULL,
    reason TEXT NOT NULL,
    source_activity_type TEXT,
    source_key_or_action TEXT,
    source_client_event_id TEXT,
    recorded_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at REAL NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_adjustments_status ON pending_adjustments(status);

CREATE TABLE IF NOT EXISTS pending_url_usage (
    id TEXT PRIMARY KEY,
    time_entry_id INTEGER NOT NULL,
    browser_name TEXT NOT NULL,
    domain TEXT NOT NULL,
    url TEXT,
    page_title TEXT,
    duration_seconds INTEGER NOT NULL,
    recorded_at TEXT NOT NULL,
    client_event_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at REAL NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_url_usage_status ON pending_url_usage(status);
"""

#: Columns added after the original schema shipped. Applied idempotently so an
#: existing ~/.monitra/cache.db upgrades in place without losing queued work.
MIGRATIONS = [
    ("pending_actions", "entity_type", "TEXT"),
    ("pending_actions", "entity_id", "TEXT"),
    ("pending_actions", "updated_at", "REAL NOT NULL DEFAULT 0"),
    ("pending_actions", "session_generation", "INTEGER NOT NULL DEFAULT 0"),
    ("pending_actions", "defer_count", "INTEGER NOT NULL DEFAULT 0"),
    # Keyboard/mouse event counts (pynput), alongside the original
    # presence-based seconds counters -- see activity/input_counter.py.
    ("activity_samples", "keyboard_strokes", "INTEGER NOT NULL DEFAULT 0"),
    ("activity_samples", "mouse_clicks", "INTEGER NOT NULL DEFAULT 0"),
    ("activity_samples", "mouse_movements", "INTEGER NOT NULL DEFAULT 0"),
]


class StorageManager:
    """
    Owns the local database. Created once by the ApplicationRuntime.

    Thread-safety model: each thread gets its own connection, created on first
    use and closed when `close_current_thread()` (or `close()`, for the owning
    thread) is called. Connections are never passed between threads.
    """

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = str(path or db_path())
        # Keyed by threading.get_ident(); see the module docstring for why this
        # is not a threading.local().
        self._conns: Dict[int, sqlite3.Connection] = {}
        self._conns_lock = threading.RLock()
        self._closed = False
        self._initialise_schema()

    @property
    def path(self) -> str:
        return self._path

    # ── Connections ───────────────────────────────────────────────────────────

    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=15.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        # WAL lets readers proceed during a write. Fall back gracefully on
        # filesystems that do not support it (e.g. some network shares).
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            try:
                conn.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.DatabaseError:
                pass
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        log.debug(
            "opened sqlite connection for thread %s (%d)",
            threading.current_thread().name, threading.get_ident(),
        )
        return conn

    def connection(self) -> sqlite3.Connection:
        """Return this thread's connection, opening one if necessary."""
        if self._closed:
            raise RuntimeError("StorageManager is closed")
        ident = threading.get_ident()
        with self._conns_lock:
            conn = self._conns.get(ident)
            if conn is None:
                conn = self._new_connection()
                self._conns[ident] = conn
            return conn

    @property
    def connection_count(self) -> int:
        """Open connections. Bounded by the number of threads using storage."""
        with self._conns_lock:
            return len(self._conns)

    # ── Statements ────────────────────────────────────────────────────────────

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        """Execute a single statement in autocommit mode."""
        return self.connection().execute(sql, params)

    def query_all(self, sql: str, params: Sequence[Any] = ()) -> List[sqlite3.Row]:
        return self.connection().execute(sql, params).fetchall()

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[sqlite3.Row]:
        return self.connection().execute(sql, params).fetchone()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """
        Run a block of statements atomically.

        Use this for every multi-statement update. A reader on another thread
        sees either none of the block or all of it — never a partial write.
        """
        conn = self.connection()
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.DatabaseError:
                log.exception("rollback failed")
            raise
        else:
            conn.execute("COMMIT")

    # ── Schema ────────────────────────────────────────────────────────────────

    def _initialise_schema(self) -> None:
        conn = self.connection()
        conn.executescript(SCHEMA)
        existing_tables = {
            row["name"] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        for table, column, decl in MIGRATIONS:
            if table not in existing_tables:
                continue
            columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in columns:
                log.info("migrating %s: adding column %s", table, column)
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        log.info("storage ready at %s", self._path)

    # ── Shutdown ──────────────────────────────────────────────────────────────

    def close_current_thread(self) -> None:
        """
        Close the calling thread's connection, if it has one.

        Service threads call this as they stop, so a connection never outlives
        its thread — and so a recycled thread id can never inherit a connection
        belonging to a thread that has already exited.
        """
        ident = threading.get_ident()
        with self._conns_lock:
            conn = self._conns.pop(ident, None)
        if conn is None:
            return
        try:
            conn.close()
        except sqlite3.DatabaseError:
            log.exception("error closing connection for thread %d", ident)

    def close(self) -> None:
        """
        Close every connection and checkpoint the WAL.

        Called once, last, by the runtime's shutdown sequence — after all
        service threads have been confirmed stopped. Closing while other
        threads are still executing statements was one of the audited defects,
        so the runtime enforces that ordering.
        """
        if self._closed:
            return
        self._closed = True
        with self._conns_lock:
            conns = list(self._conns.values())
            self._conns.clear()

        # Checkpoint on whichever connection is still usable, so the WAL does
        # not keep growing across runs.
        for conn in conns:
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                break
            except sqlite3.DatabaseError:
                continue

        for conn in conns:
            try:
                conn.close()
            except sqlite3.DatabaseError:
                # A connection owned by a thread that has already exited may
                # refuse to close from here; the process is ending regardless.
                log.debug("connection close failed during shutdown", exc_info=True)
        log.info("storage closed (%d connection(s))", len(conns))


# ── Process-wide accessor ─────────────────────────────────────────────────────

_manager: Optional[StorageManager] = None
_manager_lock = threading.Lock()


def get_storage_manager(path: Optional[str] = None) -> StorageManager:
    """
    Return the process-wide StorageManager, creating it on first call.

    The ApplicationRuntime calls this during startup; everything else should
    receive the instance by injection rather than reaching for the global.
    """
    global _manager
    with _manager_lock:
        if _manager is None or _manager._closed:
            _manager = StorageManager(path)
        return _manager


def reset_storage_manager() -> None:
    """Drop the process-wide manager. Used by tests."""
    global _manager
    with _manager_lock:
        if _manager is not None:
            _manager.close()
        _manager = None
