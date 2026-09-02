"""
local_cache — Repository API over the local SQLite database.

This is a repository, not a connection owner. All access goes through
`storage.manager.StorageManager`, which gives each thread its own connection
and provides real transactions. The previous implementation owned one shared
connection guarded by a global `threading.Lock`; see storage/manager.py for
why that was replaced.

The public method surface is unchanged so existing callers keep working. What
changed underneath:

  * multi-statement updates now run inside a transaction, so a concurrent
    reader can never observe a half-written cache (the "task name renders as
    ?" class of defect);
  * `close()` no longer yanks a connection out from under other threads —
    connection lifetime belongs to the StorageManager, and the runtime closes
    it only after every service thread has been confirmed stopped;
  * queue rows carry `session_generation`, `entity_type`/`entity_id` and
    `updated_at`, so stale work from a previous login can be identified and
    discarded rather than applied to the current session.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional

from core.logging_setup import get_logger, session_generation
from storage.manager import StorageManager, cache_dir, db_path, get_storage_manager

log = get_logger("cache")

# Re-exported for callers that imported these helpers from this module.
_get_cache_dir = cache_dir
_get_db_path = db_path

#: Terminal + non-terminal states a queued action can hold.
PENDING = "pending"
PROCESSING = "processing"
RETRY = "retry"
FAILED = "failed"
CANCELLED = "cancelled"


class LocalCache:
    """
    Local persistence for projects, tasks, time entries, queued sync actions,
    session state and captured activity.
    """

    def __init__(
        self,
        db_path_override: Optional[str] = None,
        storage: Optional[StorageManager] = None,
    ) -> None:
        self._storage = storage or get_storage_manager(db_path_override)

    @property
    def storage(self) -> StorageManager:
        return self._storage

    # ── Session Persistence ───────────────────────────────────────────────────

    def save_session(self, access_token: str, user_info: dict) -> None:
        """Persist the current auth session for crash recovery."""
        now = time.time()
        with self._storage.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO session (key, value, updated_at) VALUES (?, ?, ?)",
                ("access_token", access_token, now),
            )
            conn.execute(
                "INSERT OR REPLACE INTO session (key, value, updated_at) VALUES (?, ?, ?)",
                ("user_info", json.dumps(user_info), now),
            )

    def load_session(self) -> Optional[Dict[str, Any]]:
        """Load persisted session, or None if absent/corrupt."""
        rows = self._storage.query_all("SELECT key, value FROM session")
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
            log.warning("persisted user_info is corrupt; ignoring stored session")
            return None
        return {"access_token": token, "user_info": user_info}

    def clear_session(self) -> None:
        """Clear persisted session on logout."""
        self._storage.execute("DELETE FROM session")

    def clear_user_scoped_cache(self) -> None:
        """
        Drop every cached row that belongs to whoever was signed in.

        The projects, tasks, task-status and time-entry caches are read
        straight back on the next login to paint the dashboard before the
        network answers. They carry no user column, so without this the next
        user to sign in on this machine is shown the previous user's
        projects and tasks until the first response arrives -- measured, and
        visibly wrong rather than merely stale.

        Deliberately not the durable queues (pending actions, activity
        samples, unwanted activity, adjustments): those are captured work
        that must still be uploaded, and they are already fenced off by the
        session generation.
        """
        with self._storage.transaction() as conn:
            for table in ("projects", "tasks", "task_cache_status",
                          "task_statuses", "time_entries_today"):
                conn.execute(f"DELETE FROM {table}")

    # ── App State (Timer / Recovery) ──────────────────────────────────────────

    def save_app_state(self, key: str, value: Any) -> None:
        self._storage.execute(
            "INSERT OR REPLACE INTO app_state (key, value, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), time.time()),
        )

    def load_app_state(self, key: str) -> Optional[Any]:
        row = self._storage.query_one("SELECT value FROM app_state WHERE key = ?", (key,))
        if not row:
            return None
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            log.warning("app_state[%s] is corrupt; discarding", key)
            return None

    def clear_app_state(self, key: Optional[str] = None) -> None:
        if key:
            self._storage.execute("DELETE FROM app_state WHERE key = ?", (key,))
        else:
            self._storage.execute("DELETE FROM app_state")

    # ── Project Cache ─────────────────────────────────────────────────────────

    def cache_projects(self, projects: List[Dict[str, Any]]) -> None:
        """Atomically replace the projects cache."""
        now = time.time()
        with self._storage.transaction() as conn:
            conn.execute("DELETE FROM projects")
            for p in projects:
                conn.execute(
                    "INSERT OR REPLACE INTO projects (id, data, cached_at) VALUES (?, ?, ?)",
                    (p.get("id", 0), json.dumps(p), now),
                )

    def get_cached_projects(self) -> Optional[List[Dict[str, Any]]]:
        rows = self._storage.query_all("SELECT data FROM projects ORDER BY id")
        if not rows:
            return None
        return [json.loads(row["data"]) for row in rows]

    # ── Task Cache ────────────────────────────────────────────────────────────

    def cache_tasks(self, project_id: int, tasks: List[Dict[str, Any]]) -> None:
        """
        Atomically replace the task cache for one project.

        The delete, the inserts and the freshness marker are one transaction.
        Previously they were separate autocommitted statements, so a reader
        that ran between the DELETE and the INSERTs saw an empty or partial
        task list and rendered placeholder rows.
        """
        now = time.time()
        with self._storage.transaction() as conn:
            conn.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))
            for t in tasks:
                conn.execute(
                    "INSERT OR REPLACE INTO tasks (id, project_id, data, cached_at) "
                    "VALUES (?, ?, ?, ?)",
                    (t.get("id", 0), project_id, json.dumps(t), now),
                )
            conn.execute(
                "INSERT OR REPLACE INTO task_cache_status (project_id, synced_at) VALUES (?, ?)",
                (project_id, now),
            )

    def get_cached_tasks(self, project_id: int) -> Optional[List[Dict[str, Any]]]:
        """
        Return cached tasks for a project.

        None means "never cached"; [] means "cached, and the project has no
        tasks". Callers rely on that distinction to decide whether to show a
        loader or an empty state.
        """
        status = self._storage.query_one(
            "SELECT synced_at FROM task_cache_status WHERE project_id = ?", (project_id,)
        )
        if not status:
            return None
        rows = self._storage.query_all(
            "SELECT data FROM tasks WHERE project_id = ? ORDER BY id", (project_id,)
        )
        return [json.loads(row["data"]) for row in rows]

    def has_cached_tasks(self, project_id: int) -> bool:
        return self._storage.query_one(
            "SELECT 1 FROM task_cache_status WHERE project_id = ?", (project_id,)
        ) is not None

    def cache_task_statuses(self, statuses: List[Dict[str, Any]]) -> None:
        with self._storage.transaction() as conn:
            conn.execute("DELETE FROM task_statuses")
            for s in statuses:
                conn.execute(
                    "INSERT OR REPLACE INTO task_statuses (id, name, color) VALUES (?, ?, ?)",
                    (s.get("id"), s.get("name"), s.get("color")),
                )

    def get_cached_task_statuses(self) -> Optional[List[Dict[str, Any]]]:
        rows = self._storage.query_all("SELECT id, name, color FROM task_statuses ORDER BY id")
        if not rows:
            return None
        return [{"id": r["id"], "name": r["name"], "color": r["color"]} for r in rows]

    # ── Time Entry Cache ──────────────────────────────────────────────────────

    def cache_time_entries(self, target_date: str, entries: List[Dict[str, Any]]) -> None:
        now = time.time()
        with self._storage.transaction() as conn:
            conn.execute("DELETE FROM time_entries_today WHERE target_date = ?", (target_date,))
            for e in entries:
                conn.execute(
                    "INSERT OR REPLACE INTO time_entries_today (id, data, target_date, cached_at) "
                    "VALUES (?, ?, ?, ?)",
                    (e.get("id", 0), json.dumps(e), target_date, now),
                )

    def get_cached_time_entries(self, target_date: str) -> Optional[List[Dict[str, Any]]]:
        rows = self._storage.query_all(
            "SELECT data FROM time_entries_today WHERE target_date = ?", (target_date,)
        )
        if not rows:
            return None
        return [json.loads(row["data"]) for row in rows]

    def add_elapsed_to_cached_time_entry(
        self, target_date: str, task_id: Optional[int], elapsed_seconds: int
    ) -> None:
        """Fold newly tracked seconds into the cached entries for a date."""
        if elapsed_seconds <= 0:
            return
        now = time.time()
        with self._storage.transaction() as conn:
            rows = conn.execute(
                "SELECT id, data FROM time_entries_today WHERE target_date = ?", (target_date,)
            ).fetchall()

            for row in rows:
                data = json.loads(row["data"])
                if task_id is not None and data.get("task_id") == task_id:
                    data["total_seconds"] = data.get("total_seconds", 0) + elapsed_seconds
                    data["status"] = "completed"
                    conn.execute(
                        "UPDATE time_entries_today SET data = ?, cached_at = ? WHERE id = ?",
                        (json.dumps(data), now, row["id"]),
                    )
                    return

            new_entry = {
                "id": -int(now * 1000) % 1000000,
                "task_id": task_id,
                "total_seconds": elapsed_seconds,
                "status": "completed",
                "target_date": target_date,
            }
            conn.execute(
                "INSERT OR REPLACE INTO time_entries_today (id, data, target_date, cached_at) "
                "VALUES (?, ?, ?, ?)",
                (new_entry["id"], json.dumps(new_entry), target_date, now),
            )

    # ── Pending Actions (durable sync queue) ──────────────────────────────────

    def enqueue_action(
        self,
        action_type: str,
        payload: Dict[str, Any],
        priority: int = 5,
        idempotency_key: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> str:
        """
        Durably enqueue an action.

        Duplicate protection is enforced by a UNIQUE index on
        `idempotency_key` as well as the pre-check, so two threads racing on
        the same key cannot both insert.
        """
        now = time.time()
        if idempotency_key:
            existing = self._storage.query_one(
                "SELECT id FROM pending_actions WHERE idempotency_key = ? "
                "AND status IN ('pending', 'processing', 'retry')",
                (idempotency_key,),
            )
            if existing:
                return existing["id"]

        action_id = str(uuid.uuid4())
        try:
            self._storage.execute(
                """INSERT INTO pending_actions
                   (id, action_type, entity_type, entity_id, payload, priority,
                    created_at, updated_at, next_retry_at, status, idempotency_key,
                    session_generation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (
                    action_id, action_type, entity_type, entity_id,
                    json.dumps(payload), priority, now, now, now,
                    idempotency_key, session_generation(),
                ),
            )
        except Exception:  # sqlite3.IntegrityError on the unique index
            row = self._storage.query_one(
                "SELECT id FROM pending_actions WHERE idempotency_key = ?", (idempotency_key,)
            )
            if row:
                return row["id"]
            raise
        log.info("enqueued %s priority=%d", action_type, priority, extra={"op": action_id})
        return action_id

    def get_next_pending_action(self) -> Optional[Dict[str, Any]]:
        """
        Claim the highest-priority action that is ready to run.

        The select and the claim are one transaction, so two consumers can
        never claim the same row.
        """
        now = time.time()
        with self._storage.transaction() as conn:
            row = conn.execute(
                """SELECT id, action_type, entity_type, entity_id, payload, priority,
                          created_at, retry_count, idempotency_key, session_generation,
                          defer_count
                   FROM pending_actions
                   WHERE status IN ('pending', 'retry') AND next_retry_at <= ?
                   ORDER BY priority ASC, created_at ASC
                   LIMIT 1""",
                (now,),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE pending_actions SET status = 'processing', updated_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            return {
                "id": row["id"],
                "action_type": row["action_type"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "payload": json.loads(row["payload"]),
                "priority": row["priority"],
                "created_at": row["created_at"],
                "retry_count": row["retry_count"],
                "idempotency_key": row["idempotency_key"],
                "session_generation": row["session_generation"],
                "defer_count": row["defer_count"],
            }

    def complete_action(self, action_id: str) -> None:
        self._storage.execute("DELETE FROM pending_actions WHERE id = ?", (action_id,))

    def defer_action(self, action_id: str, reason: str, delay_seconds: float = 2.0) -> int:
        """
        Reschedule an action whose prerequisites are not ready yet.

        Deliberately does **not** increment `retry_count`: waiting on an
        ordering dependency is not a failure and must not consume the retry
        budget that exists for genuine errors. `defer_count` is tracked
        separately so a dependency that never arrives cannot defer forever.

        :return: how many times this action has now been deferred.
        """
        now = time.time()
        self._storage.execute(
            "UPDATE pending_actions SET status = 'pending', next_retry_at = ?, "
            "error_message = ?, updated_at = ?, defer_count = defer_count + 1 "
            "WHERE id = ?",
            (now + delay_seconds, reason, now, action_id),
        )
        row = self._storage.query_one(
            "SELECT defer_count FROM pending_actions WHERE id = ?", (action_id,)
        )
        return row["defer_count"] if row else 0

    def cancel_action(self, action_id: str, reason: str = "") -> None:
        self._storage.execute(
            "UPDATE pending_actions SET status = 'cancelled', error_message = ?, updated_at = ? "
            "WHERE id = ?",
            (reason, time.time(), action_id),
        )

    def fail_action(self, action_id: str, error_message: str, max_retries: int = 10) -> bool:
        """
        Record a failure and schedule a retry with exponential backoff + jitter.

        Jitter matters at fleet scale: without it, every client that lost the
        backend at the same moment retries at exactly the same moment, which
        is a self-inflicted thundering herd on recovery.

        :return: True if the action will be retried.
        """
        import random

        now = time.time()
        row = self._storage.query_one(
            "SELECT retry_count FROM pending_actions WHERE id = ?", (action_id,)
        )
        if not row:
            return False

        retry_count = row["retry_count"] + 1
        if retry_count > max_retries:
            self._storage.execute(
                "UPDATE pending_actions SET status = 'failed', error_message = ?, updated_at = ? "
                "WHERE id = ?",
                (error_message, now, action_id),
            )
            log.error("action exhausted retries: %s", error_message, extra={"op": action_id})
            return False

        base = min(2 ** (retry_count - 1), 60)
        delay = base * (0.5 + random.random())  # 50%–150% jitter
        self._storage.execute(
            """UPDATE pending_actions
               SET status = 'retry', retry_count = ?, next_retry_at = ?,
                   error_message = ?, updated_at = ?
               WHERE id = ?""",
            (retry_count, now + delay, error_message, now, action_id),
        )
        log.info(
            "action retry %d/%d in %.1fs: %s",
            retry_count, max_retries, delay, error_message, extra={"op": action_id},
        )
        return True

    def get_pending_count(self) -> int:
        row = self._storage.query_one(
            "SELECT COUNT(*) AS cnt FROM pending_actions "
            "WHERE status IN ('pending', 'processing', 'retry')"
        )
        return row["cnt"] if row else 0

    def reset_processing_actions(self) -> None:
        """
        Return interrupted claims to the pending pool.

        Called once at startup: anything left in 'processing' belongs to a
        previous process that died mid-operation.
        """
        cursor = self._storage.execute(
            "UPDATE pending_actions SET status = 'pending' WHERE status = 'processing'"
        )
        if cursor.rowcount:
            log.info("recovered %d interrupted action(s) from previous run", cursor.rowcount)

    def clear_stale_actions(self, max_age_seconds: float = 86400.0) -> None:
        cutoff = time.time() - max_age_seconds
        self._storage.execute(
            "DELETE FROM pending_actions WHERE status IN ('failed', 'cancelled') AND created_at < ?",
            (cutoff,),
        )

    def has_pending_action_for_client_op(self, client_op: str, action_type: str) -> bool:
        """Whether an unfinished action of `action_type` carries this client op."""
        rows = self._storage.query_all(
            "SELECT payload FROM pending_actions "
            "WHERE action_type = ? AND status IN ('pending', 'processing', 'retry')",
            (action_type,),
        )
        for row in rows:
            try:
                if json.loads(row["payload"]).get("client_op") == client_op:
                    return True
            except (json.JSONDecodeError, TypeError):
                continue
        return False

    def resolve_entry_id_for_client_op(self, client_op: str, entry_id: int) -> int:
        """
        Fill in the backend entry id on queued actions awaiting it.

        When a timer is started offline, the local session has no entry id yet.
        If the user then stops it, the queued `stop_timer` has nothing to
        identify on the server. Both actions carry the same `client_op`, so once
        the queued `start_timer` succeeds the resulting entry id is written into
        every queued action still waiting for it.

        Without this the stop was sent with `entry_id = None`, which stopped
        nothing and left the entry running on the backend.

        :return: how many queued actions were resolved.
        """
        rows = self._storage.query_all(
            "SELECT id, payload FROM pending_actions "
            "WHERE status IN ('pending', 'retry')",
        )
        resolved = 0
        now = time.time()
        with self._storage.transaction() as conn:
            for row in rows:
                try:
                    payload = json.loads(row["payload"])
                except (json.JSONDecodeError, TypeError):
                    continue
                if payload.get("client_op") != client_op:
                    continue
                # Only actions that *consume* an entry id are resolved. The
                # `start_timer` that produces it has no `entry_id` key at all,
                # and must not be patched with the id it just created.
                if "entry_id" not in payload or payload.get("entry_id"):
                    continue
                payload["entry_id"] = entry_id
                conn.execute(
                    "UPDATE pending_actions SET payload = ?, entity_id = ?, updated_at = ? "
                    "WHERE id = ?",
                    (json.dumps(payload), str(entry_id), now, row["id"]),
                )
                resolved += 1
        if resolved:
            log.info("resolved entry %s onto %d queued action(s)", entry_id, resolved)
        return resolved

    def cancel_actions_for_generation(self, generation: int) -> int:
        """
        Cancel queued work belonging to an earlier session generation.

        Prevents user A's queued operations from being executed with user B's
        credentials after a logout/login.
        """
        cursor = self._storage.execute(
            "UPDATE pending_actions SET status = 'cancelled', error_message = 'stale session' "
            "WHERE session_generation < ? AND status IN ('pending', 'retry', 'processing')",
            (generation,),
        )
        return cursor.rowcount or 0

    # ── Application Usage ─────────────────────────────────────────────────────

    def save_app_usage(
        self,
        time_entry_id: int,
        application_name: str,
        window_title: Optional[str],
        duration_seconds: int,
        recorded_at: str,
    ) -> str:
        record_id = str(uuid.uuid4())
        now = time.time()
        self._storage.execute(
            """INSERT INTO pending_app_usage
               (id, time_entry_id, application_name, window_title, duration_seconds,
                recorded_at, status, retry_count, next_retry_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?)""",
            (record_id, time_entry_id, application_name, window_title,
             duration_seconds, recorded_at, now, now),
        )
        return record_id

    def get_pending_app_usage(self) -> List[Dict[str, Any]]:
        rows = self._storage.query_all(
            """SELECT id, time_entry_id, application_name, window_title,
                      duration_seconds, recorded_at, retry_count
               FROM pending_app_usage
               WHERE status = 'pending' AND next_retry_at <= ?
               ORDER BY created_at ASC""",
            (time.time(),),
        )
        return [dict(row) for row in rows]

    def mark_app_usage_processing(self, ids: List[str]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        self._storage.execute(
            f"UPDATE pending_app_usage SET status = 'processing' WHERE id IN ({placeholders})", ids
        )

    def complete_app_usage(self, ids: List[str]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        self._storage.execute(
            f"DELETE FROM pending_app_usage WHERE id IN ({placeholders})", ids
        )

    def fail_app_usage(self, ids: List[str], error_message: str, max_retries: int = 10) -> None:
        import random

        if not ids:
            return
        now = time.time()
        with self._storage.transaction() as conn:
            for record_id in ids:
                row = conn.execute(
                    "SELECT retry_count FROM pending_app_usage WHERE id = ?", (record_id,)
                ).fetchone()
                if not row:
                    continue
                retry_count = row["retry_count"] + 1
                if retry_count > max_retries:
                    conn.execute(
                        "UPDATE pending_app_usage SET status = 'failed' WHERE id = ?", (record_id,)
                    )
                else:
                    delay = min(2 ** (retry_count - 1), 60) * (0.5 + random.random())
                    conn.execute(
                        "UPDATE pending_app_usage SET status = 'pending', retry_count = ?, "
                        "next_retry_at = ? WHERE id = ?",
                        (retry_count, now + delay, record_id),
                    )

    def reset_processing_app_usage(self) -> None:
        self._storage.execute(
            "UPDATE pending_app_usage SET status = 'pending' WHERE status = 'processing'"
        )

    def clear_app_usage(self) -> None:
        self._storage.execute("DELETE FROM pending_app_usage")

    # ── Activity Samples ──────────────────────────────────────────────────────

    def save_activity_sample(
        self,
        time_entry_id: int,
        window_start: str,
        window_seconds: int,
        active_seconds: int,
        key_events: int = 0,
        mouse_events: int = 0,
        keyboard_strokes: int = 0,
        mouse_clicks: int = 0,
        mouse_movements: int = 0,
        activity_percent: Optional[int] = None,
    ) -> str:
        """
        Persist one aggregated activity window.

        `activity_percent` is stored alongside the raw counts so the value the
        user sees is auditable against the inputs it was derived from.
        `keyboard_strokes`/`mouse_clicks`/`mouse_movements` are true event
        counts from the input hook; `key_events`/`mouse_events` remain the
        original seconds-with-input counters that drive the percentage.
        """
        if activity_percent is not None:
            percent = max(0, min(100, activity_percent))
        elif window_seconds > 0:
            percent = max(0, min(100, round(active_seconds / window_seconds * 100)))
        else:
            percent = 0

        record_id = str(uuid.uuid4())
        now = time.time()
        self._storage.execute(
            """INSERT INTO activity_samples
               (id, time_entry_id, window_start, window_seconds, active_seconds,
                key_events, mouse_events, keyboard_strokes, mouse_clicks, mouse_movements,
                activity_percent, status, retry_count, next_retry_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?)""",
            (record_id, time_entry_id, window_start, window_seconds, active_seconds,
             key_events, mouse_events, keyboard_strokes, mouse_clicks, mouse_movements,
             percent, now, now),
        )
        return record_id

    def get_pending_activity_samples(self) -> List[Dict[str, Any]]:
        rows = self._storage.query_all(
            """SELECT id, time_entry_id, window_start, window_seconds, active_seconds,
                      key_events, mouse_events, keyboard_strokes, mouse_clicks, mouse_movements,
                      activity_percent, retry_count
               FROM activity_samples
               WHERE status = 'pending' AND next_retry_at <= ?
               ORDER BY created_at ASC""",
            (time.time(),),
        )
        return [dict(row) for row in rows]

    def complete_activity_samples(self, ids: List[str]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        self._storage.execute(
            f"DELETE FROM activity_samples WHERE id IN ({placeholders})", ids
        )

    def fail_activity_samples(self, ids: List[str], error_message: str = "", max_retries: int = 10) -> None:
        import random

        if not ids:
            return
        now = time.time()
        with self._storage.transaction() as conn:
            for record_id in ids:
                row = conn.execute(
                    "SELECT retry_count FROM activity_samples WHERE id = ?", (record_id,)
                ).fetchone()
                if not row:
                    continue
                retry_count = row["retry_count"] + 1
                if retry_count > max_retries:
                    conn.execute(
                        "UPDATE activity_samples SET status = 'failed' WHERE id = ?", (record_id,)
                    )
                else:
                    delay = min(2 ** (retry_count - 1), 60) * (0.5 + random.random())
                    conn.execute(
                        "UPDATE activity_samples SET retry_count = ?, next_retry_at = ? "
                        "WHERE id = ?",
                        (retry_count, now + delay, record_id),
                    )

    def get_activity_percent_for_entry(self, time_entry_id: int) -> int:
        """
        Return the duration-weighted activity percentage for a time entry,
        computed from locally captured samples.
        """
        row = self._storage.query_one(
            "SELECT SUM(active_seconds) AS active, SUM(window_seconds) AS total "
            "FROM activity_samples WHERE time_entry_id = ?",
            (time_entry_id,),
        )
        if not row or not row["total"]:
            return 0
        return max(0, min(100, round(row["active"] / row["total"] * 100)))

    def get_day_activity_totals(self, start_utc_iso: str, end_utc_iso: str) -> Dict[str, int]:
        """
        Duration-weighted activity for the windows captured in a UTC range
        that have **not yet been uploaded**.

        These are exactly the windows the backend cannot know about: a sample
        row is deleted here only after its batch upload succeeded, so the
        local queue and the server's rows are disjoint and can be summed
        without double counting. Failed rows are included too — they are real
        measurements that are still waiting on a retry.

        `window_start` is stored as an ISO-8601 UTC string, so the bounds are
        compared on the first 19 characters (``YYYY-MM-DDTHH:MM:SS``); that
        keeps the comparison exact regardless of whether a given row happened
        to carry microseconds.
        """
        row = self._storage.query_one(
            """SELECT COALESCE(SUM(activity_percent * window_seconds), 0) AS weighted,
                      COALESCE(SUM(window_seconds), 0) AS measured
               FROM activity_samples
               WHERE window_seconds > 0
                 AND activity_percent BETWEEN 0 AND 100
                 AND substr(window_start, 1, 19) >= ?
                 AND substr(window_start, 1, 19) < ?""",
            (start_utc_iso[:19], end_utc_iso[:19]),
        )
        if not row:
            return {"weighted": 0, "measured": 0}
        return {
            "weighted": int(row["weighted"] or 0),
            "measured": int(row["measured"] or 0),
        }

    def clear_activity_samples(self) -> None:
        self._storage.execute("DELETE FROM activity_samples")

    # ── Unwanted Activity + Adjustments ──────────────────────────────────────
    #
    # Two small offline queues with the same pending/retry/backoff shape as
    # activity_samples. The row id doubles as the backend's client_event_id,
    # so a retried upload after a lost response can never double-insert an
    # event or -- worst of all -- apply the same deduction twice.

    def save_unwanted_activity(
        self,
        record_id: str,
        time_entry_id: int,
        activity_type: str,
        key_or_action: str,
        occurrence_count: int,
        alerted: bool,
        alert_count: int,
        recorded_at: str,
    ) -> str:
        self._storage.execute(
            """INSERT OR IGNORE INTO pending_unwanted_activity
               (id, time_entry_id, activity_type, key_or_action, occurrence_count,
                alerted, alert_count, recorded_at, status, retry_count,
                next_retry_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?)""",
            (record_id, time_entry_id, activity_type, key_or_action,
             occurrence_count, 1 if alerted else 0, alert_count, recorded_at,
             time.time(), time.time()),
        )
        return record_id

    def get_pending_unwanted_activity(self) -> List[Dict[str, Any]]:
        rows = self._storage.query_all(
            """SELECT id, time_entry_id, activity_type, key_or_action,
                      occurrence_count, alerted, alert_count, recorded_at, retry_count
               FROM pending_unwanted_activity
               WHERE status = 'pending' AND next_retry_at <= ?
               ORDER BY created_at ASC""",
            (time.time(),),
        )
        return [dict(row) for row in rows]

    def complete_unwanted_activity(self, ids: List[str]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        self._storage.execute(
            f"DELETE FROM pending_unwanted_activity WHERE id IN ({placeholders})", ids
        )

    def fail_unwanted_activity(self, ids: List[str], max_retries: int = 10) -> None:
        self._fail_queue_records("pending_unwanted_activity", ids, max_retries)

    def save_adjustment(
        self,
        record_id: str,
        time_entry_id: int,
        adjustment_seconds: int,
        reason: str,
        source_activity_type: Optional[str],
        source_key_or_action: Optional[str],
        source_client_event_id: Optional[str],
        recorded_at: str,
    ) -> str:
        self._storage.execute(
            """INSERT OR IGNORE INTO pending_adjustments
               (id, time_entry_id, adjustment_seconds, reason,
                source_activity_type, source_key_or_action, source_client_event_id,
                recorded_at, status, retry_count, next_retry_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?)""",
            (record_id, time_entry_id, adjustment_seconds, reason,
             source_activity_type, source_key_or_action, source_client_event_id,
             recorded_at, time.time(), time.time()),
        )
        return record_id

    def get_pending_adjustments(self) -> List[Dict[str, Any]]:
        rows = self._storage.query_all(
            """SELECT id, time_entry_id, adjustment_seconds, reason,
                      source_activity_type, source_key_or_action,
                      source_client_event_id, recorded_at, retry_count
               FROM pending_adjustments
               WHERE status = 'pending' AND next_retry_at <= ?
               ORDER BY created_at ASC""",
            (time.time(),),
        )
        return [dict(row) for row in rows]

    def complete_adjustments(self, ids: List[str]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        self._storage.execute(
            f"DELETE FROM pending_adjustments WHERE id IN ({placeholders})", ids
        )

    def fail_adjustments(self, ids: List[str], max_retries: int = 10) -> None:
        self._fail_queue_records("pending_adjustments", ids, max_retries)

    def _fail_queue_records(self, table: str, ids: List[str], max_retries: int) -> None:
        """Shared retry/backoff bookkeeping for the two queues above --
        exponential backoff with jitter, 'failed' after max_retries, same
        contract as fail_activity_samples."""
        import random

        if not ids:
            return
        now = time.time()
        with self._storage.transaction() as conn:
            for record_id in ids:
                row = conn.execute(
                    f"SELECT retry_count FROM {table} WHERE id = ?", (record_id,)
                ).fetchone()
                if not row:
                    continue
                retry_count = row["retry_count"] + 1
                if retry_count > max_retries:
                    conn.execute(
                        f"UPDATE {table} SET status = 'failed' WHERE id = ?", (record_id,)
                    )
                else:
                    delay = min(2 ** (retry_count - 1), 60) * (0.5 + random.random())
                    conn.execute(
                        f"UPDATE {table} SET retry_count = ?, next_retry_at = ? "
                        "WHERE id = ?",
                        (retry_count, now + delay, record_id),
                    )

    # ── URL Usage ─────────────────────────────────────────────────────────────

    def save_url_usage(
        self,
        time_entry_id: int,
        browser_name: str,
        domain: str,
        url: Optional[str],
        page_title: Optional[str],
        duration_seconds: int,
        recorded_at: str,
        client_event_id: Optional[str] = None,
    ) -> str:
        record_id = str(uuid.uuid4())
        event_id = client_event_id or str(uuid.uuid4())
        now = time.time()
        self._storage.execute(
            """INSERT INTO pending_url_usage
               (id, time_entry_id, browser_name, domain, url, page_title,
                duration_seconds, recorded_at, client_event_id, status, retry_count, next_retry_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?)""",
            (record_id, time_entry_id, browser_name, domain, url, page_title,
             duration_seconds, recorded_at, event_id, now, now),
        )
        return record_id

    def get_pending_url_usage(self) -> List[Dict[str, Any]]:
        rows = self._storage.query_all(
            """SELECT id, time_entry_id, browser_name, domain, url, page_title,
                      duration_seconds, recorded_at, client_event_id, retry_count
               FROM pending_url_usage
               WHERE status = 'pending' AND next_retry_at <= ?
               ORDER BY created_at ASC""",
            (time.time(),),
        )
        return [dict(row) for row in rows]

    def mark_url_usage_processing(self, ids: List[str]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        self._storage.execute(
            f"UPDATE pending_url_usage SET status = 'processing' WHERE id IN ({placeholders})", ids
        )

    def complete_url_usage(self, ids: List[str]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        self._storage.execute(
            f"DELETE FROM pending_url_usage WHERE id IN ({placeholders})", ids
        )

    def fail_url_usage(self, ids: List[str], error_message: str = "", max_retries: int = 10) -> None:
        import random

        if not ids:
            return
        now = time.time()
        with self._storage.transaction() as conn:
            for record_id in ids:
                row = conn.execute(
                    "SELECT retry_count FROM pending_url_usage WHERE id = ?", (record_id,)
                ).fetchone()
                if not row:
                    continue
                retry_count = row["retry_count"] + 1
                if retry_count > max_retries:
                    conn.execute(
                        "UPDATE pending_url_usage SET status = 'failed' WHERE id = ?", (record_id,)
                    )
                else:
                    delay = min(2 ** (retry_count - 1), 60) * (0.5 + random.random())
                    conn.execute(
                        "UPDATE pending_url_usage SET status = 'pending', retry_count = ?, next_retry_at = ? "
                        "WHERE id = ?",
                        (retry_count, now + delay, record_id),
                    )

    def reset_processing_url_usage(self) -> int:
        cursor = self._storage.execute(
            "UPDATE pending_url_usage SET status = 'pending' WHERE status = 'processing'"
        )
        return cursor.rowcount or 0

    def clear_url_usage(self) -> None:
        self._storage.execute("DELETE FROM pending_url_usage")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """
        Release this thread's database resources.

        Connection lifetime belongs to the StorageManager; the runtime closes
        it once, last, after all service threads have stopped. This method is
        retained so existing callers remain valid, and is a no-op beyond
        releasing the calling thread's connection.
        """
        self._storage.close_current_thread()
