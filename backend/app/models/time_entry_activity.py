from sqlalchemy import BigInteger, Integer, SmallInteger, TIMESTAMP, Identity, ForeignKeyConstraint, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base


class TimeEntryActivity(Base):
    """Per-time_entry productivity snapshots (keyboard/mouse activity samples).

    No writer populates this table today -- the desktop's activity batch-sync
    endpoint doesn't exist yet (see CLAUDE.md Known open items #1), so reads
    against it are expected to return no rows until that pipeline is built.
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
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_time_entry_activity_org', ondelete='CASCADE'),
        ForeignKeyConstraint(['time_entry_id'], ['time_entries.id'], name='fk_time_entry_activity_entry', ondelete='CASCADE'),
        CheckConstraint('activity_percentage >= 0 AND activity_percentage <= 100', name='time_entry_activity_activity_percentage_check'),
    )

    time_entry: Mapped["TimeEntry"] = relationship("TimeEntry")
