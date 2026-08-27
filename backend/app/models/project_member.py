from sqlalchemy import BigInteger, Date, TIMESTAMP, Identity, ForeignKeyConstraint, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date, datetime
from app.core.database import Base

class ProjectMember(Base):
    __tablename__ = 'project_members'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    joined_at: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_project_members_org', ondelete='CASCADE'),
        ForeignKeyConstraint(['project_id'], ['projects.id'], name='fk_project_members_project', ondelete='CASCADE'),
        ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_project_members_user', ondelete='CASCADE'),
        UniqueConstraint('project_id', 'user_id', name='uq_project_member'),
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")
