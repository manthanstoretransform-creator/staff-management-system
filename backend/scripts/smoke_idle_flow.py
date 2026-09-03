"""
End-to-end smoke test for the Idle Time + Reassign Time module.

Drives the real HTTP API against the real (dev/Neon) database and prints, for
every scenario, the number the database actually holds -- so the four idle
conditions and the reassignment can be verified rather than assumed.

It does NOT use the unit-test mocks: every row here is a genuine time entry,
idle period and adjustment written through the API.

Usage, from backend/ with the server already running:

    python -m uvicorn app.main:app --reload --port 8000     # terminal 1
    python scripts/smoke_idle_flow.py                        # terminal 2
    python scripts/smoke_idle_flow.py --cleanup              # remove its rows

Options:
    --base-url URL    API root (default http://127.0.0.1:8000)
    --user-id N       Which user to act as (default: first active employee in
                      the org who is a member of at least two projects that
                      each have a task)
    --cleanup         Delete every row this script has ever created and exit.

Every row it writes is tagged [IDLE-SMOKE] in its description, so --cleanup
can find them and nothing else is touched. Resolution of an idle period is
authenticated as the chosen user with a locally minted token, exactly as the
desktop would be.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import text

from app.core.database import describe_url, get_database_url, get_session_local
from app.core.security import create_access_token

TAG = "[IDLE-SMOKE]"
UTC = timezone.utc


# ----------------------------------------------------------------------
# Output helpers
# ----------------------------------------------------------------------

def heading(text_):
    print(f"\n{'=' * 72}\n{text_}\n{'=' * 72}")


def check(label, actual, expected):
    ok = actual == expected
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}: got {actual!r}, expected {expected!r}")
    return ok


# ----------------------------------------------------------------------
# Database helpers (read-back verification + fixture discovery)
# ----------------------------------------------------------------------

def pick_actor(db):
    """An active user who can reach at least two projects that have tasks --
    one to track against, one to reassign idle time to."""
    row = db.execute(text("""
        SELECT u.id, u.name, u.organization_id, u.idle_enabled, u.idle_minutes
        FROM users u
        WHERE u.is_active
          AND EXISTS (
              SELECT 1 FROM project_members pm
              JOIN projects p ON p.id = pm.project_id AND p.status <> 'archived'
              JOIN tasks t ON t.project_id = p.id AND t.status <> 'archived'
              WHERE pm.user_id = u.id
              GROUP BY pm.user_id HAVING COUNT(DISTINCT p.id) >= 2
          )
        ORDER BY u.id
        LIMIT 1
    """)).first()
    return row


def adjustments_for(db, entry_id):
    return db.execute(text(
        "SELECT COALESCE(SUM(adjustment_seconds), 0) FROM time_entry_adjustments "
        "WHERE time_entry_id = :e"
    ), {"e": entry_id}).scalar() or 0


def entry_row(db, entry_id):
    return db.execute(text(
        "SELECT total_seconds, end_time, status, project_id, task_id "
        "FROM time_entries WHERE id = :e"
    ), {"e": entry_id}).mappings().first()


def idle_row(db, idle_id):
    return db.execute(text(
        "SELECT status, counted, keep_idle_time, action, idle_duration_seconds, "
        "reassigned, reassigned_seconds, reassigned_time_entry_id "
        "FROM time_entry_idle_periods WHERE id = :i"
    ), {"i": idle_id}).mappings().first()


# ----------------------------------------------------------------------
# API client
# ----------------------------------------------------------------------

class Api:
    def __init__(self, base_url, user_id):
        self.user_id = user_id
        token = create_access_token({"user_id": user_id})
        self.c = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    def _call(self, method, path, expect=None, **kw):
        r = self.c.request(method, path, **kw)
        if expect is not None and r.status_code != expect:
            raise SystemExit(
                f"{method} {path} -> {r.status_code} (expected {expect}): {r.text}"
            )
        return r

    def me(self):
        return self._call("GET", "/auth/me", 200).json()

    def idle_config(self):
        return self._call("GET", "/idle-periods/config", 200).json()

    def projects(self):
        return self._call("GET", "/projects", 200).json()

    def tasks(self, project_id):
        return self._call("GET", f"/projects/{project_id}/tasks", 200).json()

    def active_entry(self):
        """The caller's OWN running entry. A privileged user (manager, admin)
        sees the whole organization's entries from this endpoint, and stopping
        somebody else's timer is both wrong and a 404 -- so filter to self."""
        entries = self._call("GET", "/time-entries", 200, params={
            "status": "running", "user_id": self.user_id,
        }).json()
        mine = [e for e in entries if e["user_id"] == self.user_id]
        return mine[0] if mine else None

    def start(self, project_id, task_id, started_at):
        return self._call("POST", "/time-entries/start", 201, json={
            "project_id": project_id, "task_id": task_id,
            "description": f"{TAG} tracked work",
            "started_at": started_at.isoformat(),
        }).json()

    def stop(self, entry_id, stopped_at=None, expect=200):
        body = {"stopped_at": (stopped_at or datetime.now(UTC)).isoformat()}
        return self._call("POST", f"/time-entries/{entry_id}/stop", expect, json=body)

    def report_idle(self, entry_id, started, detected, key=None, expect=201):
        body = {
            "time_entry_id": entry_id,
            "idle_started_at": started.isoformat(),
            "idle_detected_at": detected.isoformat(),
        }
        if key:
            body["client_event_id"] = key
        return self._call("POST", "/idle-periods", expect, json=body)

    def resolve(self, idle_id, keep, action, resolved_at=None, expect=200):
        return self._call("POST", f"/idle-periods/{idle_id}/resolve", expect, json={
            "keep_idle_time": keep, "action": action,
            "resolved_at": (resolved_at or datetime.now(UTC)).isoformat(),
        })

    def reassign(self, idle_id, project_id, task_id, expect=200):
        return self._call("POST", f"/idle-periods/{idle_id}/reassign", expect, json={
            "project_id": project_id, "task_id": task_id,
        })

    def time_tracking_today(self, employee_id):
        return self._call(
            "GET", f"/api/v1/time-tracking/{employee_id}", 200, params={"range": "today"}
        ).json()


