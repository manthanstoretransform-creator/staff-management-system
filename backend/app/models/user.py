from sqlalchemy import BigInteger, String, Boolean, Integer, TIMESTAMP, Identity, ForeignKeyConstraint, text, func, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from typing import List, Optional
from app.core.database import Base

# Stub table for organizations so SQLAlchemy can resolve foreign keys
Table(
    'organizations',
    Base.metadata,
    Column('id', BigInteger, primary_key=True)
)

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    hubstaff_user_id: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    username: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    designation: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role_name: Mapped[str] = mapped_column(String, nullable=False)
    permissions: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    wp_capabilities: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    idle_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    idle_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('5'))
    capture_frequency: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'active'"))
    created_at: Mapped[func.now] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[func.now] = mapped_column(
        TIMESTAMP(timezone=True), 
        nullable=False, 
        server_default=func.now(), 
        onupdate=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_users_organization', ondelete='CASCADE'),
    )

    # Relationships
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
