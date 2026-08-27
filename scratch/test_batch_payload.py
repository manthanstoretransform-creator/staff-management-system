import requests
import sqlite3
import os

# Connect to DB and read one batch of records
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

print(f"Testing batch sync with {len(records)} records...")

# Test with backend url
# We can test calling backend directly via Python code to see traceback
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.database import get_session_local
from app.models.user import User
from app.schemas.url_usage import URLUsageBatchCreate
from app.services.url_usage_service import URLUsageService

db = get_session_local()()
user = db.query(User).first()
print(f"Test user: {user.email}, org: {user.organization_id}")

try:
    payload = URLUsageBatchCreate(records=records)
    accepted, failed = URLUsageService.batch_record_usage(db, payload, user)
    print(f"Batch result: accepted={accepted}, failed={failed}")
except Exception as e:
    import traceback
    print("EXCEPTION RAISED IN BATCH RECORD USAGE:")
    traceback.print_exc()
finally:
    db.close()
