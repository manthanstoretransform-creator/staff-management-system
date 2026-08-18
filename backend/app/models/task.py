from app.models.project import Project
from sqlalchemy import BigInteger, String, Text, Integer, Date, TIMESTAMP, Numeric, Identity, ForeignKeyConstraint, text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date, datetime
from typing import Optional
from app.core.database import Base

class Task(Base):
    __tablename__ = 'tasks'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    task_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'todo'"))
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    estimated_hours: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    time_tracked_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        nullable=False, 
        server_default=func.now(), 
        onupdate=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_tasks_organization', ondelete='CASCADE'),
        ForeignKeyConstraint(['project_id'], ['projects.id'], name='fk_tasks_project', ondelete='CASCADE'),
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")
