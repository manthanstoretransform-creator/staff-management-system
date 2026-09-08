"""time_entry_screenshot — Storing, serving and grouping desktop screenshots.

Three responsibilities, in the order the product uses them:

1. **Upload.** Validate the image, authorise it against the *authenticated*
   session rather than against anything the request body claims, put the bytes
   in Google Drive under Year/Month/User/Date, and write the metadata row —
   idempotently on the client's own `client_screenshot_id`.
2. **View.** Stream one screenshot back to a caller who is allowed to see it.
   The bytes are proxied, never linked: a Drive URL would outlive the
   permission check and would require the folder to be public.
3. **Timeline.** Group screenshots and activity into the same fixed windows the
   desktop captures against, so a window's activity percentage describes that
   window and nothing else.
"""
from __future__ import annotations

import logging
from datetime import date as date_type, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time_format import ist_day_end_utc, ist_day_start_utc, ist_today
from app.models.time_entry import TimeEntry
from app.models.time_entry_screenshot import TimeEntryScreenshot
from app.models.user import User
from app.repositories.time_entry import TimeEntryRepository
from app.repositories.time_entry_screenshot import TimeEntryScreenshotRepository
from app.schemas.time_entry_screenshot import TimeEntryScreenshotCreate
from app.services.google_drive_service import (
    GoogleDriveError, GoogleDriveNotAccessible, drive_service,
)
from app.services.member_scope import visible_member_ids

logger = logging.getLogger(__name__)

#: The only image format the desktop produces and the only one accepted.
ALLOWED_MIME_TYPES = {"image/webp"}

#: WebP's container signature: "RIFF" .... "WEBP". Checked against the actual
#: bytes rather than trusting the multipart content type, which the client
#: chooses and can be wrong about — by mistake or otherwise.
_RIFF = b"RIFF"
_WEBP = b"WEBP"


def _expected_dimensions() -> int:
    return 1000


