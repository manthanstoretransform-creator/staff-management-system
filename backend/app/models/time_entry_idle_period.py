from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Integer, String, TIMESTAMP, Identity,
    ForeignKeyConstraint, Index, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base


class IdlePeriodStatus:
    """Lifecycle of one idle period. Stored as a string, like every other
    status column in this schema (`time_entries.status`, `tasks.status`), and
    constrained by a CHECK rather than a PostgreSQL enum so adding a state
    later does not need an ALTER TYPE."""

    PENDING = "pending"
    RESOLVED = "resolved"

    ALL = (PENDING, RESOLVED)


class IdlePeriodAction:
    """What the user did with the timer when they dismissed the idle popup."""

    STOP = "stop"
    RESUME = "resume"

    ALL = (STOP, RESUME)


class TimeEntryIdlePeriod(Base):
    """One stretch of keyboard/mouse inactivity during a running time entry.

    The desktop detects the inactivity; this row is the authoritative record
    of it. The timer keeps running throughout -- an idle period never edits
    `time_entries.total_seconds`. Instead, idle time that must NOT be counted
    is removed through a negative `time_entry_adjustments` row, the same
    mechanism the unwanted-activity rules already use, so every aggregation
    that already nets adjustments accounts for discarded idle time without
    any per-report special casing.

    Idle time is counted only when `keep_idle_time` is true AND `action` is
    `resume`; see `TimeEntryIdlePeriodService.counts_idle_time`. Every other
    combination -- including "keep" followed by "stop" -- discards it.

    Reassignment attributes the idle seconds elapsed up to the moment the user
    pressed Reassign to a different project/task by creating a *separate*,
    already-stopped time entry (`reassigned_time_entry_id`) covering exactly
    that window, and deducting the same number of seconds from the original
    entry. The seconds are therefore counted exactly once, under the
    destination project/task, and the work done before the idle period stays
    with the original project/task.
    """

    __tablename__ = 'time_entry_idle_periods'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    time_entry_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    #: The project/task the original entry was tracking when the user went
    #: idle, denormalized so the audit trail survives a later reassignment.
    original_project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    #: Last observed keyboard/mouse activity -- where the idle period begins.
    idle_started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    #: When the user's `idle_minutes` threshold was crossed and the popup was
    #: raised. Never the end of the idle period: the popup is modal and the
    #: user may leave it open for much longer.
    idle_detected_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    #: When the user finally answered the popup. NULL while pending.
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    #: `resolved_at - idle_started_at`, written once at resolution. This is
    #: the ACTUAL idle duration, which is >= the user's idle_minutes.
    idle_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    keep_idle_time: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    action: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: The decision the server made, not the one the client asked for:
    #: `keep_idle_time AND action == 'resume'`.
    counted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    reassigned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    reassigned_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    reassigned_project_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reassigned_task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    #: The stopped time entry created for the destination project/task.
    reassigned_time_entry_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    #: Seconds moved to the destination. Always <= idle_duration_seconds.
    reassigned_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Client-generated idempotency key: the desktop reports the threshold
    #: through the same durable queue as everything else, so a retry must
    #: return the existing row rather than open a second idle period.
    client_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_idle_periods_org', ondelete='CASCADE'),
        ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_idle_periods_user', ondelete='CASCADE'),
        ForeignKeyConstraint(['time_entry_id'], ['time_entries.id'], name='fk_idle_periods_entry', ondelete='CASCADE'),
        ForeignKeyConstraint(['original_project_id'], ['projects.id'], name='fk_idle_periods_original_project', ondelete='CASCADE'),
        ForeignKeyConstraint(['original_task_id'], ['tasks.id'], name='fk_idle_periods_original_task', ondelete='CASCADE'),
        ForeignKeyConstraint(['reassigned_project_id'], ['projects.id'], name='fk_idle_periods_reassigned_project', ondelete='SET NULL'),
        ForeignKeyConstraint(['reassigned_task_id'], ['tasks.id'], name='fk_idle_periods_reassigned_task', ondelete='SET NULL'),
        ForeignKeyConstraint(['reassigned_time_entry_id'], ['time_entries.id'], name='fk_idle_periods_reassigned_entry', ondelete='SET NULL'),
        CheckConstraint("status IN ('pending', 'resolved')", name='ck_idle_periods_status'),
        CheckConstraint("action IS NULL OR action IN ('stop', 'resume')", name='ck_idle_periods_action'),
        CheckConstraint('idle_detected_at >= idle_started_at', name='ck_idle_periods_detected_after_start'),
        CheckConstraint('resolved_at IS NULL OR resolved_at >= idle_started_at', name='ck_idle_periods_resolved_after_start'),
        CheckConstraint('idle_duration_seconds IS NULL OR idle_duration_seconds >= 0', name='ck_idle_periods_duration_nonneg'),
        CheckConstraint('reassigned_seconds IS NULL OR reassigned_seconds > 0', name='ck_idle_periods_reassigned_seconds_positive'),
        # A resolved row is never ambiguous: it always carries the answer,
        # the action, the server's counting decision and the duration.
        CheckConstraint(
            "status <> 'resolved' OR ("
            "resolved_at IS NOT NULL AND keep_idle_time IS NOT NULL "
            "AND action IS NOT NULL AND counted IS NOT NULL "
            "AND idle_duration_seconds IS NOT NULL)",
            name='ck_idle_periods_resolved_complete',
        ),
        # A reassigned row always carries a complete destination.
        CheckConstraint(
            "reassigned = false OR ("
            "reassigned_at IS NOT NULL AND reassigned_project_id IS NOT NULL "
            "AND reassigned_task_id IS NOT NULL AND reassigned_seconds IS NOT NULL)",
            name='ck_idle_periods_reassigned_complete',
        ),
        # At most one unresolved idle period per time entry -- enforced by the
        # database, not only by the service, because two retries of the same
        # threshold report can race.
        Index(
            'uq_idle_periods_pending_entry', 'time_entry_id', unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            'uq_idle_periods_client_event_id', 'client_event_id', unique=True,
            postgresql_where=text('client_event_id IS NOT NULL'),
        ),
        Index(
            'uq_idle_periods_reassigned_entry', 'reassigned_time_entry_id', unique=True,
            postgresql_where=text('reassigned_time_entry_id IS NOT NULL'),
        ),
        Index('ix_idle_periods_time_entry_id', 'time_entry_id'),
        Index('ix_idle_periods_organization_id', 'organization_id'),
        Index('ix_idle_periods_user_id', 'user_id'),
        Index('ix_idle_periods_idle_started_at', 'idle_started_at'),
    )

    time_entry: Mapped["TimeEntry"] = relationship("TimeEntry", foreign_keys=[time_entry_id])