# ----------------------------------------------------------------------
# Scenario driver
# ----------------------------------------------------------------------

class Runner:
    """Each scenario starts a fresh timer backdated 30 minutes, so a 20-minute
    idle period ending "now" is genuine rather than simulated."""

    IDLE_SECONDS = 1200  # 20 minutes: idle_started -> resolved

    def __init__(self, api, db, project, task, dest_project, dest_task):
        self.api, self.db = api, db
        self.project, self.task = project, task
        self.dest_project, self.dest_task = dest_project, dest_task
        self.results = []

    def _fresh_timer(self):
        active = self.api.active_entry()
        if active:
            self.api.stop(active["id"])
        now = datetime.now(UTC)
        entry = self.api.start(self.project["id"], self.task["id"], now - timedelta(minutes=30))
        # idle_started 20 min ago, threshold crossed 10 min ago, answered now.
        return entry, now - timedelta(minutes=20), now - timedelta(minutes=10), now

    def _record(self, name, checks):
        passed = all(checks)
        self.results.append((name, passed))
        print(f"  -> {name}: {'PASS' if passed else 'FAIL'}")

    def condition(self, name, keep, action, expect_counted):
        heading(name)
        entry, idle_started, detected, now = self._fresh_timer()
        idle = self.api.report_idle(entry["id"], idle_started, detected).json()
        print(f"  entry={entry['id']} idle_period={idle['id']} status={idle['status']}")

        self.api.resolve(idle["id"], keep, action, now)
        self.db.commit()  # see the API's committed rows

        row = idle_row(self.db, idle["id"])
        adj = adjustments_for(self.db, entry["id"])
        entry_now = entry_row(self.db, entry["id"])

        checks = [
            check("idle period resolved", row["status"], "resolved"),
            check("server counted decision", row["counted"], expect_counted),
            check("actual idle duration (not the 5-min threshold)",
                  row["idle_duration_seconds"], self.IDLE_SECONDS),
            check("deduction on the original entry", adj,
                  0 if expect_counted else -self.IDLE_SECONDS),
            check("timer stopped?", entry_now["end_time"] is not None, action == "stop"),
            check("total_seconds never edited by the idle rules",
                  entry_now["total_seconds"] == 0 or action == "stop", True),
        ]
        if action == "resume":
            self.api.stop(entry["id"])
        self._record(name, checks)

    def reassignment(self):
        heading("REASSIGN: idle time moves to another project/task, counted once")
        entry, idle_started, detected, now = self._fresh_timer()
        idle = self.api.report_idle(entry["id"], idle_started, detected).json()

        # A task that belongs to a DIFFERENT project must be refused.
        self.api.reassign(idle["id"], self.dest_project["id"], self.task["id"], expect=404)
        print("  [PASS] task from another project rejected (404)")

        result = self.api.reassign(
            idle["id"], self.dest_project["id"], self.dest_task["id"]
        ).json()
        self.db.commit()

        moved = result["reassigned_seconds"]
        dest_entry = entry_row(self.db, result["reassigned_time_entry_id"])
        original = entry_row(self.db, entry["id"])
        adj = adjustments_for(self.db, entry["id"])

        checks = [
            check("destination project", dest_entry["project_id"], self.dest_project["id"]),
            check("destination task", dest_entry["task_id"], self.dest_task["id"]),
            check("destination carries the idle seconds", dest_entry["total_seconds"], moved),
            check("same seconds deducted from the original", adj, -moved),
            check("original entry NOT re-pointed", original["project_id"], self.project["id"]),
            check("original task NOT re-pointed", original["task_id"], self.task["id"]),
            check("idle period still pending for the main popup",
                  result["status"], "pending"),
        ]

        # Duplicate reassignment must be refused.
        self.api.reassign(idle["id"], self.dest_project["id"], self.dest_task["id"], expect=409)
        print("  [PASS] duplicate reassignment rejected (409)")

        # Answer the main popup: keep + resume. The reassigned seconds must not
        # be deducted a second time; only the residual follows the rule.
        self.api.resolve(idle["id"], True, "resume", now)
        self.db.commit()
        adj_after = adjustments_for(self.db, entry["id"])
        checks.append(check("no second deduction after resolution", adj_after, -moved))

        self.api.stop(entry["id"])
        self._record("REASSIGN", checks)

    def stop_while_pending(self):
        heading("STOP while an idle period is still pending -> discarded, never banked")
        entry, idle_started, detected, now = self._fresh_timer()
        idle = self.api.report_idle(entry["id"], idle_started, detected).json()

        self.api.stop(entry["id"], now)   # straight to Stop, popup never answered
        self.db.commit()

        row = idle_row(self.db, idle["id"])
        checks = [
            check("pending period auto-resolved", row["status"], "resolved"),
            check("resolved as discarded", row["counted"], False),
            check("recorded as a stop", row["action"], "stop"),
            check("idle seconds deducted", adjustments_for(self.db, entry["id"]),
                  -self.IDLE_SECONDS),
        ]
        self._record("STOP-WHILE-PENDING", checks)

    def idempotency(self):
        heading("IDEMPOTENCY: duplicate reports, double-clicked Resume")
        entry, idle_started, detected, now = self._fresh_timer()

        first = self.api.report_idle(entry["id"], idle_started, detected, key="smoke-evt-1").json()
        again = self.api.report_idle(entry["id"], idle_started, detected, key="smoke-evt-1").json()
        no_key = self.api.report_idle(entry["id"], idle_started, detected).json()
        checks = [
            check("retry with the same client_event_id returns the same period",
                  again["id"], first["id"]),
            check("a second report while one is pending returns the same period",
                  no_key["id"], first["id"]),
        ]

        self.api.resolve(first["id"], False, "resume", now)
        self.db.commit()
        adj_once = adjustments_for(self.db, entry["id"])

        self.api.resolve(first["id"], False, "resume", now)          # double click
        self.db.commit()
        checks.append(check("double-clicked Resume does not deduct twice",
                            adjustments_for(self.db, entry["id"]), adj_once))

        # A different answer to an already-resolved period is a conflict.
        self.api.resolve(first["id"], True, "resume", now, expect=409)
        print("  [PASS] changing the answer after resolution rejected (409)")

        self.api.stop(entry["id"])
        self._record("IDEMPOTENCY", checks)

    def reporting_surface(self, employee_id):
        heading("REPORTING: the deductions are visible in time-tracking")
        detail = self.api.time_tracking_today(employee_id)
        print(f"  today's net tracked time: {detail['summary']['total_time']} "
              f"({detail['summary']['total_seconds']}s across "
              f"{len(detail['projects'])} project(s))")
        print("  (this figure nets time_entry_adjustments, so discarded and "
              "reassigned idle time is already excluded)")


