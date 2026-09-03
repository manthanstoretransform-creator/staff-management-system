from sqlalchemy import (
    BigInteger, Identity, Index, String, Text, TIMESTAMP, ForeignKeyConstraint,
    text, func,
)
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.core.database import Base


class FeedbackRequest(Base):
    """One piece of feedback or help request submitted from a Monitra client.

    The desktop's "Feedback & Help" dialog writes here. Every row is owned by
    the authenticated user who submitted it and by that user's organization —
    both are taken from the access token server-side, never from the request
    body, so a client cannot file feedback as somebody else or against another
    tenant.

    `status` exists for a future support/admin workflow. Submissions always
    start at ``'new'``; the submitting client has no say in it.
    """

    __tablename__ = 'feedback_requests'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    #: One of FeedbackCategory. Stored as a validated string rather than a
    #: database enum, matching how every other status-like column in this
    #: schema is stored (see Task.status, TimeEntry.status).
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    #: The user's message, stored verbatim apart from surrounding whitespace.
    message: Mapped[str] = mapped_column(Text, nullable=False)
    #: One of FeedbackStatus; always 'new' at creation time.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'new'"),
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ['organization_id'], ['organizations.id'],
            name='fk_feedback_requests_organization', ondelete='CASCADE',
        ),
        ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name='fk_feedback_requests_user', ondelete='CASCADE',
        ),
        Index('idx_feedback_requests_org_status', 'organization_id', 'status'),
        Index('idx_feedback_requests_user_created_at', 'user_id', 'created_at'),
    )
