import type { UserRead } from "../api/auth";

/**
 * The roles whose view of the app is their own team rather than the whole
 * organization.
 *
 * The names mirror `TEAM_SCOPED_ROLES` in
 * `backend/app/services/member_scope.py`, including the second `project_leader`
 * spelling. This is used only to make the UI *say* what the backend will do --
 * every scoping rule is still enforced server-side, so a stale copy of this
 * list narrows a form label, never a permission.
 */
const TEAM_SCOPED_ROLES = ["leader", "project_leader"];

/** Whether this user leads a team rather than administering the organization. */
export const isTeamScoped = (user: UserRead | null | undefined) =>
  !!user && TEAM_SCOPED_ROLES.includes(user.role_name);