# ----------------------------------------------------------------------
# Cleanup
# ----------------------------------------------------------------------

def cleanup(db):
    ids = [r[0] for r in db.execute(text(
        "SELECT id FROM time_entries WHERE description LIKE :tag"
    ), {"tag": f"%{TAG}%"}).all()]
    reassigned = [r[0] for r in db.execute(text(
        "SELECT reassigned_time_entry_id FROM time_entry_idle_periods "
        "WHERE time_entry_id = ANY(:ids) AND reassigned_time_entry_id IS NOT NULL"
    ), {"ids": ids or [0]}).all()]
    all_ids = list({*ids, *reassigned})
    if not all_ids:
        print("Nothing tagged to clean up.")
        return
    # Idle periods and adjustments cascade from time_entries.
    db.execute(text("DELETE FROM time_entries WHERE id = ANY(:ids)"), {"ids": all_ids})
    db.commit()
    print(f"Deleted {len(all_ids)} tagged time entries (idle periods and "
          f"adjustments cascade).")


# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--user-id", type=int)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()

    print(f"database: {describe_url(get_database_url())}")
    db = get_session_local()()

    if args.cleanup:
        cleanup(db)
        return

    if args.user_id:
        actor = db.execute(text(
            "SELECT id, name, organization_id, idle_enabled, idle_minutes "
            "FROM users WHERE id = :i"
        ), {"i": args.user_id}).first()
    else:
        actor = pick_actor(db)
    if not actor:
        raise SystemExit(
            "No suitable user found. Pass --user-id, or seed data first with "
            "scripts/seed_dummy_time_tracking.py."
        )
    print(f"acting as user {actor.id} ({actor.name}), "
          f"idle_enabled={actor.idle_enabled} idle_minutes={actor.idle_minutes}")
    if not actor.idle_enabled:
        raise SystemExit("This user has idle detection disabled; pick another --user-id.")
    if actor.idle_minutes > 10:
        raise SystemExit(
            f"idle_minutes={actor.idle_minutes} is larger than this script's "
            "10-minute simulated gap; pick a user with a smaller threshold."
        )

    api = Api(args.base_url, actor.id)
    print(f"GET /idle-periods/config -> {api.idle_config()}")

    # Two projects the user is genuinely authorized for, each with a task.
    usable = []
    for project in api.projects():
        tasks = api.tasks(project["id"])
        if tasks:
            usable.append((project, tasks[0]))
        if len(usable) == 2:
            break
    if len(usable) < 2:
        raise SystemExit("Need two authorized projects that have tasks.")
    (project, task), (dest_project, dest_task) = usable
    print(f"tracking against  : {project['project_name']} / {task['task_name']}")
    print(f"reassigning to    : {dest_project['project_name']} / {dest_task['task_name']}")

    r = Runner(api, db, project, task, dest_project, dest_task)
    r.condition("CONDITION 1: No, discard + Stop   -> NOT counted", False, "stop", False)
    r.condition("CONDITION 2: No, discard + Resume -> NOT counted", False, "resume", False)
    r.condition("CONDITION 3: Yes, keep + Stop     -> NOT counted", True, "stop", False)
    r.condition("CONDITION 4: Yes, keep + Resume   -> COUNTED", True, "resume", True)
    r.reassignment()
    r.stop_while_pending()
    r.idempotency()
    r.reporting_surface(actor.id)

    heading("SUMMARY")
    for name, passed in r.results:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    failed = [n for n, ok in r.results if not ok]
    print(f"\n{len(r.results) - len(failed)}/{len(r.results)} scenarios passed.")
    print("Run with --cleanup to delete the rows this script created.")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
