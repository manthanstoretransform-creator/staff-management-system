import os
import sys
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.database import get_session_local
from app.models.user import User
from app.models.time_entry import TimeEntry
from app.schemas.url_usage import URLUsageBatchCreate
from app.services.url_usage_service import URLUsageService

db_path = os.path.expanduser("~/.monitra/cache.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM pending_url_usage WHERE status != 'completed'").fetchall()
conn.close()

records = []
for r in rows:
    records.append({
        "time_entry_id": r["time_entry_id"],
        "browser_name": r["browser_name"],
        "domain": r["domain"],
        "url": r["url"],
        "page_title": r["page_title"],
        "duration_seconds": r["duration_seconds"],
        "recorded_at": r["recorded_at"],
        "client_event_id": r["client_event_id"],
    })

db = get_session_local()()
try:
    first_entry_id = records[0]["time_entry_id"]
    te = db.query(TimeEntry).filter(TimeEntry.id == first_entry_id).first()
    owner_user = db.query(User).filter(User.id == te.user_id).first()
    
    print(f"Testing batch sync for time entry {first_entry_id} belonging to user {owner_user.email}...")
    payload = URLUsageBatchCreate(records=records)
    accepted, failed = URLUsageService.batch_record_usage(db, payload, owner_user)
    print(f"BATCH RESULT SUCCESS: accepted={accepted}, failed={failed}")
finally:
    db.close()
