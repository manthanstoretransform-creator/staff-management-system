from sqlalchemy import BigInteger, TIMESTAMP, Identity, ForeignKeyConstraint, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base

class TaskAssignee(Base):
    __tablename__ = 'task_assignees'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    assigned_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(['task_id'], ['tasks.id'], name='fk_task_assignees_task', ondelete='CASCADE'),
        UniqueConstraint('task_id', 'user_id', name='uq_task_assignee'),
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task")
