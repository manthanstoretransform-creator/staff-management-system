from sqlalchemy import BigInteger, SmallInteger, Text, TIMESTAMP, Identity, ForeignKeyConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base

class TimeEntryScreenshot(Base):
    __tablename__ = 'time_entry_screenshots'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    time_entry_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    monitor_number: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='time_entry_screenshots_organization_id_fkey', ondelete='CASCADE'),
        ForeignKeyConstraint(['time_entry_id'], ['time_entries.id'], name='time_entry_screenshots_time_entry_id_fkey', ondelete='CASCADE'),
    )

    # Relationships
    time_entry: Mapped["TimeEntry"] = relationship("TimeEntry")
