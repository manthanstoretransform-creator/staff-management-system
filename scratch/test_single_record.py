import os
import sys
import sqlite3
import traceback
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.database import get_session_local
from app.models.user import User
from app.models.time_entry import TimeEntry
from app.repositories.time_entry import TimeEntryRepository
from app.services.url_usage_service import URLUsageService
from app.schemas.url_usage import URLUsageCreate

# Connect to DB and read first pending record
db_path = os.path.expanduser("~/.monitra/cache.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
r = conn.execute("SELECT * FROM pending_url_usage WHERE status != 'completed' LIMIT 1").fetchone()
conn.close()

record_dict = dict(r)
print(f"Target Record: {record_dict}")

db = get_session_local()()
try:
    # Get user who owns this time_entry_id
    te = TimeEntryRepository.get_by_id(db, record_dict["time_entry_id"])
    if not te:
        print(f"ERROR: time_entry {record_dict['time_entry_id']} does NOT exist in backend DB!")
    else:
        print(f"Found TimeEntry: id={te.id}, org_id={te.organization_id}, user_id={te.user_id}, status={te.status}")
        user = db.query(User).filter(User.id == te.user_id).first()
        print(f"TimeEntry owner user: {user.email}")
        
        # Test record_usage with this user
        payload = URLUsageCreate(
            time_entry_id=record_dict["time_entry_id"],
            browser_name=record_dict["browser_name"],
            domain=record_dict["domain"],
            url=record_dict["url"],
            page_title=record_dict["page_title"],
            duration_seconds=record_dict["duration_seconds"],
            recorded_at=record_dict["recorded_at"],
            client_event_id=record_dict["client_event_id"]
        )
        res = URLUsageService.record_usage(db, payload, user)
        print(f"SUCCESS! Recorded usage ID: {res.id}")

except Exception as e:
    print("EXCEPTIONAL ERROR DETECTED:")
    traceback.print_exc()
finally:
    db.close()
