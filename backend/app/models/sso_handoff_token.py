from sqlalchemy import BigInteger, String, TIMESTAMP, Identity, ForeignKeyConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional
from app.core.database import Base


class SsoHandoffToken(Base):
    """One desktop-to-web sign-in handoff.

    The desktop client already holds a valid local session, so it asks the
    backend to mint a very short-lived handoff token and opens the web client
    with it in the URL. The row exists so the token can only ever be redeemed
    once: a URL is read by the browser, kept in history and may be re-opened,
    and a credential that survives being replayed is not a handoff, it is a
    second password.

    Only the hash is stored, for the same reason refresh tokens store only a
    hash: a database dump must not hand anyone a usable credential.
    """

    __tablename__ = 'sso_handoff_tokens'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    #: Set the moment the token is exchanged. A row with this set is spent and
    #: is never accepted again, whatever its expiry says.
    used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_sso_handoff_tokens_user', ondelete='CASCADE'),
    )

    user: Mapped["User"] = relationship("User")
