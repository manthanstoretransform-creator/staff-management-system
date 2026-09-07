"""google_drive_service — The only place this application talks to Google Drive.

Credential handling
-------------------
The service account key is read from settings, which read it from the
environment. It is never logged, never returned in a response, and never sent
to the desktop client: the desktop uploads an image to this backend over its
ordinary authenticated session, and this module is what puts the bytes in
Drive. `describe_configuration()` deliberately reports only whether a
credential is present and which folder is the root — never any part of the key
itself, so it is safe in a health endpoint and in a log line.

Folder layout
-------------
    <root>/<year>/<month name>/User_<id>/<YYYY-MM-DD>/<file>

Each level is looked up by name inside its parent and created only if missing.
Two things make that safe under concurrency, which matters because a dozen
desktop clients can upload their first screenshot of a month within the same
second:

* Lookups are cached per (parent, name) for the process lifetime. Folder ids
  never change, and the alternative is a Drive query per level per upload —
  four extra round trips on every screenshot.
* A create that races another creates a *second* folder with the same name,
  because Drive permits duplicate names. So after creating, the code re-queries
  and keeps the **oldest** match, and every process converges on the same
  folder. Without that step a month boundary would quietly fan a team's
  screenshots across several identically named folders.

The Google client libraries are imported lazily so the rest of the backend —
and its test suite — runs without them installed.
"""
from __future__ import annotations

import io
import json
import logging
import threading
from datetime import date
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from app.core.config import settings

logger = logging.getLogger(__name__)

#: Drive's own type for a folder.
FOLDER_MIME = "application/vnd.google-apps.folder"

#: Write + read of files this service account created. Deliberately not
#: `drive`, which would grant the whole of the user's Drive.
SCOPES = ["https://www.googleapis.com/auth/drive"]


class GoogleDriveError(RuntimeError):
    """A Drive operation failed. Carries no credential material."""


class GoogleDriveNotAccessible(GoogleDriveError):
    """The configured root folder cannot be reached by the service account.

    Kept distinct from the general error because the two need opposite
    responses. A transient Drive failure is worth retrying; this one never
    resolves on its own — the folder is not shared, or the id names a shared
    drive this account is not a member of — and Drive reports it as a bare 404
    that reads exactly like a missing file. Surfacing it as "temporarily
    unavailable" would have every client in the fleet retry a permanent
    misconfiguration until their retry budgets ran out.
    """


def normalize_folder_id(value: str) -> str:
    """Accept either a Drive folder id or the URL a person actually copies.

    Nobody reads a folder id out of Drive; they open the folder and copy the
    address bar. Passing that whole URL to the API as a parent id fails with a
    404 that says nothing about the real cause, and the operator's natural next
    move — re-checking that the folder is shared — does not fix it. Since the
    id is unambiguously recoverable from every URL form Drive produces, taking
    the URL is strictly better than rejecting it.

    Handles:
        https://drive.google.com/drive/folders/<id>?usp=sharing
        https://drive.google.com/drive/u/0/folders/<id>
        https://drive.google.com/open?id=<id>
        <id>
    """
    text = (value or "").strip().strip('"').strip("'")
    if not text or "/" not in text and "?" not in text:
        return text

    parsed = urlparse(text)
    query_id = parse_qs(parsed.query).get("id")
    if query_id and query_id[0]:
        return query_id[0]

    segments = [segment for segment in parsed.path.split("/") if segment]
    if "folders" in segments:
        index = segments.index("folders")
        if index + 1 < len(segments):
            return segments[index + 1]
    return segments[-1] if segments else text


