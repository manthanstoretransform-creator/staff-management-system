import type { UserRead } from "../../api/auth";

/**
 * Who may read the whole organization's feedback.
 *
 * Almost every gate in this app is a *permission* check, because the backend
 * endpoint behind it is gated on a permission. Feedback is the exception: the
 * backend gates `GET /feedback` on the role name itself
 * (`FEEDBACK_VIEW_ALL_ROLES` in `app/services/feedback.py`), so mirroring that
 * role list is what keeps the sidebar from offering a page the API would
 * answer with 403. The two lists must stay in step — if a role is added to one,
 * add it to the other.
 *
 * `org_admin` / `super_admin` and `project_leader` are the alternate spellings
 * the backend's ROLE_PERMISSIONS table already defines for admin and leader
 * authority; `administrator` is the WordPress slug the provider sends for an
 * admin, which the backend resolves through its alias table.
 */
const FEEDBACK_VIEW_ALL_ROLES = new Set([
  "admin",
  "administrator",
  "org_admin",
  "super_admin",
  "hr",
  "leader",
  "project_leader",
]);

/** True for Admin, HR and Leader — the roles allowed the org-wide feedback list. */
export const canViewAllFeedback = (user: UserRead | null) =>
  FEEDBACK_VIEW_ALL_ROLES.has((user?.role_name || "").trim().toLowerCase());
