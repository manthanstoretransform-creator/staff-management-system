from sqlalchemy import BigInteger, Integer, String, Boolean, Text, TIMESTAMP, Identity, ForeignKeyConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base
from app.models.project import Project  # Adjust the import path if your folder structure is different
from app.models.task import Task
from app.models.user import User


class TimeEntry(Base):
    __tablename__ = 'time_entries'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    start_time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    total_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='running')
    is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='time_entries_organization_id_fkey', ondelete='CASCADE'),
        ForeignKeyConstraint(['project_id'], ['projects.id'], name='time_entries_project_id_fkey', ondelete='CASCADE'),
        ForeignKeyConstraint(['task_id'], ['tasks.id'], name='time_entries_task_id_fkey', ondelete='CASCADE'),
        ForeignKeyConstraint(['user_id'], ['users.id'], name='time_entries_user_id_fkey', ondelete='CASCADE'),
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")
    task: Mapped["Task"] = relationship("Task")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
