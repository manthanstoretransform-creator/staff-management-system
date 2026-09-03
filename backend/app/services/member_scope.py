"""Which people a caller is allowed to *see*.

``time_entries:view_all`` and ``view_employees`` answer "may this caller look
past themselves?" — they do not answer "at whom?". For an admin, an org_admin,
a manager or HR the answer is the whole organization. For a **leader** it is
their own team: the people an admin put on the projects that leader leads,
plus the leader themselves.

One helper, used by every read surface (member directory, member details,
dashboard, reports, time tracking, manual time entry listings), so a leader's
scope cannot be right on one screen and wrong on the next.

Two things this deliberately does *not* touch:

* **Assignable-member pickers.** When a leader creates a project they choose
  freely from the whole organization — narrowing the picker would make it
  impossible to build a team. Scoping applies to reading other people's
  recorded work, not to staffing.
* **Anyone without ``time_entries:view_all`` / ``view_employees``.** They are
  already pinned to themselves by the caller-side checks that were there
  before; this helper only narrows the "sees other people" case.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User

#: The role names whose visibility is their own team rather than the whole
#: organization. Both spellings of the leader role are covered, matching
#: ``ProjectMemberService.LEADER_ROLES``.
TEAM_SCOPED_ROLES = frozenset({"leader", "project_leader"})


def is_team_scoped(user: User) -> bool:
    """Whether this caller sees a team rather than the organization."""
    return getattr(user, "role_name", None) in TEAM_SCOPED_ROLES


def visible_member_ids(db: Optional[Session], user: User) -> Optional[set[int]]:
    """The member ids this caller may read, or ``None`` for "no restriction".

    ``None`` means the organization, and is what every non-leader role gets —
    callers can then skip the filter entirely rather than building an ``IN``
    list of the whole company.

    With no session to ask (``db is None``) a team-scoped caller falls back to
    just themselves. The fallback narrows and never widens: a missing session
    must not silently turn a leader into an org-wide reader.
    """
    if not is_team_scoped(user):
        return None
    if db is None:
        return {user.id}

    led_projects = select(Project.id).where(
        Project.leader_id == user.id,
        Project.organization_id == user.organization_id,
    )
    member_ids = set(
        db.scalars(
            select(ProjectMember.user_id).where(
                ProjectMember.project_id.in_(led_projects),
                ProjectMember.organization_id == user.organization_id,
            )
        ).all()
    )
    # A leader is always part of their own team, so their own dashboard and
    # their own time are never empty even before a project is assigned.
    member_ids.add(user.id)
    return member_ids


def may_view_member(db: Optional[Session], user: User, member_id: int) -> bool:
    """Whether ``user`` may read the person with id ``member_id``."""
    allowed = visible_member_ids(db, user)
    return allowed is None or member_id in allowed
