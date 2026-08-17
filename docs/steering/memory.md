# Project Memory — Last updated: Aug 17, 2026

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
  - POST /auth/dev-login still exists for internal testing only. Confirmed
    gated to dev/test ENV. NOT used by the frontend login screen anymore.
    STILL NEEDS: full removal or hardened lockdown before Aug 25 ship.
  - JWT middleware + GET /auth/me tested: rejects missing/invalid/expired
    tokens. Reject deactivated users (`is_active: False`) with `401 Unauthorized`.
  - **Auth Session Persistence on Refresh**: Frontend now stores `accessToken` and `refreshToken` in `localStorage`. On application mount, a loading state (`isLoading`) is triggered while the frontend queries `GET /auth/me` to restore the full user profile. This prevents flash redirects to `/login` and ensures identity state (e.g. role, name, email) survives page refreshes.
  - **WordPress Auth Outage Fallback & Hashing Compatibility**: Integrated a local database authentication fallback inside `AuthService.login_exchange` to allow seamless local developer logins using the default credential (`developer_st_performance` password) during external WordPress Pantheon server-freeze outages. Also bypassed the `passlib` version validation compatibility bug (`AttributeError: module 'bcrypt' has no attribute '__about__'`) by using Python's standard `bcrypt` package directly for hashing and verification.
- Phase 2 (Core CRUD): Done, tested end-to-end.
  - Projects CRUD (Task 5): org-scoped, archive = soft delete via status
    field. Verified cross-org access returns 404, archived rows aren't
    deleted.
  - Tasks CRUD (Task 6): nested under projects, two-level scoping (project's
    org + task belongs to that specific project). Verified task-ID/project-ID
    mismatch returns 404.
  - Project Members + Task Assignees (Task 7): built, cross-org validation on
    the ADDED user (not just the project/task).
  - **Employee Task Creation (Task 11)**: Updated role permissions map so `"tasks:create"` is granted to both `"admin"` and `"employee"`. Added project-membership check to `TaskService.create_task` so employees can ONLY create tasks in projects they are a member of (verified against `project_members`). Admins/managers bypass membership checks. Organization check isolation happens first (cross-org requests return 404, not 403).
- Phase 3 (Time Tracking): In progress.
  - Task 8 (Automatic Timer — start/stop): Backend built and verified —
    one-active-timer-per-user constraint enforced (409 on double-start),
    server-computed total_seconds on stop, cross-org/task-mismatch scoping
    verified. Frontend UI (Start/Stop Timer button, live elapsed-time
    display) built and verified: correctly detects an already-running timer
    on page refresh (does not allow double-start), shows readable error on
    cross-task 409 conflict, handles double-stop gracefully.
  - **Task Row Inline Start/Stop Controls**: Integrated Start/Stop Timer button controls directly next to each task in the project task list. Supported active timer user-scoping to ensure that starting an employee task timer does not trigger active running timers on the Admin's view of that task.
  - **Automatic Task Switching**: Added frontend task switching logic in `ProjectList.tsx` Start Timer buttons. If a user clicks Start Timer on Task B while Task A is running, the app stops Task A first, then starts Task B timer, updating the active timer state dynamically with backend reconciliation and failure handling. General task row clicks only open task details without triggering any timer actions, and the details modal is scoped to the selected task ID.
  - Task 9 (Manual Time Entries + approval workflow): Backend built and
    verified — approval_status forced to "pending" on creation, 403 for
    non-manager/admin approve/reject attempts, 409 on re-approving/rejecting
    an already-decided entry. NOTE: backend schema initially had a bug
    (ManualTimeEntryCreate incorrectly required start_time/end_time instead
    of work_date/total_seconds) — fixed. Frontend "Log Time Manually" form
    built and verified: date/hours/minutes inputs, client-side validation
    (no future dates, 1–86400 second bounds), entry list with status badges,
    persists correctly across page reload.
  - **Employee Project-wise tracked hours**: Added summation of automatic and approved manual time entries on the client-side to render project-wise totals under each project name in the left sidebar listing and selected project details card.
  - **Expanded Query Limit Validator**: Increased max limit parameter query constraint from `100` to `10000` in the backend `/time-entries` and `/manual-time-entries` routes. This prevents client bulk queries from triggering a FastAPI 422 validation failure, resolving incorrect project-level calculations (0.0h).
  - **Employee Management API & Access Controls (Task 10)**: Added `is_active` column to the `users` table via Alembic migration (`is_active BOOLEAN NOT NULL DEFAULT true`). Implemented a paginated listing of employees and user-status toggle endpoint (`PUT /employees/{user_id}/status`) scoped by organization. Added logic blocking self-deactivation with `409 Conflict`.
  - **Role-Based Project Visibility (Task 12)**: Enforced project visibility scopes on project listing and detail retrieval. Admin/manager/superadmin see all active projects in their organization. Employees see only active projects in their organization where they are a project member (verified via a join with `ProjectMember`). GET project details returns `404 Not Found` for unassigned projects or cross-org project lookups.
  - **Sidebar User Profile Card**: Added a user profile card at the bottom of the left sidebar showing name, email, role (case-sensitive mapping: `Employee`/`Admin`), and initials-based avatar. Survives browser refresh and remains aligned with Sign Out controls.
  - Activity/Screenshot/App-Usage tracking: NOT STARTED — blocked on the
    desktop app stack decision (see Open Questions).