class GoogleDriveService:
    """Uploads and reads screenshot objects. One instance per process."""

    def __init__(self) -> None:
        self._service = None
        self._lock = threading.Lock()
        #: (parent_id, name) -> folder id.
        self._folder_cache: Dict[Tuple[str, str], str] = {}

    # ── Configuration ─────────────────────────────────────────────────────────

    @property
    def configured(self) -> bool:
        return settings.google_drive_configured

    @property
    def root_folder_id(self) -> str:
        """The configured root, as an id even when a URL was supplied."""
        return normalize_folder_id(settings.GOOGLE_DRIVE_ROOT_FOLDER_ID)

    def unconfigured_reason(self) -> Optional[str]:
        """Why storage cannot work, or None. Logged when an upload is refused.

        An upload that fails with a bare "not configured" tells an operator
        nothing about which of the two settings is missing, and the desktop's
        message cannot say more than that without leaking configuration to a
        client. So the detail goes to the server log instead.
        """
        if not settings.GOOGLE_DRIVE_ROOT_FOLDER_ID:
            return "GOOGLE_DRIVE_ROOT_FOLDER_ID is not set"
        if not (settings.GOOGLE_SERVICE_ACCOUNT_JSON or settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH):
            return (
                "neither GOOGLE_SERVICE_ACCOUNT_JSON nor "
                "GOOGLE_SERVICE_ACCOUNT_JSON_PATH is set"
            )
        return None

    def describe_configuration(self) -> dict:
        """Non-sensitive summary, safe to log or return in diagnostics."""
        return {
            "configured": self.configured,
            "root_folder_id": self.root_folder_id or None,
            "credential_source": (
                "inline" if settings.GOOGLE_SERVICE_ACCOUNT_JSON
                else "file" if settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH
                else None
            ),
        }

    @staticmethod
    def _key_file_path() -> str:
        """Resolve the key file relative to the backend, not to the CWD.

        `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` is naturally written relative
        (`./secrets/google-service-account.json`), and a relative path is
        resolved against whatever directory the server was launched from — the
        repository root, a systemd unit's WorkingDirectory, a serverless
        function's sandbox. The same configuration then works for one operator
        and fails for the next, reporting only "file not found".
        """
        raw = settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH
        if not raw:
            return raw
        path = Path(raw).expanduser()
        if path.is_absolute():
            return str(path)
        # <backend>/ — this file is app/services/google_drive_service.py.
        backend_root = Path(__file__).resolve().parents[2]
        candidate = (backend_root / path).resolve()
        if candidate.exists():
            return str(candidate)
        return str(path)

    def _credentials(self):
        from google.oauth2 import service_account  # type: ignore

        if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
            try:
                info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
            except json.JSONDecodeError as exc:
                # The message deliberately does not include the value.
                raise GoogleDriveError(
                    "GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON"
                ) from exc
            return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

        path = self._key_file_path()
        try:
            return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
        except FileNotFoundError as exc:
            raise GoogleDriveError(
                f"the service account key file was not found at {path}"
            ) from exc

    def _client(self):
        """The Drive client, built once and reused."""
        if self._service is not None:
            return self._service
        with self._lock:
            if self._service is not None:
                return self._service
            if not self.configured:
                raise GoogleDriveError(
                    "Google Drive is not configured: set GOOGLE_DRIVE_ROOT_FOLDER_ID "
                    "and one of GOOGLE_SERVICE_ACCOUNT_JSON / "
                    "GOOGLE_SERVICE_ACCOUNT_JSON_PATH"
                )
            try:
                from googleapiclient.discovery import build  # type: ignore
            except ImportError as exc:
                raise GoogleDriveError(
                    "google-api-python-client is not installed on this backend"
                ) from exc
            try:
                self._service = build(
                    "drive", "v3",
                    credentials=self._credentials(),
                    cache_discovery=False,
                )
            except GoogleDriveError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise GoogleDriveError(f"could not initialise the Drive client: {exc}") from exc
            return self._service

    # ── Folders ───────────────────────────────────────────────────────────────

    @staticmethod
    def _escape(name: str) -> str:
        """Escape a name for a Drive query literal."""
        return name.replace("\\", "\\\\").replace("'", "\\'")

    def _service_account_email(self) -> str:
        """The address the root folder has to be shared with. Log-only."""
        try:
            if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
                return json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON).get("client_email", "?")
            with open(self._key_file_path(), encoding="utf-8") as handle:
                return json.load(handle).get("client_email", "?")
        except Exception:  # noqa: BLE001
            return "?"

    def verify_root_access(self) -> None:
        """Confirm the configured root exists and is writable by this account.

        :raises GoogleDriveNotAccessible: with an actionable message naming the
            address the folder must be shared with. That message is for the
            server log and for an operator running this check by hand — it is
            never returned to a client.
        """
        root = self.root_folder_id
        try:
            self._client().files().get(
                fileId=root, fields="id, name, driveId", supportsAllDrives=True
            ).execute()
        except GoogleDriveError:
            raise
        except Exception as exc:  # noqa: BLE001
            if "notFound" in str(exc) or "File not found" in str(exc):
                raise GoogleDriveNotAccessible(
                    f"the configured root folder '{root}' is not visible to the "
                    f"service account {self._service_account_email()}. Share the "
                    f"folder (or add the account to the shared drive) with "
                    f"Editor/Content manager access, and check that "
                    f"GOOGLE_DRIVE_ROOT_FOLDER_ID names that folder"
                ) from exc
            raise GoogleDriveError(f"could not read the root folder: {exc}") from exc

    def _find_folder(self, parent_id: str, name: str) -> Optional[str]:
        """The oldest folder with this name under `parent_id`, or None.

        Oldest, not first: if a race once created duplicates, every process
        must agree on which one is canonical, and creation time is the only
        ordering both of them can see.
        """
        query = (
            f"name = '{self._escape(name)}' and mimeType = '{FOLDER_MIME}' "
            f"and '{parent_id}' in parents and trashed = false"
        )
        response = self._client().files().list(
            q=query,
            fields="files(id, name, createdTime)",
            orderBy="createdTime",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files = response.get("files", [])
        return files[0]["id"] if files else None

    def ensure_folder(self, parent_id: str, name: str) -> str:
        """Return the id of `name` under `parent_id`, creating it if missing."""
        key = (parent_id, name)
        cached = self._folder_cache.get(key)
        if cached:
            return cached

        existing = self._find_folder(parent_id, name)
        if existing:
            self._folder_cache[key] = existing
            return existing

        try:
            self._client().files().create(
                body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]},
                fields="id",
                supportsAllDrives=True,
            ).execute()
        except Exception as exc:  # noqa: BLE001
            # Drive reports an unreachable parent as a plain 404 on the parent
            # id, which reads like "the file you asked for is missing" and sends
            # an operator looking in the wrong place entirely. Translate it once,
            # here, into the thing that is actually wrong.
            if "notFound" in str(exc) or "File not found" in str(exc):
                raise GoogleDriveNotAccessible(
                    f"cannot create '{name}': the parent folder '{parent_id}' is "
                    f"not visible to the service account "
                    f"{self._service_account_email()}. Share it with "
                    f"Editor/Content manager access"
                ) from exc
            raise

        # Re-query rather than trusting the id just created: another process
        # may have created the same folder in the same instant, and both must
        # settle on the same one. See the module docstring.
        canonical = self._find_folder(parent_id, name)
        if not canonical:
            raise GoogleDriveError(f"could not create or locate the folder '{name}'")
        self._folder_cache[key] = canonical
        return canonical

    def ensure_screenshot_folder(self, user_id: int, captured_on: date) -> Tuple[str, str]:
        """
        Resolve (and create) `<root>/Year/Month/User_<id>/<date>`.

        A new year, month, user or date folder appears automatically the first
        time a screenshot needs it — there is nothing to provision by hand.

        :return: `(folder_id, logical_path)`. The logical path is stored on the
            row so a human can find the object in the Drive UI.
        """
        root = self.root_folder_id
        year = f"{captured_on.year:04d}"
        month = captured_on.strftime("%B")
        user = f"User_{user_id}"
        day = captured_on.isoformat()

        folder_id = root
        for segment in (year, month, user, day):
            folder_id = self.ensure_folder(folder_id, segment)
        return folder_id, f"{year}/{month}/{user}/{day}"

    # ── Objects ───────────────────────────────────────────────────────────────

    def upload_file(
        self,
        folder_id: str,
        file_name: str,
        content: bytes,
        mime_type: str = "image/webp",
    ) -> str:
        """Store `content` in `folder_id`. Returns the Drive file id."""
        try:
            from googleapiclient.http import MediaIoBaseUpload  # type: ignore
        except ImportError as exc:
            raise GoogleDriveError(
                "google-api-python-client is not installed on this backend"
            ) from exc

        media = MediaIoBaseUpload(
            io.BytesIO(content), mimetype=mime_type, resumable=False
        )
        created = self._client().files().create(
            body={"name": file_name, "parents": [folder_id]},
            media_body=media,
            fields="id",
            supportsAllDrives=True,
        ).execute()
        file_id = created.get("id")
        if not file_id:
            raise GoogleDriveError("Drive accepted the upload but returned no file id")
        return file_id

    def download_file(self, file_id: str) -> bytes:
        """Read an object back, for the authenticated view endpoint.

        The bytes are proxied through this backend rather than handed out as a
        Drive link, so viewing a screenshot stays subject to Monitra's own
        organization and role checks and the Drive folder never has to be made
        public.
        """
        request = self._client().files().get_media(fileId=file_id, supportsAllDrives=True)
        buffer = io.BytesIO()
        try:
            from googleapiclient.http import MediaIoBaseDownload  # type: ignore
        except ImportError as exc:
            raise GoogleDriveError(
                "google-api-python-client is not installed on this backend"
            ) from exc

        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()

    def delete_file(self, file_id: str) -> None:
        """Remove an object. Used to roll back a file whose row could not be
        written, so a failed upload does not leave an orphan in Drive."""
        try:
            self._client().files().delete(fileId=file_id, supportsAllDrives=True).execute()
        except Exception:  # noqa: BLE001
            logger.warning("could not delete orphaned Drive file %s", file_id, exc_info=True)


#: Process-wide instance. The folder cache is what makes sharing it worthwhile.
drive_service = GoogleDriveService()
