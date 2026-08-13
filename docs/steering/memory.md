docs/steering/memory.md

# Project Memory — Last updated: Aug 12, 2026

## Status by Phase
- Phase 0 (Scaffolding): Done. backend/desktop/frontend folders + docs set up.
- Phase 1 (Identity): Done, tested end-to-end.
  - users + refresh_tokens tables live in dev AND production Neon.
  - Real WordPress login flow (POST /auth/login) fully working end-to-end:
    frontend → FastAPI (server-side WordPress call via httpx) → JWT issued.
    Verified with Hardik Raval's real credentials (employee role).
  - Frontend login screen switched from /auth/dev-login to /auth/login.
    Wrong-password path confirmed showing WordPress's exact error message
    ("The username or password you entered is incorrect.") rather than a
    generic error.
  - Fabricated test users (2 fake admins, 1 fake employee) removed from dev
    Neon branch — real login is now the only path creating user rows.
  - POST /auth/dev-login still exists for internal testing only (e.g. minting
    an admin token before a real admin credential is available). Confirmed
    gated to dev/test ENV. NOT used by the frontend login screen anymore.
    STILL NEEDS: full removal or hardened lockdown before Aug 25 ship.
  - JWT middleware + GET /auth/me tested: rejects missing/invalid/expired
    tokens.
- Phase 2 (Core CRUD): Done, tested end-to-end.
  - Projects CRUD (Task 5): org-scoped, archive = soft delete via status
    field. Verified cross-org access returns 404, archived rows aren't
    deleted.
  - Tasks CRUD (Task 6): nested under projects, two-level scoping (project's
    org + task belongs to that specific project). Verified task-ID/project-ID
    mismatch returns 404.
  - Project Members + Task Assignees (Task 7): built, cross-org validation on
    the ADDED user (not just the project/task).
- Phase 3 (Time Tracking): In progress.
  - Task 8 (Automatic Timer — start/stop): Backend built and verified —
    one-active-timer-per-user constraint enforced (409 on double-start),
    server-computed total_seconds on stop, cross-org/task-mismatch scoping
    verified. Frontend UI (Start/Stop Timer button, live elapsed-time
    display) built and verified: correctly detects an already-running timer
    on page refresh (does not allow double-start), shows readable error on
    cross-task 409 conflict, handles double-stop gracefully.
  - Task 9 (Manual Time Entries + approval workflow): Backend built and
    verified — approval_status forced to "pending" on creation, 403 for
    non-manager/admin approve/reject attempts, 409 on re-approving/rejecting
    an already-decided entry. NOTE: backend schema initially had a bug
    (ManualTimeEntryCreate incorrectly required start_time/end_time instead
    of work_date/total_seconds) — fixed. Frontend "Log Time Manually" form
    built and verified: date/hours/minutes inputs, client-side validation
    (no future dates, 1–86400 second bounds), entry list with status badges,
    persists correctly across page reload.
  - Time Tracked display (project total, task row, task modal): Previously
    showed 0.0h everywhere — root cause was reading from unused/never-updated
    projects.time_tracked_seconds and tasks.time_tracked_seconds DB columns.
    FIXED: now computed client-side by summing real time_entries (stopped)
    + approved manual_time_entries via listProjectTimeEntriesAPI /
    listProjectManualTimeEntriesAPI. Verified working correctly across all
    three display locations.
  - KNOWN LIMITATION (flagged, not yet fixed): the above two list functions
    request limit=100 (backend's GET /time-entries and GET /manual-time-entries
    cap limit at le=100). Any project exceeding 100 time entries will show a
    silently incorrect (too-low) total. TODO comments added in code. Needs
    real pagination (loop until a response returns fewer than `limit`
    results) before this ships to real users with meaningful usage volume.
  - Activity/Screenshot/App-Usage tracking: NOT STARTED — blocked on the
    desktop app stack decision (see Open Questions).

## RBAC / Security Remediation (started Aug 12, in progress)
- AUDIT COMPLETE: found employees could perform admin-only actions (e.g.
  delete/archive projects) because zero permission checks existed on most
  protected endpoints — require_permission() already existed as a working
  mechanism but was barely used (only manual-entry approve/reject used it).
- CRITICAL VULNERABILITY FOUND AND FIXED: POST /auth/login previously wrote
  role_name and permissions directly from the request body into the users
  table on every login — meant any caller could self-assign admin
  permissions. FIXED: WordPress call moved server-side (backend calls
  WordPress directly via httpx); role_name now resolved only from
  WordPress's trusted response; permissions for API authorization now
  resolved server-side from a new ROLE_PERMISSIONS map
  (backend/app/core/permissions.py), never from client/WordPress input
  directly.
