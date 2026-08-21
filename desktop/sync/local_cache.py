"""
local_cache — Thread-safe SQLite cache for local persistence.

Tables:
  - projects: Cached project list with TTL
  - tasks: Cached tasks per project with TTL
  - time_entries_today: Cached today's time entries with TTL
  - pending_actions: Persistent sync queue for offline/background operations
  - session: Persisted auth token + user info for crash recovery
  - app_state: Running timer state (task_id, entry_id, start_time) for crash recovery

Uses WAL journal mode for concurrent reads during writes.
All operations are serialized via threading.Lock to avoid cross-thread issues.
No external dependencies — uses Python's built-in sqlite3 module.
"""
import json
import sqlite3
import threading
import time
import uuid
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def _get_cache_dir() -> Path:
    """Return the Monitra cache directory, creating it if needed."""
    home = Path.home()
    cache_dir = home / ".monitra"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _get_db_path() -> Path:
    """Return the path to the SQLite cache database."""
    return _get_cache_dir() / "cache.db"


class LocalCache:
    """
    Thread-safe SQLite cache for local persistence.
    
    All public methods acquire a lock before touching the database.
    The database is opened once and kept alive for the lifetime of the object.
    Call close() during application shutdown.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or str(_get_db_path())
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        """Create the database and all tables if they don't exist."""
        with self._lock:
            self._conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
                timeout=10.0,
            )
            self._conn.row_factory = sqlite3.Row
            # WAL mode for better concurrency (with fallback to default if unsupported by drive)
            try:
                self._conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.OperationalError:
                try:
                    self._conn.execute("PRAGMA journal_mode=delete")
                except sqlite3.OperationalError:
                    pass
            self._conn.execute("PRAGMA busy_timeout=5000")

            self._conn.executescript("""
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

                CREATE TABLE IF NOT EXISTS time_entries_today (
                    id INTEGER PRIMARY KEY,
                    data TEXT NOT NULL,
                    target_date TEXT NOT NULL,
                    cached_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS pending_actions (
                    id TEXT PRIMARY KEY,
                    action_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 5,
                    created_at REAL NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    next_retry_at REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    idempotency_key TEXT,
                    error_message TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_actions(status, priority, created_at);

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
            """)
            self._conn.commit()

    # ── Session Persistence ───────────────────────────────────────────────────

    def save_session(self, access_token: str, user_info: dict) -> None:
        """Persist the current auth session for crash recovery."""
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO session (key, value, updated_at) VALUES (?, ?, ?)",
                ("access_token", access_token, now)
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO session (key, value, updated_at) VALUES (?, ?, ?)",
                ("user_info", json.dumps(user_info), now)
            )
            self._conn.commit()

    def load_session(self) -> Optional[Dict[str, Any]]:
        """Load persisted session. Returns {'access_token': str, 'user_info': dict} or None."""
        with self._lock:
            rows = self._conn.execute("SELECT key, value FROM session").fetchall()
            if not rows:
                return None
            data = {row["key"]: row["value"] for row in rows}
            token = data.get("access_token")
            user_info_str = data.get("user_info")
            if not token or not user_info_str:
                return None
            try:
                user_info = json.loads(user_info_str)
            except (json.JSONDecodeError, TypeError):
                return None
            return {"access_token": token, "user_info": user_info}

    def clear_session(self) -> None:
        """Clear persisted session on logout."""
        with self._lock:
            self._conn.execute("DELETE FROM session")
            self._conn.commit()

    # ── App State (Timer Recovery) ────────────────────────────────────────────

    def save_app_state(self, key: str, value: Any) -> None:
        """Save a key-value pair to app_state for crash recovery."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO app_state (key, value, updated_at) VALUES (?, ?, ?)",
                (key, json.dumps(value), time.time())
            )
            self._conn.commit()

    def load_app_state(self, key: str) -> Optional[Any]:
        """Load a value from app_state. Returns None if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM app_state WHERE key = ?", (key,)
            ).fetchone()
            if row:
                try:
                    return json.loads(row["value"])
                except (json.JSONDecodeError, TypeError):
                    return None
            return None

    def clear_app_state(self, key: Optional[str] = None) -> None:
        """Clear app state. If key is given, clear only that key; otherwise clear all."""
        with self._lock:
            if key:
                self._conn.execute("DELETE FROM app_state WHERE key = ?", (key,))
            else:
                self._conn.execute("DELETE FROM app_state")
            self._conn.commit()

    # ── Project Cache ─────────────────────────────────────────────────────────

    def cache_projects(self, projects: List[Dict[str, Any]]) -> None:
        """Replace the entire projects cache with fresh data."""
        now = time.time()
        with self._lock:
            self._conn.execute("DELETE FROM projects")
            for p in projects:
                pid = p.get("id", 0)
                self._conn.execute(
                    "INSERT OR REPLACE INTO projects (id, data, cached_at) VALUES (?, ?, ?)",
                    (pid, json.dumps(p), now)
                )
            self._conn.commit()

    def get_cached_projects(self) -> Optional[List[Dict[str, Any]]]:
        """
        Load projects from cache.
        Returns None if cache is empty.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT data FROM projects ORDER BY id"
            ).fetchall()
            if not rows:
                return None
            return [json.loads(row["data"]) for row in rows]

    # ── Task Cache ────────────────────────────────────────────────────────────

    def cache_tasks(self, project_id: int, tasks: List[Dict[str, Any]]) -> None:
        """Replace the task cache for a specific project."""
        now = time.time()
        with self._lock:
            self._conn.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))
            for t in tasks:
                tid = t.get("id", 0)
                self._conn.execute(
                    "INSERT OR REPLACE INTO tasks (id, project_id, data, cached_at) VALUES (?, ?, ?, ?)",
                    (tid, project_id, json.dumps(t), now)
                )
            self._conn.execute(
                "INSERT OR REPLACE INTO task_cache_status (project_id, synced_at) VALUES (?, ?)",
                (project_id, now)
            )
            self._conn.commit()

    def get_cached_tasks(self, project_id: int) -> Optional[List[Dict[str, Any]]]:
        """
        Load tasks for a project from cache.
        Returns None if cache is empty (never loaded).
        Returns [] if cache exists but project has no tasks.
        """
        with self._lock:
            status = self._conn.execute(
                "SELECT synced_at FROM task_cache_status WHERE project_id = ?",
                (project_id,)
            ).fetchone()
            if not status:
                return None

            rows = self._conn.execute(
                "SELECT data FROM tasks WHERE project_id = ? ORDER BY id",
                (project_id,)
            ).fetchall()
            return [json.loads(row["data"]) for row in rows]

    def has_cached_tasks(self, project_id: int) -> bool:
        """Check if we have a cache entry (even empty) for this project."""
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM task_cache_status WHERE project_id = ?",
                (project_id,)
            ).fetchone()
            return row is not None

    # ── Time Entry Cache ──────────────────────────────────────────────────────

    def cache_time_entries(self, target_date: str, entries: List[Dict[str, Any]]) -> None:
        """Cache today's time entries."""
        now = time.time()
        with self._lock:
            self._conn.execute("DELETE FROM time_entries_today WHERE target_date = ?", (target_date,))
            for e in entries:
                eid = e.get("id", 0)
                self._conn.execute(
                    "INSERT OR REPLACE INTO time_entries_today (id, data, target_date, cached_at) VALUES (?, ?, ?, ?)",
                    (eid, json.dumps(e), target_date, now)
                )
            self._conn.commit()

    def get_cached_time_entries(self, target_date: str) -> Optional[List[Dict[str, Any]]]:
        """Load cached time entries for a date. Returns None if empty."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT data FROM time_entries_today WHERE target_date = ?",
                (target_date,)
            ).fetchall()
            if not rows:
                return None
            return [json.loads(row["data"]) for row in rows]

    def add_elapsed_to_cached_time_entry(self, target_date: str, task_id: Optional[int], elapsed_seconds: int) -> None:
        """Add newly tracked elapsed seconds to today's cached time entries."""
        if elapsed_seconds <= 0:
            return
        now = time.time()
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, data FROM time_entries_today WHERE target_date = ?",
                (target_date,)
            ).fetchall()

            found = False
            for row in rows:
                data = json.loads(row["data"])
                if task_id is not None and data.get("task_id") == task_id:
                    data["total_seconds"] = data.get("total_seconds", 0) + elapsed_seconds
                    data["status"] = "completed"
                    self._conn.execute(
                        "UPDATE time_entries_today SET data = ?, cached_at = ? WHERE id = ?",
                        (json.dumps(data), now, row["id"])
                    )
                    found = True
                    break

            if not found:
                new_entry = {
                    "id": -int(now * 1000) % 1000000,
                    "task_id": task_id,
                    "total_seconds": elapsed_seconds,
                    "status": "completed",
                    "target_date": target_date
                }
                self._conn.execute(
                    "INSERT INTO time_entries_today (id, data, target_date, cached_at) VALUES (?, ?, ?, ?)",
                    (new_entry["id"], json.dumps(new_entry), target_date, now)
                )
            self._conn.commit()

    # ── Pending Actions (Sync Queue) ──────────────────────────────────────────

    def enqueue_action(
        self,
        action_type: str,
        payload: Dict[str, Any],
        priority: int = 5,
        idempotency_key: Optional[str] = None,
    ) -> str:
        """
        Add an action to the pending sync queue.
        
        Priority levels (lower = higher priority):
          1 = stop_timer
          2 = start_timer
          3 = switch_timer (atomic stop+start)
          5 = create_task, update_task, delete_task
          8 = refresh_data
        
        Returns the action ID.
        """
        action_id = str(uuid.uuid4())
        now = time.time()

        # Check for duplicate idempotency key
        if idempotency_key:
            with self._lock:
                existing = self._conn.execute(
                    "SELECT id FROM pending_actions WHERE idempotency_key = ? AND status IN ('pending', 'processing')",
                    (idempotency_key,)
                ).fetchone()
                if existing:
                    return existing["id"]

        with self._lock:
            self._conn.execute(
                """INSERT INTO pending_actions 
                   (id, action_type, payload, priority, created_at, next_retry_at, status, idempotency_key)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
                (action_id, action_type, json.dumps(payload), priority, now, now, idempotency_key)
            )
            self._conn.commit()
        return action_id

    def get_next_pending_action(self) -> Optional[Dict[str, Any]]:
        """
        Get the highest-priority pending action that is ready for processing.
        Returns None if queue is empty.
        Marks the action as 'processing'.
        """
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                """SELECT id, action_type, payload, priority, created_at, retry_count, idempotency_key
                   FROM pending_actions
                   WHERE status = 'pending' AND next_retry_at <= ?
                   ORDER BY priority ASC, created_at ASC
                   LIMIT 1""",
                (now,)
            ).fetchone()
            if not row:
                return None
            action_id = row["id"]
            self._conn.execute(
                "UPDATE pending_actions SET status = 'processing' WHERE id = ?",
                (action_id,)
            )
            self._conn.commit()
            return {
                "id": action_id,
                "action_type": row["action_type"],
                "payload": json.loads(row["payload"]),
                "priority": row["priority"],
                "created_at": row["created_at"],
                "retry_count": row["retry_count"],
                "idempotency_key": row["idempotency_key"],
            }

    def complete_action(self, action_id: str) -> None:
        """Mark a pending action as completed and remove it."""
        with self._lock:
            self._conn.execute("DELETE FROM pending_actions WHERE id = ?", (action_id,))
            self._conn.commit()

    def fail_action(self, action_id: str, error_message: str, max_retries: int = 10) -> bool:
        """
        Mark a pending action as failed and schedule retry with exponential backoff.
        Returns True if the action will be retried, False if max retries exceeded.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT retry_count FROM pending_actions WHERE id = ?",
                (action_id,)
            ).fetchone()
            if not row:
                return False

            retry_count = row["retry_count"] + 1
            if retry_count > max_retries:
                self._conn.execute(
                    "UPDATE pending_actions SET status = 'failed', error_message = ? WHERE id = ?",
                    (error_message, action_id)
                )
                self._conn.commit()
                return False

            # Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s max
            delay = min(2 ** (retry_count - 1), 30)
            next_retry = time.time() + delay

            self._conn.execute(
                """UPDATE pending_actions 
                   SET status = 'pending', retry_count = ?, next_retry_at = ?, error_message = ?
                   WHERE id = ?""",
                (retry_count, next_retry, error_message, action_id)
            )
            self._conn.commit()
            return True

    def get_pending_count(self) -> int:
        """Return the number of pending actions in the queue."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM pending_actions WHERE status IN ('pending', 'processing')"
            ).fetchone()
            return row["cnt"] if row else 0

    def reset_processing_actions(self) -> None:
        """
        Reset any 'processing' actions back to 'pending'.
        Called on startup to recover from interrupted operations.
        """
        with self._lock:
            self._conn.execute(
                "UPDATE pending_actions SET status = 'pending' WHERE status = 'processing'"
            )
            self._conn.commit()

    def clear_stale_actions(self, max_age_seconds: float = 86400.0) -> None:
        """Remove failed actions older than max_age_seconds (default 24h)."""
        cutoff = time.time() - max_age_seconds
        with self._lock:
            self._conn.execute(
                "DELETE FROM pending_actions WHERE status = 'failed' AND created_at < ?",
                (cutoff,)
            )
            self._conn.commit()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
