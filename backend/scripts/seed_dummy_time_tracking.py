"""
Dummy test-data seeder: Project Management + Time Tracking (dev DB only).

Populates 20 real, currently task-less projects in organization_id=1 with:
  - a project leader, cycled across the org's 4 'leader' users + 1 'admin' user
    (org_id=1 only has 5 such users, so leadership repeats every 5 projects --
    see docs/Database_Documentation.md "users" table for the current role mix)
  - project_members drawn from all active employees, round-robined so every
    employee shows up on several projects rather than a handful hogging all of them
  - 4-6 tasks per project with varied statuses, due dates and estimates
  - task_assignees drawn from each project's members (1-3 people per task)
  - time_entries for "today" and the past 30 days, on a random subset of each
    assignee's workdays (nobody logs time literally every single day)
  - a few manual_time_entries per project in varied approval states

Every row this script creates is tagged "[SEED]" in its description so it can
be identified or cleaned up later. Uses get_database_url() from
app.core.database, so it follows the same explicit-env > production > dev
resolution as the app itself -- run it with the same environment you'd run
the backend in locally (DATABASE_URL_DEV in backend/.env), not against
production.

Run from backend/:  python scripts/seed_dummy_time_tracking.py
"""
import os
import sys
import random
from datetime import date, datetime, timedelta, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_session_local, describe_url, get_database_url
from sqlalchemy import text

ORG_ID = 1
SEED = 20260827  # fixed seed so re-running (after a wipe) reproduces the same data
random.seed(SEED)

PROJECT_COUNT = 20

TASK_TEMPLATES = [
    "Requirement analysis", "UI/UX design review", "Backend API implementation",
    "Frontend integration", "Database schema update", "Bug fixing - {area}",
    "Code review", "QA testing", "Client feedback revisions", "Deployment & release",
    "Performance optimization", "Documentation update", "Third-party API integration",
    "Security audit", "Staging environment setup", "Content migration",
    "Cross-browser testing", "SEO optimization", "Sprint planning", "Production hotfix",
]
AREAS = ["checkout", "login", "dashboard", "reports", "search", "cart", "profile", "sync"]

PROJECT_STATUS_IDS = {"active": 1, "pending": 2, "todo": 3, "completed": 4}
TASK_STATUS_IDS = {"todo": 1, "in_progress": 2, "completed": 3}  # 'archived' has no lookup row


