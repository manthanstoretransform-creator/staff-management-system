import sys
import os
import time

desktop_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
backend_path = os.path.abspath(os.path.join(desktop_path, "..", "backend"))

# 1. Prepend backend first to load DB session helper
sys.path.insert(0, backend_path)
from app.core.database import get_session_local
from sqlalchemy import text

# 2. Clean up sys.path and sys.modules cache to load desktop app
sys.path.remove(backend_path)
del sys.modules["app"]

# 3. Prepend desktop path
sys.path.insert(0, desktop_path)
from app.api.client import ApiClient
from app.auth.session import SessionManager
from app.auth.service import AuthService
from app.time_entries.service import TimeEntryService

def print_db_row(entry_id: int, label: str):
    db = get_session_local()()
    try:
        sql = """
            SELECT id, organization_id, user_id, project_id, task_id, start_time, end_time, total_seconds, status, is_manual, is_billable, created_at, updated_at
            FROM time_entries
            WHERE id = :entry_id;
        """
        row = db.execute(text(sql), {"entry_id": entry_id}).fetchone()
        if row:
            print(f"\n[{label}] NEON DB ROW FOR ID {entry_id}:")
            print("  id:             ", row[0])
            print("  organization_id:", row[1])
            print("  user_id:        ", row[2])
            print("  project_id:     ", row[3])
            print("  task_id:        ", row[4])
            print("  start_time:     ", row[5])
            print("  end_time:       ", row[6])
            print("  total_seconds:  ", row[7])
            print("  status:         ", row[8])
            print("  is_manual:      ", row[9])
            print("  is_billable:    ", row[10])
            print("  created_at:     ", row[11])
            print("  updated_at:     ", row[12])
        else:
            print(f"\n[{label}] ROW ID {entry_id} NOT FOUND IN NEON!")
    finally:
        db.close()

def query_latest_rows(limit=5):
    db = get_session_local()()
    try:
        sql = "SELECT id, user_id, project_id, task_id, start_time, end_time, status FROM time_entries ORDER BY id DESC LIMIT :limit;"
        rows = db.execute(text(sql), {"limit": limit}).fetchall()
        print(f"\nLATEST {limit} ROWS IN NEON:")
        print(f"{'ID':<6} | {'USER_ID':<8} | {'PROJECT_ID':<10} | {'TASK_ID':<8} | {'START_TIME':<26} | {'END_TIME':<26} | {'STATUS':<8}")
        print("-" * 110)
        for r in rows:
            print(f"{r[0]:<6} | {r[1]:<8} | {r[2]:<10} | {r[3]:<8} | {str(r[4]):<26} | {str(r[5]):<26} | {r[6]:<8}")
    finally:
        db.close()

def run():
    client = ApiClient()
    session = SessionManager()
    auth_service = AuthService(client, session)
    time_entry_service = TimeEntryService(client)
    
    # 1. Log in to get active session
    print("Logging in...")
    auth_service.login("hardikravalstoretransform@gmail.com", "developer_st_performance")
    print("Logged in successfully. Active User ID:", session.user_info["id"])
    
    # Pre-clean active timers from database to ensure fresh start
    db = get_session_local()()
    try:
        active_row = db.execute(text("SELECT id FROM time_entries WHERE user_id = 36 AND end_time IS NULL LIMIT 1;")).fetchone()
        if active_row:
            active_id = active_row[0]
            print(f"\nFound active running timer ID {active_id} in database. Stopping it first to clean state...")
            try:
                time_entry_service.stop_time_entry(active_id)
                print(f"Stopped pre-existing active timer ID {active_id} successfully.")
            except Exception as stop_err:
                print(f"Note: Failed to stop pre-existing active timer: {stop_err}")
    finally:
        db.close()

    # Print baseline database rows
    print("\n--- BASELINE DATABASE STATE ---")
    query_latest_rows(3)
    
    # 2. Start time entry (using project 53 and task 63)
    project_id = 53
    task_id = 63
    print(f"\nStarting time entry for project {project_id}, task {task_id}...")
    entry_id = time_entry_service.start_time_entry(project_id, task_id)
    print("SUCCESS! Created Time Entry ID:", entry_id)
    
    # Print row immediately after creation (while running)
    print_db_row(entry_id, "RUNNING STATE")
    
    # 3. Wait 5 seconds
    print("\nWaiting 5 seconds...")
    time.sleep(5)
    
    # 4. Stop time entry
    print(f"Stopping time entry ID {entry_id}...")
    stop_result = time_entry_service.stop_time_entry(entry_id)
    print("SUCCESS! Stop request returned.")
    
    # Print row immediately after stopping
    print_db_row(entry_id, "STOPPED STATE")
    
    # Print final database rows to confirm no duplicates
    print("\n--- FINAL DATABASE STATE ---")
    query_latest_rows(3)

if __name__ == "__main__":
    run()
