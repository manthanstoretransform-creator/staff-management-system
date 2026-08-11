from sqlalchemy import BigInteger, Integer, String, Boolean, Text, Date, TIMESTAMP, Identity, ForeignKeyConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date, datetime
from app.core.database import Base

class ManualTimeEntry(Base):
    __tablename__ = 'manual_time_entries'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    total_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending')
    approved_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_manual_time_org', ondelete='CASCADE'),
        ForeignKeyConstraint(['project_id'], ['projects.id'], name='fk_manual_time_project', ondelete='CASCADE'),
        ForeignKeyConstraint(['task_id'], ['tasks.id'], name='fk_manual_time_task', ondelete='CASCADE'),
        ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_manual_time_user', ondelete='CASCADE'),
        ForeignKeyConstraint(['approved_by'], ['users.id'], name='fk_manual_time_approved_by', ondelete='SET NULL'),
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")
    task: Mapped["Task"] = relationship("Task")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    approver: Mapped["User | None"] = relationship("User", foreign_keys=[approved_by])
