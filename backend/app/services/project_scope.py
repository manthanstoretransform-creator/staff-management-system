"""Which projects a caller is allowed to *see*.

The companion to ``member_scope``. That module answers "at which people may
this caller look?"; this one answers "at which projects?", and the two have to
agree or a leader's screens contradict each other -- their member directory
showing one team while the project list shows the whole company's work.

``projects:view`` and ``time_entries:view_all`` say a caller may look past
their own row. For an admin, an org_admin, a manager or HR that means the
organization. For a **leader** it means their own projects: the ones an admin
put them in charge of, plus any they were staffed onto as a member.

One helper, used by every read surface that returns projects or the tasks
inside them (the project list, project detail, project tasks, and the
project/task summary behind the Task Listing screen), so a leader's scope
cannot be right on one screen and wrong on the next.

Membership is included alongside leadership deliberately: a leader who is
staffed onto somebody else's project still tracks time against it from the
desktop client, and a project they cannot read is a project they cannot pick.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.services.member_scope import is_team_scoped


def visible_project_ids(db: Optional[Session], user: User) -> Optional[set[int]]:
    """The project ids this caller may read, or ``None`` for "no restriction".

    ``None`` means the organization, and is what every non-leader role gets, so
    callers can skip the filter entirely rather than building an ``IN`` list of
    every project in the company.

    With no session to ask (``db is None``) a team-scoped caller gets the empty
    set. Like ``visible_member_ids``, the fallback narrows and never widens: a
    missing session must not silently turn a leader into an org-wide reader.
    """
    if not is_team_scoped(user):
        return None
    if db is None:
        return set()

    led = set(
        db.scalars(
            select(Project.id).where(
                Project.leader_id == user.id,
                Project.organization_id == user.organization_id,
            )
        ).all()
    )
    staffed = set(
        db.scalars(
            select(ProjectMember.project_id).where(
                ProjectMember.user_id == user.id,
                ProjectMember.organization_id == user.organization_id,
            )
        ).all()
    )
    return led | staffed


def may_view_project(db: Optional[Session], user: User, project_id: int) -> bool:
    """Whether ``user`` may read the project with id ``project_id``."""
    allowed = visible_project_ids(db, user)
    return allowed is None or project_id in allowed
