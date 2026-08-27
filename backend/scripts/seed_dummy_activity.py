"""
Dummy test-data seeder: time_entry_activity (dev DB only).

time_entry_activity has no writer in the real app yet -- the desktop's
activity batch-sync endpoint doesn't exist (CLAUDE.md Known open items #1),
so every time_entries row currently has zero activity samples and the
frontend's activity % always renders empty/0. This script backfills
realistic activity samples for every existing time_entries row in
organization_id=1 (both the [SEED] dummy entries and the handful of real
ones) purely so the frontend has something to render while testing --
it does not change how the real app computes or ingests activity.

For each time_entries row, inserts one sample every ~10 minutes of its
duration (at least 1, capped at 8 per entry), each with a per-entry baseline
activity_percentage (jittered per-sample) plus plausible keyboard/mouse
counts, so both within-entry and across-entry variation look real.

Idempotent: skips any time_entries row that already has an activity sample
(the table is empty today, but a re-run after this script has already run
will add samples only for entries that still have none).

Run from backend/:  python scripts/seed_dummy_activity.py
"""
import os
import sys
import random
from datetime import timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_session_local, describe_url, get_database_url
from app.models.time_entry_activity import TimeEntryActivity
from sqlalchemy import insert, text

ORG_ID = 1
SEED = 20260828
random.seed(SEED)

SAMPLE_INTERVAL_SECONDS = 10 * 60
MAX_SAMPLES_PER_ENTRY = 8


def main():
    print("DB target:", describe_url(get_database_url()))
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        total = run(db)
        db.commit()
        print(f"Done, committed {total} time_entry_activity rows.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


BATCH_SIZE = 1000


def run(db) -> int:
    entries = db.execute(text("""
        select te.id, te.organization_id, te.start_time, te.end_time, te.total_seconds
        from time_entries te
        where te.organization_id = :org
          and te.id not in (select distinct time_entry_id from time_entry_activity)
        order by te.id
    """), {"org": ORG_ID}).fetchall()
    print(f"{len(entries)} time_entries with no activity samples yet.")

    rows = []
    for entry in entries:
        duration = max(entry.total_seconds or 0, 60)  # at least one minute of spread
        sample_count = min(MAX_SAMPLES_PER_ENTRY, max(1, duration // SAMPLE_INTERVAL_SECONDS))
        # a per-entry baseline so one person's whole session reads consistently
        # productive/idle, with per-sample jitter on top for realism
        baseline = random.randint(35, 95)

        for i in range(sample_count):
            offset = int(duration * (i + 1) / (sample_count + 1))
            recorded_at = entry.start_time + timedelta(seconds=offset)
            activity_pct = max(0, min(100, baseline + random.randint(-12, 12)))
            # roughly scale input counts with how "active" this sample was
            scale = activity_pct / 100
            rows.append({
                "organization_id": entry.organization_id, "time_entry_id": entry.id, "recorded_at": recorded_at,
                "keyboard_strokes": int(random.randint(50, 400) * scale),
                "mouse_clicks": int(random.randint(10, 120) * scale),
                "mouse_movements": int(random.randint(100, 900) * scale),
                "activity_percentage": activity_pct,
            })

    # A single Core insert() against a list of dicts lets SQLAlchemy 2.0's
    # "insertmanyvalues" batch each chunk into one real multi-row
    # `VALUES (...), (...), ...` statement -- one round trip per batch,
    # not one round trip per row (which is what psycopg2's executemany
    # does for a raw text() DML statement, and why the first version of
    # this script was still crawling despite "batching" in Python).
    stmt = insert(TimeEntryActivity)
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        db.execute(stmt, batch)
        print(f"  inserted {min(start + BATCH_SIZE, len(rows))}/{len(rows)}", flush=True)

    return len(rows)


if __name__ == "__main__":
    main()