class TimeEntryScreenshotService:
    # ── Authorisation ─────────────────────────────────────────────────────────

    @staticmethod
    def _entry_for_upload(db: Session, time_entry_id: int, current_user: User) -> TimeEntry:
        """The entry a screenshot may be written against, or an error.

        Organization and user are derived here from the authenticated session
        and the entry — never read from the request. A client that could name
        its own `organization_id` could write into another organization's data.
        """
        entry = TimeEntryRepository.get_by_id(db, time_entry_id)
        if not entry or entry.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found",
            )
        if entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot upload screenshots for another user's time entry",
            )
        return entry

    @staticmethod
    def _may_view(
        db: Session,
        screenshot: TimeEntryScreenshot,
        current_user: User,
        entry: Optional[TimeEntry] = None,
    ) -> bool:
        """Whether this caller may see this screenshot.

        The same scope every other read surface uses: your own always; your
        team's if you are a leader; your organization's if your role sees past
        itself. There is no separate screenshot permission model, deliberately
        — a second one would drift out of step with the first.

        `entry` may be supplied by a caller that has already loaded it, to save
        a round trip; it is only ever an optimisation, and the checks applied
        are identical either way.
        """
        if screenshot.organization_id != current_user.organization_id:
            return False
        if entry is None:
            entry = TimeEntryRepository.get_by_id(db, screenshot.time_entry_id)
        if not entry:
            return False
        if entry.user_id == current_user.id:
            return True
        if current_user.role_name == "employee":
            return False
        allowed = visible_member_ids(db, current_user)
        return allowed is None or entry.user_id in allowed

    # ── Validation ────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_image(content: bytes, content_type: Optional[str]) -> Tuple[int, int]:
        """Check the upload really is a WebP of the expected geometry.

        :return: `(width, height)` read from the file itself.
        """
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded screenshot is empty",
            )
        if len(content) > settings.SCREENSHOT_MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"Screenshot exceeds the {settings.SCREENSHOT_MAX_UPLOAD_BYTES} "
                    f"byte limit"
                ),
            )
        if content_type and content_type.split(";")[0].strip() not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported screenshot type '{content_type}'; expected image/webp",
            )
        if not (content[:4] == _RIFF and content[8:12] == _WEBP):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The uploaded file is not a WebP image",
            )

        width, height = TimeEntryScreenshotService._read_dimensions(content)
        expected = _expected_dimensions()
        if width and height and (width != expected or height != expected):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Screenshot must be {expected}x{expected}; "
                    f"received {width}x{height}"
                ),
            )
        return width, height

    @staticmethod
    def _read_dimensions(content: bytes) -> Tuple[int, int]:
        """Read the image's real geometry with Pillow.

        Returns `(0, 0)` when Pillow is not installed, in which case the
        dimension check above is skipped rather than failing every upload — the
        format check has already established the file is a WebP, and refusing
        real screenshots because an optional dependency is missing would be a
        worse outcome than not verifying the size.
        """
        try:
            import io

            from PIL import Image  # type: ignore
        except ImportError:
            logger.warning(
                "Pillow is not installed; screenshot dimensions cannot be verified"
            )
            return 0, 0
        try:
            with Image.open(io.BytesIO(content)) as image:
                return int(image.width), int(image.height)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"The uploaded screenshot could not be decoded: {exc}",
            )

    # ── Upload ────────────────────────────────────────────────────────────────

    @staticmethod
    def upload_screenshot(
        db: Session,
        time_entry_id: int,
        content: bytes,
        content_type: Optional[str],
        client_screenshot_id: str,
        current_user: User,
        captured_at: Optional[datetime] = None,
        monitor_number: int = 1,
    ) -> Tuple[TimeEntryScreenshot, bool]:
        """
        Store one screenshot.

        :return: `(row, duplicate)`. `duplicate` is True when this
            `client_screenshot_id` had already been stored — the desktop's
            retry after a lost response. Nothing is uploaded a second time and
            the original record is returned, which is exactly what the client
            needs to stop retrying and delete its local copy.
        """
        if not client_screenshot_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="client_screenshot_id is required for idempotent upload",
            )

        entry = TimeEntryScreenshotService._entry_for_upload(db, time_entry_id, current_user)

        # Idempotency, checked before any work is done, so the common retry
        # case costs one indexed lookup rather than a Drive upload.
        existing = TimeEntryScreenshotRepository.get_by_client_id(
            db, current_user.organization_id, client_screenshot_id
        )
        if existing is not None:
            logger.info(
                "screenshot %s already stored as id %s; returning the existing record",
                client_screenshot_id, existing.id,
            )
            return existing, True

        width, height = TimeEntryScreenshotService._validate_image(content, content_type)

        if not drive_service.configured:
            # Honest failure: nothing is written, so the desktop keeps the file
            # and retries. Silently accepting an upload we cannot store would
            # make the client delete its only copy.
            #
            # The reason goes to the log, not to the response: the client
            # cannot act on it, and naming which server-side setting is missing
            # in an HTTP body describes this deployment to whoever asked.
            logger.error(
                "refusing screenshot upload: Google Drive storage is not "
                "configured (%s)",
                drive_service.unconfigured_reason(),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Screenshot storage is not configured on this server",
            )

        when = captured_at or datetime.now(timezone.utc)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)

        file_name = f"screenshot_{client_screenshot_id}.webp"
        try:
            # The folder is named for the entry's owner, not for the caller —
            # they are the same person on the upload path today, but naming a
            # folder after whoever happened to send the request is the kind of
            # assumption that silently misfiles data the moment it stops
            # holding.
            owner = db.get(User, entry.user_id)
            folder_id, logical_path = drive_service.ensure_screenshot_folder(
                user_id=entry.user_id,
                captured_on=when.astimezone(timezone.utc).date(),
                user_name=getattr(owner, "name", None),
            )
            file_id = drive_service.upload_file(
                folder_id=folder_id,
                file_name=file_name,
                content=content,
                mime_type="image/webp",
            )
        except GoogleDriveNotAccessible as exc:
            # A misconfiguration, not an outage. Reported as 503 so it reads as
            # "this server cannot store screenshots" rather than as a blip the
            # client should expect to clear on its own.
            logger.error("screenshot storage is misconfigured: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Screenshot storage is not available on this server",
            )
        except GoogleDriveError as exc:
            logger.error("Drive upload failed for %s: %s", client_screenshot_id, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Screenshot storage is temporarily unavailable",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("unexpected Drive failure for %s", client_screenshot_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Screenshot storage is temporarily unavailable",
            ) from exc

        try:
            record = TimeEntryScreenshotRepository.create_uploaded(
                db=db,
                organization_id=current_user.organization_id,
                time_entry_id=time_entry_id,
                captured_at=when,
                file_path=f"{logical_path}/{file_name}",
                file_name=file_name,
                google_drive_file_id=file_id,
                google_drive_folder_id=folder_id,
                file_size_bytes=len(content),
                mime_type="image/webp",
                width=width or None,
                height=height or None,
                monitor_number=monitor_number,
                client_screenshot_id=client_screenshot_id,
            )
        except IntegrityError:
            # Two uploads of the same capture raced past the lookup above. The
            # unique index is what makes that safe; the loser discards its own
            # Drive object and returns the winner's row, so the retry still
            # sees a success and the orphan does not accumulate.
            db.rollback()
            drive_service.delete_file(file_id)
            winner = TimeEntryScreenshotRepository.get_by_client_id(
                db, current_user.organization_id, client_screenshot_id
            )
            if winner is None:
                raise
            return winner, True

        logger.info(
            "stored screenshot %s for entry %s as Drive file %s (%d bytes)",
            client_screenshot_id, time_entry_id, file_id, len(content),
        )
        return record, False

    # ── View ──────────────────────────────────────────────────────────────────

    @staticmethod
    def get_screenshot_bytes(
        db: Session, screenshot_id: int, current_user: User
    ) -> Tuple[bytes, str, str]:
        """
        Read one screenshot back for an authorised caller.

        :return: `(content, mime_type, file_name)`.
        """
        # Both rows in one round trip; the database answers in ~80ms and a
        # grid pays this per thumbnail.
        record, entry = TimeEntryScreenshotRepository.get_with_entry(db, screenshot_id)
        if not record or not TimeEntryScreenshotService._may_view(
            db, record, current_user, entry=entry
        ):
            # A screenshot the caller may not see is reported as absent rather
            # than as forbidden: "403" on an id you guessed confirms the id
            # exists, which is itself information about another user's day.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Screenshot not found",
            )
        if not record.google_drive_file_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="This screenshot has no stored image",
            )
        try:
            content = drive_service.download_file(record.google_drive_file_id)
        except GoogleDriveError as exc:
            logger.error("could not read Drive file %s: %s", record.google_drive_file_id, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Screenshot storage is temporarily unavailable",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("unexpected failure reading Drive file %s", record.google_drive_file_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Screenshot storage is temporarily unavailable",
            ) from exc
        return content, record.mime_type or "image/webp", record.file_name or f"screenshot_{record.id}.webp"

    # ── Timeline ──────────────────────────────────────────────────────────────

    @staticmethod
    def get_timeline(
        db: Session,
        current_user: User,
        user_id: Optional[int] = None,
        target_date: Optional[date_type] = None,
    ) -> Tuple[int, List[dict]]:
        """
        Screenshots and activity for one IST day, grouped into fixed windows.

        Windows are derived from timestamps rather than stored on the rows:
        `captured_at` and `recorded_at` are bucketed by the same epoch-aligned
        arithmetic the desktop schedules against, so nothing has to be
        backfilled and changing the window length is a configuration change
        rather than a migration.

        Only windows that contain a screenshot or measured activity are
        returned — an untracked hour produces no empty blocks to scroll past.

        :return: `(window_minutes, windows)`.
        """
        subject_id = TimeEntryScreenshotService._resolve_subject(db, current_user, user_id)
        day = target_date or ist_today()
        start = ist_day_start_utc(day)
        end = ist_day_end_utc(day)
        window_minutes = max(1, int(settings.SCREENSHOT_WINDOW_MINUTES))
        window_seconds = window_minutes * 60

        screenshots = TimeEntryScreenshotRepository.list_screenshots(
            db=db,
            organization_id=current_user.organization_id,
            user_id=subject_id,
            start=start,
            end=end,
            # A tracked day at one capture per ten minutes is ~144 rows; the
            # ceiling is generous enough for a future five-per-window setting.
            limit=5000,
        )
        activity = TimeEntryScreenshotRepository.get_activity_totals_in_range(
            db=db,
            organization_id=current_user.organization_id,
            user_id=subject_id,
            start=start,
            end=end,
        )

        buckets: Dict[int, dict] = {}

        def bucket(when: datetime) -> dict:
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            index = int(when.timestamp() // window_seconds)
            return buckets.setdefault(index, {
                "index": index,
                "screenshots": [],
                "weighted": 0.0,
                "measured": 0,
            })

        for shot in screenshots:
            bucket(shot.captured_at)["screenshots"].append(shot)

        for recorded_at, percentage, seconds in activity:
            if seconds <= 0:
                continue
            slot = bucket(recorded_at)
            slot["weighted"] += percentage * seconds
            slot["measured"] += seconds

        windows: List[dict] = []
        for index in sorted(buckets):
            slot = buckets[index]
            window_start = datetime.fromtimestamp(index * window_seconds, tz=timezone.utc)
            measured = slot["measured"]
            # Weighted by duration, so a 12-second tail window cannot count as
            # much as a full one. Zero measured seconds means "not measured",
            # which is reported as 0% alongside the measured count so a caller
            # can tell the two apart.
            percentage = int(round(slot["weighted"] / measured)) if measured else 0
            shots = sorted(slot["screenshots"], key=lambda s: s.captured_at)
            windows.append({
                "window_start": window_start,
                "window_end": window_start + timedelta(seconds=window_seconds),
                "activity_percentage": max(0, min(100, percentage)),
                "activity_measured_seconds": measured,
                "screenshots": [
                    {
                        "id": s.id,
                        "captured_at": s.captured_at,
                        "monitor_number": s.monitor_number,
                        "width": s.width,
                        "height": s.height,
                        "file_size_bytes": s.file_size_bytes,
                        "view_url": f"/time-entry-screenshots/{s.id}/view",
                    }
                    for s in shots
                ],
                "screenshot_count": len(shots),
            })
        return window_minutes, windows

    @staticmethod
    def _resolve_subject(db: Session, current_user: User, user_id: Optional[int]) -> int:
        """Whose day is being read, after scope enforcement."""
        if user_id is None or user_id == current_user.id:
            return current_user.id
        if current_user.role_name == "employee":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You may only view your own screenshots",
            )
        allowed = visible_member_ids(db, current_user)
        if allowed is not None and user_id not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This member is outside your visible team",
            )
        return user_id

    # ── Existing surface (unchanged behaviour) ────────────────────────────────

    @staticmethod
    def create_screenshot(
        db: Session,
        payload: TimeEntryScreenshotCreate,
        current_user: User
    ) -> TimeEntryScreenshot:
        # Verify time entry exists and belongs to the user's organization
        time_entry = TimeEntryRepository.get_by_id(db, payload.time_entry_id)
        if not time_entry or time_entry.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found"
            )
        # If employee, ensure they own the time entry
        if current_user.role_name == "employee" and time_entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to add screenshots to this time entry"
            )

        return TimeEntryScreenshotRepository.create(
            db=db,
            organization_id=current_user.organization_id,
            time_entry_id=payload.time_entry_id,
            file_path=payload.file_path,
            monitor_number=payload.monitor_number,
            captured_at=payload.captured_at
        )

    @staticmethod
    def list_screenshots(
        db: Session,
        time_entry_id: Optional[int],
        user_id: Optional[int],
        limit: int,
        current_user: User
    ) -> List[TimeEntryScreenshot]:
        # Enforce scoping: employees can only list their own screenshots
        target_user_id = user_id
        if current_user.role_name == "employee":
            target_user_id = current_user.id

        # And a leader only their team's -- the same set `member_scope` hands
        # the member directory and the time-tracking listing. `None` is "no
        # restriction", which is every other role, and a `user_id` on the query
        # string is filtered against the set rather than trusted.
        return TimeEntryScreenshotRepository.list_screenshots(
            db=db,
            organization_id=current_user.organization_id,
            user_id=target_user_id,
            time_entry_id=time_entry_id,
            limit=limit,
            user_ids=visible_member_ids(db, current_user),
        )
