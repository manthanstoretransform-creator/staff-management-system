from sqlalchemy import (
    BigInteger, Boolean, Integer, String, TIMESTAMP, Identity,
    ForeignKeyConstraint, Index, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base


class TimeEntryUnwantedActivity(Base):
    """Suspicious/unwanted input detected during an active tracking session.

    One row per detection *event* (a rule's threshold being crossed once,
    e.g. "CTRL pressed 15+ times inside the rule's window"), not one row
    per key press. The desktop client owns the detection rules and posts
    events here as they trigger; `occurrence_count` is how many matching
    inputs were seen inside the triggering window, `alerted`/`alert_count`
    record whether and how many times the user has been warned for this
    rule within the same time entry.
    """
    __tablename__ = 'time_entry_unwanted_activity'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    time_entry_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    key_or_action: Mapped[str] = mapped_column(String(100), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alerted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    alert_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    #: Client-generated idempotency key: the desktop queues these offline and
    #: retries with backoff, so a retry after a lost response must not insert
    #: a duplicate event.
    client_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_unwanted_activity_org', ondelete='CASCADE'),
        ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_unwanted_activity_user', ondelete='CASCADE'),
        ForeignKeyConstraint(['project_id'], ['projects.id'], name='fk_unwanted_activity_project', ondelete='CASCADE'),
        ForeignKeyConstraint(['task_id'], ['tasks.id'], name='fk_unwanted_activity_task', ondelete='CASCADE'),
        ForeignKeyConstraint(['time_entry_id'], ['time_entries.id'], name='fk_unwanted_activity_entry', ondelete='CASCADE'),
        Index('ix_unwanted_activity_time_entry_id', 'time_entry_id'),
        Index('ix_unwanted_activity_organization_id', 'organization_id'),
        Index('ix_unwanted_activity_recorded_at', 'recorded_at'),
    )

    time_entry: Mapped["TimeEntry"] = relationship("TimeEntry")
