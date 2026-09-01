from sqlalchemy import BigInteger, Integer, SmallInteger, String, TIMESTAMP, Identity, ForeignKeyConstraint, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base


class TimeEntryActivity(Base):
    """Per-time_entry productivity snapshots (keyboard/mouse activity samples).

    Written by the desktop client's activity pipeline: one row per
    aggregated capture window (60s), batch-uploaded through
    POST /time-entries/{id}/activity/batch with client-generated
    idempotency keys, since the desktop queues windows offline and retries
    with backoff.
    """
    __tablename__ = 'time_entry_activity'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    time_entry_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    keyboard_strokes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mouse_clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mouse_movements: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activity_percentage: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    #: Client-generated idempotency key -- a retried batch upload after a
    #: lost response must not double-insert the same window.
    client_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_time_entry_activity_org', ondelete='CASCADE'),
        ForeignKeyConstraint(['time_entry_id'], ['time_entries.id'], name='fk_time_entry_activity_entry', ondelete='CASCADE'),
        CheckConstraint('activity_percentage >= 0 AND activity_percentage <= 100', name='time_entry_activity_activity_percentage_check'),
    )

    time_entry: Mapped["TimeEntry"] = relationship("TimeEntry")
