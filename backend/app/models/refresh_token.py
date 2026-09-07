from sqlalchemy import BigInteger, String, TIMESTAMP, Identity, ForeignKeyConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional
from app.core.database import Base

class RefreshToken(Base):
    __tablename__ = 'refresh_tokens'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    token_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    #: When the *sign-in* this token descends from happened. Rotation copies it
    #: forward unchanged, which is what stops a silently refreshing client from
    #: living forever: `expires_at` is always session_started_at + the session
    #: window, never "now + the window".
    session_started_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_refresh_tokens_user', ondelete='CASCADE'),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")
