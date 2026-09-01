from sqlalchemy import (
    BigInteger, CheckConstraint, Integer, String, TIMESTAMP, Text, Identity,
    ForeignKeyConstraint, Index, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base


class TimeEntryAdjustment(Base):
    """A signed, auditable correction to a time entry's reportable seconds.

    The original `time_entries.total_seconds` is NEVER modified by an
    adjustment -- that value stays exactly what the timer measured (and is
    what the desktop's offline sync reconciles against). Reportable time is
    computed as `total_seconds + SUM(adjustment_seconds)` wherever reports
    aggregate durations, so every deduction remains individually visible:
    who, which entry, how many seconds, why, and which detected activity
    triggered it.

    `adjustment_seconds` is negative for a deduction (e.g. -600 for the
    "three unwanted-activity occurrences" rule). Positive credits are
    allowed by the schema for future use but nothing writes them today.
    """
    __tablename__ = 'time_entry_adjustments'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    time_entry_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    adjustment_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    #: What triggered this adjustment, denormalized for the audit trail even
    #: if the linked unwanted-activity row is ever removed.
    source_activity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_key_or_action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unwanted_activity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    #: Client-generated idempotency key (the desktop queues adjustments
    #: offline; a retry must not deduct twice).
    client_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_time_entry_adjustments_org', ondelete='CASCADE'),
        ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_time_entry_adjustments_user', ondelete='CASCADE'),
        ForeignKeyConstraint(['project_id'], ['projects.id'], name='fk_time_entry_adjustments_project', ondelete='CASCADE'),
        ForeignKeyConstraint(['task_id'], ['tasks.id'], name='fk_time_entry_adjustments_task', ondelete='CASCADE'),
        ForeignKeyConstraint(['time_entry_id'], ['time_entries.id'], name='fk_time_entry_adjustments_entry', ondelete='CASCADE'),
        ForeignKeyConstraint(['unwanted_activity_id'], ['time_entry_unwanted_activity.id'], name='fk_time_entry_adjustments_unwanted', ondelete='SET NULL'),
        CheckConstraint('adjustment_seconds <> 0', name='ck_time_entry_adjustments_nonzero'),
        Index('ix_time_entry_adjustments_time_entry_id', 'time_entry_id'),
        Index('ix_time_entry_adjustments_organization_id', 'organization_id'),
        Index('ix_time_entry_adjustments_recorded_at', 'recorded_at'),
    )

    time_entry: Mapped["TimeEntry"] = relationship("TimeEntry")
