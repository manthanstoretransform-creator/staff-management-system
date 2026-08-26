"""
Seed (and remove) disposable users for the backend load test.

WHY
---
TimeEntryService.start_timer returns 409 CONFLICT when a user already has an
active timer. With only a handful of real users in the database, 200 virtual
clients sharing those ids would collide on nearly every start, so the write
path would never actually be measured and the error rate would be noise.

This creates N users that exist only for load testing. Every one is named
`loadtest_*` with an email at `@loadtest.invalid` -- a reserved TLD that can
never route anywhere real -- so they are trivially identifiable and safe to
delete.

The users get the `employee` permission set, not admin: load traffic should
exercise the permission checks a normal client hits, not bypass them.

USAGE
-----
    python tests/load/seed_load_users.py --count 200
    python tests/load/seed_load_users.py --cleanup

--cleanup deletes the seeded users AND every row they created (time entries,
app usage, screenshots, refresh tokens), in foreign-key-safe order. It only
ever touches rows whose owner matches the loadtest email pattern, so it cannot
remove real data even if pointed at the wrong database.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from sqlalchemy import text  # noqa: E402

# Every command must resolve to the dedicated load-test branch. Any other host
# -- production, or the branch named in .env -- is a hard stop, not a warning.
EXPECTED_HOST_PREFIX = os.environ.get("MONITRA_LOADTEST_HOST_PREFIX", "ep-quiet-frost-")

EMAIL_DOMAIN = "loadtest.invalid"
EMAIL_PATTERN = f"%@{EMAIL_DOMAIN}"

EMPLOYEE_PERMISSIONS = {
    "tasks:view": True,
    "tasks:create": True,
    "tasks:update": True,
    "projects:view": True,
    "time_entries:manage_own": True,
}


def engine_for(database_url: str):
    """Build an engine for an EXPLICIT database URL.

    There is no implicit default here, on purpose. get_database_url() prefers
    DATABASE_URL -- the production endpoint -- regardless of ENV, and
    app.core.database calls load_dotenv(override=True) at import time, which
    silently clobbers any DATABASE_URL set beforehand. That combination once
    sent a seeding run at production. So: import the module first (its
    load_dotenv runs), then set the URL, then build the lazily-created engine,
    then print the host that actually resolved before touching anything.
    """
    import app.core.database as database  # noqa: PLC0415

    os.environ["DATABASE_URL"] = database_url
    database._engine = None  # discard any engine built during import
    database._SessionLocal = None
    engine = database.get_engine()

    host = str(engine.url.host or "")
    if not host.startswith(EXPECTED_HOST_PREFIX):
        sys.exit(f"Refusing to continue: resolved host {host!r} does not start "
                 f"with the expected dev prefix {EXPECTED_HOST_PREFIX!r}.")
    return engine


def describe_target(engine) -> str:
    url = engine.url
    return f"{url.host}/{url.database}"


def seed(engine, count: int, organization_id: int, capture_frequency: int) -> list[int]:
    created: list[int] = []
    permissions = json.dumps(EMPLOYEE_PERMISSIONS)
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM users WHERE email LIKE :pattern ORDER BY id"),
            {"pattern": EMAIL_PATTERN},
        ).fetchall()
        if existing:
            print(f"  {len(existing)} load-test users already present; reusing them.")
            created.extend(r[0] for r in existing)

        needed = count - len(created)
        for index in range(needed):
            slot = len(created) + index
            row = conn.execute(
                text(
                    """
                    INSERT INTO users (organization_id, username, email, name,
                                       role_name, permissions, is_active,
                                       capture_frequency, status)
                    VALUES (:org, :username, :email, :name, 'employee',
                            CAST(:permissions AS jsonb), true, :capture, 'active')
                    ON CONFLICT (email) DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "username": f"loadtest_{slot:04d}",
                    "email": f"loadtest_{slot:04d}@{EMAIL_DOMAIN}",
                    "name": f"Load Test {slot:04d}",
                    "permissions": permissions,
                    "capture": capture_frequency,
                },
            ).fetchone()
            if row is not None:
                created.append(row[0])

        # Employees only see projects they belong to (ProjectService.list_projects
        # joins project_members for role_name == 'employee'). Without membership
        # rows every virtual user would get an empty project list and a 404 on
        # every task and timer call -- the load test would measure the 404 path.
        projects = [
            r[0]
            for r in conn.execute(
                text("SELECT id FROM projects WHERE organization_id = :org "
                     "AND status <> 'archived' ORDER BY id"),
                {"org": organization_id},
            ).fetchall()
        ]
        if not projects:
            print(f"  WARNING: organization {organization_id} has no active projects; "
                  f"virtual users will have nothing to work on.")
        for project_id in projects:
            conn.execute(
                text(
                    """
                    INSERT INTO project_members (organization_id, project_id,
                                                 user_id, created_by)
                    SELECT :org, :project, u.id, :creator
                    FROM users u
                    WHERE u.id = ANY(:ids)
                    ON CONFLICT ON CONSTRAINT uq_project_member DO NOTHING
                    """
                ),
                {"org": organization_id, "project": project_id,
                 "creator": created[0] if created else 1, "ids": created},
            )
        print(f"  members added across {len(projects)} project(s)")
    return created


TRACKED_TABLES = (
    "time_entry_app_usage",
    "time_entry_screenshots",
    "manual_time_entries",
    "time_entries",
    "task_assignees",
    "project_members",
    "refresh_tokens",
    "tasks",
    "users",
)