def main():
    print("DB target:", describe_url(get_database_url()))
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        run(db)
        db.commit()
        print("Done, committed.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run(db):
    users = db.execute(text(
        "select id, role_name from users where organization_id=:org "
        "and is_active=true and status='active'"
    ), {"org": ORG_ID}).fetchall()
    leaders = [u.id for u in users if u.role_name in ("leader", "admin")]
    employees = [u.id for u in users if u.role_name == "employee"]
    if not leaders or not employees:
        raise RuntimeError("Expected leader/admin and employee users in organization_id=1")
    print(f"Leader/admin pool: {len(leaders)} users. Employee pool: {len(employees)} users.")

    candidates = db.execute(text("""
        select id, project_name, is_billable
        from projects
        where organization_id = :org
          and id not in (select distinct project_id from tasks)
          and project_name not ilike '%test%'
        order by id
    """), {"org": ORG_ID}).fetchall()
    if len(candidates) < PROJECT_COUNT:
        raise RuntimeError(f"Only {len(candidates)} eligible task-less, non-test projects found")

    step = len(candidates) // PROJECT_COUNT
    chosen = [candidates[i * step] for i in range(PROJECT_COUNT)]

    today = date.today()

    emp_cycle = employees[:]
    random.shuffle(emp_cycle)
    emp_pos = 0

    people_used = set()
    total_tasks = total_assignees = total_entries = total_manual = 0
    time_entry_pairs = []  # (task_id, user_id, project_id, is_billable)

    for i, proj in enumerate(chosen):
        leader_id = leaders[i % len(leaders)]
        people_used.add(leader_id)

        status = random.choices(
            ["active", "active", "active", "pending", "todo", "completed"], k=1
        )[0]
        db.execute(text("""
            update projects set leader_id=:l, status=:s, status_id=:sid where id=:id
        """), {"l": leader_id, "s": status, "sid": PROJECT_STATUS_IDS[status], "id": proj.id})

        member_count = random.randint(5, 8)
        members = []
        for _ in range(member_count):
            members.append(emp_cycle[emp_pos % len(emp_cycle)])
            emp_pos += 1
        members = list(dict.fromkeys(members))  # de-dupe if the cycle wrapped
        people_used.update(members)
        for uid in members:
            db.execute(text("""
                insert into project_members (organization_id, project_id, user_id, created_by)
                values (:org, :pid, :uid, :creator)
                on conflict (project_id, user_id) do nothing
            """), {"org": ORG_ID, "pid": proj.id, "uid": uid, "creator": leader_id})

        task_count = random.randint(4, 6)
        task_names = random.sample(TASK_TEMPLATES, k=task_count)
        project_task_ids = []

        for name in task_names:
            if "{area}" in name:
                name = name.format(area=random.choice(AREAS))
            t_status = random.choices(
                ["todo", "in_progress", "completed", "archived"], weights=[3, 3, 3, 1], k=1
            )[0]
            assignee_for_task = random.choice(members)
            start_offset = random.randint(0, 20)
            start_date = today - timedelta(days=start_offset)
            due_date = start_date + timedelta(days=random.randint(3, 21))

            task_id = db.execute(text("""
                insert into tasks (
                    organization_id, project_id, task_name, description, status, status_id,
                    assignee_id, start_date, due_date, estimated_hours, created_by
                ) values (
                    :org, :pid, :name, :desc, :status, :status_id,
                    :assignee, :start_date, :due_date, :hours, :creator
                ) returning id
            """), {
                "org": ORG_ID, "pid": proj.id, "name": name,
                "desc": f"[SEED] Dummy test task for {proj.project_name}",
                "status": t_status, "status_id": TASK_STATUS_IDS.get(t_status),
                "assignee": assignee_for_task,
                "start_date": start_date, "due_date": due_date,
                "hours": round(random.uniform(2, 24), 2),
                "creator": leader_id,
            }).scalar_one()
            project_task_ids.append(task_id)
            total_tasks += 1

            assignees = set(random.sample(members, k=min(len(members), random.randint(1, 3))))
            assignees.add(assignee_for_task)
            for uid in assignees:
                db.execute(text("""
                    insert into task_assignees (task_id, user_id, assigned_by)
                    values (:tid, :uid, :by)
                    on conflict (task_id, user_id) do nothing
                """), {"tid": task_id, "uid": uid, "by": leader_id})
                total_assignees += 1
                people_used.add(uid)
                time_entry_pairs.append((task_id, uid, proj.id, proj.is_billable))

        # a few manual_time_entries per project, varied approval state
        for _ in range(random.randint(1, 3)):
            task_id = random.choice(project_task_ids)
            user_id = random.choice(members)
            d = today - timedelta(days=random.randint(0, 30))
            start_dt = datetime(d.year, d.month, d.day, 9, 0, tzinfo=timezone.utc)
            secs = random.randint(3600, 8 * 3600)
            end_dt = start_dt + timedelta(seconds=secs)
            approval = random.choices(["approved", "pending", "rejected"], weights=[6, 3, 1], k=1)[0]
            db.execute(text("""
                insert into manual_time_entries (
                    organization_id, user_id, project_id, task_id, work_date,
                    start_time, end_time, total_seconds, description, is_billable,
                    approval_status, approved_by, approved_at
                ) values (
                    :org, :uid, :pid, :tid, :wd, :start, :end, :secs, :desc, :billable,
                    :appr, :approved_by, :approved_at
                )
            """), {
                "org": ORG_ID, "uid": user_id, "pid": proj.id, "tid": task_id, "wd": d,
                "start": start_dt, "end": end_dt, "secs": secs,
                "desc": "[SEED] Dummy manual time entry", "billable": proj.is_billable,
                "appr": approval,
                "approved_by": leader_id if approval != "pending" else None,
                "approved_at": (start_dt + timedelta(hours=2)) if approval != "pending" else None,
            })
            total_manual += 1

        print(f"  project {proj.id} ({proj.project_name}): leader={leader_id}, "
              f"members={len(members)}, tasks={len(project_task_ids)}")

    # time_entries: today + past 30 days, on a random subset of each pair's workdays
    for task_id, user_id, project_id, is_billable in time_entry_pairs:
        work_days = random.randint(6, 14)
        days = random.sample(range(0, 31), k=min(work_days, 31))
        for offset in days:
            d = today - timedelta(days=offset)
            if d.weekday() >= 5 and random.random() < 0.8:
                continue  # mostly skip weekends
            start_hour = random.randint(9, 16)
            start_minute = random.choice([0, 15, 30, 45])
            start_dt = datetime(d.year, d.month, d.day, start_hour, start_minute, tzinfo=timezone.utc)
            duration_seconds = random.randint(20 * 60, 4 * 3600)
            end_dt = start_dt + timedelta(seconds=duration_seconds)
            db.execute(text("""
                insert into time_entries (
                    organization_id, user_id, project_id, task_id,
                    start_time, end_time, total_seconds, status,
                    is_manual, is_billable, description
                ) values (
                    :org, :uid, :pid, :tid, :start, :end, :secs, 'stopped',
                    :manual, :billable, :desc
                )
            """), {
                "org": ORG_ID, "uid": user_id, "pid": project_id, "tid": task_id,
                "start": start_dt, "end": end_dt, "secs": duration_seconds,
                "manual": random.random() < 0.15,
                "billable": is_billable,
                "desc": "[SEED] Dummy tracked time",
            })
            total_entries += 1

    # keep the denormalized rollups in sync (CLAUDE.md dev rule #6)
    db.execute(text("""
        update tasks t set time_tracked_seconds = coalesce((
            select sum(te.total_seconds) from time_entries te where te.task_id = t.id
        ), 0)
        where t.id in (select task_id from time_entries)
    """))
    db.execute(text("""
        update projects p set time_tracked_seconds = coalesce((
            select sum(te.total_seconds) from time_entries te where te.project_id = p.id
        ), 0)
        where p.id in (select project_id from time_entries)
    """))

    print(f"\nTotals: projects={len(chosen)}, tasks={total_tasks}, "
          f"task_assignees={total_assignees}, time_entries={total_entries}, "
          f"manual_time_entries={total_manual}")
    print(f"Distinct people used (leaders + members + assignees): "
          f"{len(people_used)} / {len(leaders) + len(employees)} active org users")


if __name__ == "__main__":
    main()
