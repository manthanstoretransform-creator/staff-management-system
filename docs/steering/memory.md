docs/steering/memory.md

# Project Memory — Last updated: Aug 10, 2026

## Status by Phase
- Phase 0 (Scaffolding): Done. backend/desktop/frontend folders + docs set up.
- Phase 1 (Identity): Done, tested end-to-end.
  - users + refresh_tokens tables live in dev AND production Neon.
  - Login-exchange endpoint (POST /auth/login) working: find-or-create by hubstaff_user_id,
    correct organization_id validation (fixed — no longer defaults to first org in DB).
  - JWT middleware + GET /auth/me tested: rejects missing/invalid/expired tokens.
  - A temporary POST /auth/dev-login endpoint exists for local frontend testing without
    live Hubstaff credentials. NEEDS: confirm it's gated to dev-only (ENV check), confirm
    it does NOT check password against the real users table, fix bcrypt/passlib version
    mismatch warning. Must be removed or fully locked before Aug 25 ship.
- Phase 2 (Core CRUD): Done, tested end-to-end.
  - Projects CRUD (Task 5): org-scoped, archive = soft delete via status field. Verified
    cross-org access returns 404, archived rows aren't deleted.
  - Tasks CRUD (Task 6): nested under projects, two-level scoping (project's org +
    task belongs to that specific project). Verified task-ID/project-ID mismatch returns 404.
  - Project Members + Task Assignees (Task 7): built, cross-org validation on the ADDED
    user (not just the project/task). Testing in progress as of Aug 10 — confirm duplicate
    handling and hard-delete-on-remove behavior against Database_Documentation.md.

## Frontend Status
- Login screen: built, tested, currently pointed at /auth/dev-login (see note above — must
  switch back to /auth/login once real Hubstaff test credentials are available).
- Sidebar project navigation: built, matches prototype layout, real org-scoped data confirmed.
- Task list per project: built, read-only, real API data only (no fabricated budget/tracked-time
  fields — those don't exist in the backend schema yet).
- Create Task: built, wired to real POST endpoint.
- Task detail + status update: built, wired to real PUT endpoint.
- Archive task from list: built, wired to real PATCH endpoint, confirmed soft-delete in DB.

## Open Questions (unresolved with senior as of Aug 10)
1. Can a user belong to more than one organization? Affects whether organization_id
   stays directly on `users` or needs a separate membership table. Currently assuming
   single-org-per-user.
2. Which permission key (from permission_schema.permissions) gates adding project
   members / task assignees? Currently a TODO in the backend code, no check enforced yet.
3. Desktop app: Python + Electron, or pure PySide6 (Qt)? Recommended PySide6 given
   tracking-logic complexity, but not yet confirmed with senior.
4. Deployment: Vercel serverless may not suit FastAPI long-term (cold starts, no
   background workers) — flagged, not yet decided.

## Conventions in Use
- One Antigravity task per PR, reviewed before merge.
- Migrations: dev Neon branch first, verify, then production.
- Soft-delete via `status` field, never hard-delete on projects/tasks.
- Steering docs (rules.md, architecture.md, phases.md, prd.md) referenced in every
  Antigravity prompt, not restated each time.

## Next Planned Task
Phase 3 kickoff (time tracking) — not yet started.