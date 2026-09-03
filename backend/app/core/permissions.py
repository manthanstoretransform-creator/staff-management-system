# backend/app/core/permissions.py
#
# This table is the login gate: AuthService.login_exchange refuses any role that
# is missing a key here, with 502 "Invalid authentication provider response".
# That makes it the second half of a pair -- `MemberRole` in app/schemas/member.py
# says which roles a member may be *given*, and this says which roles may
# *sign in*. When the two drift apart you can create a member nobody can log in
# as, which is exactly what happened to `leader` and then to `hr`. Every
# MemberRole value must have an entry here; tests/test_auth_flow.py pins that.

ROLE_PERMISSIONS = {
    "employee": {
        "projects:view",
        "tasks:view",
        "time_entries:manage_own",
        "tasks:create",
        "tasks:update",
        # TODO: Confirm with senior if employee role should also get granular permissions
        # for creating/updating tasks they are assigned to, once task assignee checking is unified.
    },
    "manager": {
        "projects:create",
        "projects:update",
        "projects:delete",
        "projects:view",
        "tasks:create",
        "tasks:update",
        "tasks:delete",
        "tasks:view",
        "project_members:manage",
        "task_assignees:manage",
        "time_entries:manage_own",
        "time_entries:view_all",
        "manual_time_entries:approve",
        "view_employees",
    },
    "org_admin": {
        "projects:create",
        "projects:update",
        "projects:delete",
        "projects:view",
        "tasks:create",
        "tasks:update",
        "tasks:delete",
        "tasks:view",
        "project_members:manage",
        "task_assignees:manage",
        "time_entries:manage_own",
        "time_entries:view_all",
        "manual_time_entries:approve",
        "view_employees",
        "manage_employees",
    },
    "admin": {  # Alias/compatible role name mapping to org_admin permissions
        "projects:create",
        "projects:update",
        "projects:delete",
        "projects:view",
        "tasks:create",
        "tasks:update",
        "tasks:delete",
        "tasks:view",
        "project_members:manage",
        "task_assignees:manage",
        "time_entries:manage_own",
        "time_entries:view_all",
        "manual_time_entries:approve",
        "view_employees",
        "manage_employees",
    },
    # Human resources. `hr` is one of the four roles this system offers --
    # MemberRole in app/schemas/member.py accepts it, and the
    # /project-management/metadata endpoint serves it to the UI as a choice --
    # but it had no entry here, so an HR member could be created and then could
    # not sign in. HR's authority is over people rather than projects: they
    # administer the member directory and need to see the organisation's time
    # and approve manual entries, but they do not own or delete projects.
    "hr": {
        "projects:view",
        "tasks:view",
        "time_entries:manage_own",
        "time_entries:view_all",
        "manual_time_entries:approve",
        "view_employees",
        "manage_employees",
    },
    # A team / project leader. `leader` is a role the rest of the application
    # already recognises -- TeamsService.leaders(), TeamsService.summary() and
    # /projects/assignable-leaders all select on
    # `role_name IN ("admin", "leader")`, and ProjectMemberService.LEADER_ROLES
    # is {"leader", "project_leader"} -- but it was never given a permission set
    # here. login_exchange refuses any role missing from this table, so a
    # WordPress user coming back with roles: ["leader"] authenticated
    # successfully and was then rejected with 502 "Invalid authentication
    # provider response". A leader's authority matches a manager's: they lead
    # projects, manage their members, approve manual time and see the team's
    # entries.
    "leader": {
        "projects:create",
        "projects:update",
        "projects:delete",
        "projects:view",
        "tasks:create",
        "tasks:update",
        "tasks:delete",
        "tasks:view",
        "project_members:manage",
        "task_assignees:manage",
        "time_entries:manage_own",
        "time_entries:view_all",
        "manual_time_entries:approve",
        "view_employees",
    },
    "super_admin": {
        "projects:create",
        "projects:update",
        "projects:delete",
        "projects:view",
        "tasks:create",
        "tasks:update",
        "tasks:delete",
        "tasks:view",
        "project_members:manage",
        "task_assignees:manage",
        "time_entries:manage_own",
        "time_entries:view_all",
        "manual_time_entries:approve",
        "view_employees",
        "manage_employees",
        # TODO: Define super-admin specific system-wide settings permissions once verified.
    }
}

# `project_leader` is the second spelling ProjectMemberService.LEADER_ROLES
# already accepts. It carries exactly a leader's authority; defining it here
# keeps a provider that uses that spelling from hitting the same 502 that
# `leader` did.
ROLE_PERMISSIONS["project_leader"] = set(ROLE_PERMISSIONS["leader"])
