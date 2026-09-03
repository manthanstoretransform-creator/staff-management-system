from sqlalchemy import (
    BigInteger, Identity, Index, String, TIMESTAMP, ForeignKeyConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.core.database import Base


class DesktopClientVersion(Base):
    """The desktop version last seen for one user — fleet update visibility.

    Support cannot answer "did everyone move off the bad build?" or "is anyone
    still on a version too old to upload activity?" without a record of what
    each installed client is actually running. This table is that record, and
    deliberately nothing more.

    **Scope of collection.** One row per user, overwritten in place: the
    version string the desktop already sends in its `User-Agent`
    (`Monitra/1.0.1`), the OS family it reported, and when it was last seen.
    No history, no hostname, no machine identifier, no per-request log. The
    question being answered is "which version is this person on", so a single
    current value answers it; keeping a trail would collect materially more
    about staff machines than the decision approved.

    Rows are written from the desktop's own periodic update check
    (`GET /desktop/latest-version`), which is authenticated and already runs
    on a low-frequency loop — so recording a version costs no extra request
    and no per-request database write on the hot path.
    """

    __tablename__ = 'desktop_client_versions'

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    #: One row per user. Unique, because this is a current-state table, not a
    #: history: a new report overwrites the previous one.
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)

    #: The `major.minor.patch` string the client reported, exactly as sent.
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)
    #: OS family, as `sys.platform` names it ("win32", "darwin", "linux").
    #: Needed because Windows and macOS releases are separate artifacts and a
    #: rollout can be complete on one platform and not the other.
    platform: Mapped[str | None] = mapped_column(String(32), nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(),
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ['organization_id'], ['organizations.id'],
            name='fk_desktop_client_versions_org', ondelete='CASCADE',
        ),
        ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name='fk_desktop_client_versions_user', ondelete='CASCADE',
        ),
        Index('ix_desktop_client_versions_organization_id', 'organization_id'),
        Index('ix_desktop_client_versions_app_version', 'app_version'),
    )
