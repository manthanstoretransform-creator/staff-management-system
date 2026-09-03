# backend/app/core/permissions.py

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
