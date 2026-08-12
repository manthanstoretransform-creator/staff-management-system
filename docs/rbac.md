# Role-Based Access Control (RBAC) System

The StaffTrack system enforces access control via a server-derived, role-to-permission mapping dictionary. Permission keys are embedded into user claims and validated during API requests.

## Role Permissions Mapping

| role_name | permission keys granted | notes |
| :--- | :--- | :--- |
| **employee** | `projects:view`<br>`tasks:view`<br>`time_entries:manage_own` | Limited to viewing active projects/tasks and tracking own automated time timers. |
| **manager** | `projects:create`, `projects:update`, `projects:delete`, `projects:view`<br>`tasks:create`, `tasks:update`, `tasks:delete`, `tasks:view`<br>`project_members:manage`<br>`task_assignees:manage`<br>`time_entries:manage_own`, `time_entries:view_all`<br>`manual_time_entries:approve` | Full project & task CRUD management, team member assignments, viewing all time logs, approving manual logs. |
| **org_admin** / **admin** | `projects:create`, `projects:update`, `projects:delete`, `projects:view`<br>`tasks:create`, `tasks:update`, `tasks:delete`, `tasks:view`<br>`project_members:manage`<br>`task_assignees:manage`<br>`time_entries:manage_own`, `time_entries:view_all`<br>`manual_time_entries:approve` | High-level organizational control, identical permissions to managers at this phase. |
| **super_admin** | `projects:create`, `projects:update`, `projects:delete`, `projects:view`<br>`tasks:create`, `tasks:update`, `tasks:delete`, `tasks:view`<br>`project_members:manage`<br>`task_assignees:manage`<br>`time_entries:manage_own`, `time_entries:view_all`<br>`manual_time_entries:approve` | System-wide administrators (superset of org admin). |

## Tenant Organization Scoping Note

> [!NOTE]
> **TEMPORARY BEHAVIOR**: Because the server-side WordPress login response does not currently provide an `organization_id`, every newly created user is assigned the system default `DEFAULT_ORGANIZATION_ID` (retrieved from the `.env` configuration file).
> Existing users' `organization_id` values will NOT be updated during subsequent logins if they have already been set to another value (e.g. manually updated in the database).