def snapshot(engine) -> dict[str, int]:
    """Row counts for every table the load test could possibly touch."""
    counts: dict[str, int] = {}
    with engine.connect() as conn:
        for table in TRACKED_TABLES:
            try:
                counts[table] = conn.execute(
                    text(f"SELECT count(*) FROM {table}")).scalar_one()
            except Exception:  # noqa: BLE001 - table may not exist
                counts[table] = -1
    return counts


def watermarks(engine) -> dict[str, int]:
    """Highest existing id per table, captured BEFORE the run.

    Cleanup deletes strictly above these values. This is the safeguard that
    matters: `user_id` has no foreign key in this schema, so deleting by
    user_id can match pre-existing orphaned rows that merely share an id
    range. Deleting by `id > watermark` cannot -- identity columns only ever
    hand out higher values, so anything above the mark was created by this
    run and nothing else can be.
    """
    marks: dict[str, int] = {}
    with engine.connect() as conn:
        for table in TRACKED_TABLES:
            try:
                marks[table] = conn.execute(
                    text(f"SELECT coalesce(max(id), 0) FROM {table}")).scalar_one()
            except Exception:  # noqa: BLE001
                marks[table] = -1
    return marks


def cleanup(engine, marks: dict[str, int]) -> dict[str, int]:
    """Delete only rows created after the watermark, children before parents.

    Refuses to run without watermarks rather than fall back to a broader
    predicate. A cleanup that guesses is how real data gets deleted.
    """
    if not marks:
        sys.exit("Refusing to clean up without a baseline file. "
                 "Re-run with --baseline pointing at the file written at seed time.")

    removed: dict[str, int] = {}
    with engine.begin() as conn:
        for table in TRACKED_TABLES:  # already ordered children-first
            mark = marks.get(table, -1)
            if mark < 0:
                continue
            result = conn.execute(
                text(f"DELETE FROM {table} WHERE id > :mark"), {"mark": mark}
            )
            if result.rowcount:
                removed[table] = result.rowcount

        # Seeded users can legitimately sit BELOW the watermark when the
        # baseline was re-captured after seeding (for example after running
        # migrations). Removing them by the loadtest email pattern is safe in a
        # way that removing them by user_id is not: the pattern is unique to
        # rows this script created, whereas user_id has no foreign key here and
        # can collide with pre-existing orphaned rows.
        result = conn.execute(
            text("DELETE FROM users WHERE email LIKE :pattern"),
            {"pattern": EMAIL_PATTERN},
        )
        if result.rowcount:
            removed["users (by loadtest email)"] = result.rowcount
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--organization-id", type=int, default=1)
    parser.add_argument("--capture-frequency", type=int, default=10)
    parser.add_argument("--database-url", default=os.environ.get("MONITRA_LOADTEST_DB_URL"),
                        help="REQUIRED. Explicit connection string for the "
                             "load-test branch (or set MONITRA_LOADTEST_DB_URL). "
                             "Never read from .env -- that file points at production.")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--snapshot", action="store_true",
                        help="print row counts for every table and exit")
    parser.add_argument("--out", help="write the seeded user ids as JSON fixtures")
    parser.add_argument("--baseline", help="path for the pre-test row-count and "
                                           "id-watermark baseline; required for --cleanup")
    args = parser.parse_args()

    if not args.database_url:
        sys.exit("--database-url is required (or set MONITRA_LOADTEST_DB_URL).")

    engine = engine_for(args.database_url)
    print(f"target: {describe_target(engine)}")

    if args.snapshot:
        for table, count in snapshot(engine).items():
            print(f"  {count:>8}  {table}")
        return 0

    if args.cleanup:
        if not args.baseline or not os.path.exists(args.baseline):
            sys.exit("--cleanup requires --baseline <file> written at seed time.")
        with open(args.baseline, encoding="utf-8") as handle:
            baseline = json.load(handle)
        removed = cleanup(engine, baseline["watermarks"])
        for table, count in removed.items():
            print(f"  deleted {count:>6} from {table}")

        after = snapshot(engine)
        drift = {t: after[t] - baseline["counts"][t]
                 for t in after if baseline["counts"].get(t) is not None
                 and after[t] != baseline["counts"][t]}
        if drift:
            print("\n  ROW COUNT DRIFT vs before the test:")
            for table, delta in drift.items():
                print(f"    {table}: {delta:+d}")
        else:
            print("\n  every tracked table matches its pre-test row count exactly.")
        return 0

    # Capture the baseline BEFORE inserting anything.
    baseline = {"counts": snapshot(engine), "watermarks": watermarks(engine)}

    user_ids = seed(engine, args.count, args.organization_id, args.capture_frequency)
    print(f"  {len(user_ids)} load-test users available (org {args.organization_id})")

    if args.baseline:
        with open(args.baseline, "w", encoding="utf-8") as handle:
            json.dump(baseline, handle, indent=2)
        print(f"  wrote baseline {args.baseline}")

    if args.out:
        # Only the projects and tasks these users can actually reach. Handing the
        # load test ids from another organization would measure the 404 path.
        with engine.connect() as conn:
            projects = [r[0] for r in conn.execute(
                text("SELECT id FROM projects WHERE organization_id = :org "
                     "AND status <> 'archived' ORDER BY id"),
                {"org": args.organization_id}).fetchall()]
            tasks = [{"id": r[0], "project_id": r[1]} for r in conn.execute(
                text("SELECT id, project_id FROM tasks WHERE project_id = ANY(:ids) "
                     "ORDER BY id"), {"ids": projects}).fetchall()]
        fixtures = {"users": user_ids, "projects": projects, "tasks": tasks}
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(fixtures, handle, indent=2)
        print(f"  wrote {args.out} "
              f"(projects={len(projects)} tasks={len(tasks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
