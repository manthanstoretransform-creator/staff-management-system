- Never modify, rename, or drop any existing table: organizations, projects,
  project_members, tasks, task_assignees, time_entries, manual_time_entries,
  time_entry_activity, time_entry_app_usage, time_entry_url_usage,
  time_entry_screenshots, activity_logs, api_error_logs.
- Read docs/Database_Documentation.md before writing any migration.
- All schema changes go through Alembic migrations. Never manual DDL.
- New tables only when explicitly requested in a task prompt.
- All DB connections via environment variable. Never hardcode credentials.
- Point migrations at DATABASE_URL_DEV (Neon branch), never production, unless told otherwise.
- Follow Repository Pattern / Service Layer separation. No direct SQLAlchemy
  queries inside route handlers.
- Every new endpoint needs a matching request added to docs/postman/collection.json.
- Pydantic schemas for all request/response bodies. No raw dicts.