- Phase 4 (Admin Dashboards & Management): Done, tested end-to-end.
  - **Admin Menu & Dashboard**: Registered `/admin` route. Displayed a summary of organization projects, members, tasks, and productivity counters.
  - **Admin Project Management**: Created `/admin/projects` view for CRUD operations and member-to-project assignment UI (dropdown list + Assign Member button action).
  - **Admin Task Listing**: Created `/admin/tasks` displaying all active organization tasks. Added project dropdown selector for quick project filtering.
  - **Admin/Employee Task Creation Self-Assignment**: Supported `assignee_id` field in task creation schema and service. If selected, a corresponding relationship row is generated in the `task_assignees` table.

## RBAC / Security Remediation (updated Aug 17)
- Centralized RBAC (`require_permission` dependency) applied across Projects, Tasks, Project Members, Task Assignees, and Employees.
- Employees can now create tasks but are dynamically restricted to their member projects.
- Organization isolation checks occur before membership/role permission verification, returning 404 for cross-org requests instead of leaks.
- Deactivated users are blocked from `/auth/me` (returning 401 Unauthorized) and cannot access dashboard pages or track time.

## Frontend Status
- Login screen: built, tested, pointed at real /auth/login. Fixes loop unmount bug during form submit.
- Sidebar project navigation: built, matches prototype layout, dynamic role-based visibility active (employee sees member projects, admin sees all projects).
- User Profile Card: Displays logged-in user initials, name, email, and mapped role at the bottom-left sidebar.
- Task list per project: built, wired to real API data, Time Tracked now accurate.
- Create Task: Employees can create tasks in assigned projects; admins can create tasks in all organization projects. Supported optional assignee selection and self-assignment checkboxes.
- Task detail + status update: built, wired to real PUT endpoint.
- Archive task from list: built, wired to real PATCH endpoint, confirmed soft-delete in DB.
- Task Detail modal: now includes Automatic Timer (Start/Stop) and Manual Time Entry logging + list, both verified working.
- Admin Panels: Admin Dashboard, Project Management, and Task list components are registered and fully functional.

## Open Questions (status as of Aug 17)
1. Desktop app: Python + Electron, or pure PySide6 (Qt)? STILL UNRESOLVED —
   Project_Requirements.md documents Electron + React + TypeScript as the
   stack, but earlier internal recommendation was PySide6 given
   tracking-logic complexity. Not yet reconciled with senior. This is
   currently the single biggest deadline risk, since Activity/Screenshot/
   App-Usage tracking (Phase 3 remainder) cannot start without this
   decision.
2. Deployment: Vercel serverless may not suit FastAPI long-term (cold
   starts, no background workers) — flagged, not yet decided.

## Conventions in Use
- One Antigravity task per PR, reviewed before merge.
- Migrations: dev Neon branch first, verify, then production.
- Soft-delete via `status` field, never hard-delete on projects/tasks.
- Steering docs (rules.md, architecture.md, phases.md, prd.md) referenced in
  every Antigravity prompt, not restated each time.
- Frontend error handling: raw API error objects/arrays must never be
  rendered directly — always extract the message field first.
