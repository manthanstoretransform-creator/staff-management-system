import sqlite3
import os
import json

db_path = os.path.expanduser("~/.monitra/cache.db")
print(f"Opening DB: {db_path}")

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    rows = cursor.execute("SELECT * FROM pending_url_usage").fetchall()
    print(f"Total pending_url_usage rows: {len(rows)}")
    for r in rows:
        print(dict(r))
    conn.close()
else:
    print("DB file does not exist.")