- WordPress's raw permission_schema.permissions (capture_screenshot,
  track_keyboard, view_reports, manage_users, etc. — a mix of desktop
  tracking config and capability flags) is now stored separately as
  wp_capabilities — used for future desktop app config, NOT used to gate
  API authorization.
- Centralized RBAC (require_permission dependency) applied across Projects,
  Tasks, Project Members, Task Assignees — IN PROGRESS, not yet fully
  verified with a real admin token (see blocker below).
- Scattered inconsistent role_name tuple checks in time_entry.py and
  manual_time_entry.py — replacement with centralized require_permission()
  calls scoped but not yet fully confirmed complete.
- docs/rbac.md created documenting the ROLE_PERMISSIONS map and the
  wp_capabilities vs. authorization-permissions split.
- BLOCKER: No real admin/manager WordPress credential yet. Requested from
  senior, confirmed "will provide later." Employee-side 403 checks can be
  and have been partially verified; admin-side 200 checks and full RBAC
  regression are blocked until that credential arrives.

## Frontend Status
- Login screen: built, tested, pointed at real /auth/login (see above).
- Sidebar project navigation: built, matches prototype layout, real
  org-scoped data confirmed.
- Task list per project: built, wired to real API data, Time Tracked now
  accurate (see Phase 3 notes above).
- Create Task: built, wired to real POST endpoint.
- Task detail + status update: built, wired to real PUT endpoint.
- Archive task from list: built, wired to real PATCH endpoint, confirmed
  soft-delete in DB.
- Task Detail modal: now includes Automatic Timer (Start/Stop) and Manual
  Time Entry logging + list, both verified working.

## Open Questions (status as of Aug 12)
1. ~~Can a user belong to more than one organization?~~ / organization_id
   gap: RESOLVED Aug 12 — WordPress's login response does not include
   organization_id at all. Temporary fix: DEFAULT_ORGANIZATION_ID (env
   config, currently = 1) assigned to all new real-login users. Confirmed
   as acceptable short-term solution by senior. Real per-user org mapping
   still not implemented — revisit if multi-org support becomes a
   requirement.
2. Which permission key gates adding project members / task assignees? —
   Being resolved as part of the RBAC remediation now in progress (see RBAC
   section above) — should be closed out once ROLE_PERMISSIONS map is fully
   applied and verified.
3. Desktop app: Python + Electron, or pure PySide6 (Qt)? STILL UNRESOLVED —
   Project_Requirements.md documents Electron + React + TypeScript as the
   stack, but earlier internal recommendation was PySide6 given
   tracking-logic complexity. Not yet reconciled with senior. This is
   currently the single biggest deadline risk, since Activity/Screenshot/
   App-Usage tracking (Phase 3 remainder) cannot start without this
   decision.
4. Deployment: Vercel serverless may not suit FastAPI long-term (cold
   starts, no background workers) — flagged, not yet decided.

## Conventions in Use
- One Antigravity task per PR, reviewed before merge.
- IMPORTANT LESSON (Aug 12): Antigravity has repeatedly described a fix in
  its plan/chat response without actually modifying the file that mattered
  (e.g. changed an API client file but not the UI component; changed docs
  but not code). Always check the "files changed" list in the diff BEFORE
  approving — confirm the actual component/file you expect to see modified
  is really in that list, not just an adjacent file.
- Migrations: dev Neon branch first, verify, then production.
- Soft-delete via `status` field, never hard-delete on projects/tasks.
- Steering docs (rules.md, architecture.md, phases.md, prd.md) referenced in
  every Antigravity prompt, not restated each time.
- Frontend error handling: raw API error objects/arrays must never be
  rendered directly (caused a "[object Object]" bug) — always extract the
  message field first. Shared error-parsing fix applied, but worth
  double-checking new forms don't reintroduce this.
- Backend list endpoints cap `limit` at le=100 (Query validation) — frontend
  calls requesting more than 100 will 422. Check this cap before writing any
  new "fetch everything" style frontend function.

## Next Planned Task
- Finish RBAC verification once admin credential arrives (full employee vs.
  admin/manager test matrix, per docs/rbac.md).
- Resolve desktop app stack decision with senior (Electron vs. PySide6) —
  blocking the rest of Phase 3.
- Implement real pagination for Time Tracked summation before ship (currently
  capped at first 100 entries per project).
- Remove or fully lock down /auth/dev-login before Aug 25.