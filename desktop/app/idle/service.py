"""
Backend calls for the idle-time module.

One method per endpoint, in the same shape as the other services in `app/`:
they translate HTTP outcomes into `ApiError` with the backend's own
explanation attached, and they never decide anything. The backend is
authoritative for whether idle time is counted, how long an idle period
actually was, and where reassigned time lands — this layer only carries the
request and hands the answer back.

Paths are the bare ones (`/idle-periods`, not `/api/v1/idle-periods`),
matching `TimeEntryService`. The backend registers the router under both.
"""
from typing import Any, Dict, Optional

from app.api.client import ApiClient, TIMEOUT_FAST
from app.api.exceptions import (
    ApiConnectionError, ApiError, ApiHttpError, error_detail,
)
from core.logging_setup import get_logger

log = get_logger("idle.api")


def _explain(action: str, exc: ApiHttpError) -> ApiError:
    """Turn an HTTP failure into a sentence the user can act on.

    The backend already explains its refusals ("Idle period has already been
    resolved.", "Only a pending idle period can be reassigned."). Replacing
    that with a bare status code is what made a previous generation of these
    services impossible to debug from a screenshot.
    """
    detail = error_detail(exc.response_body)
    log.warning(
        "%s failed: HTTP %s%s", action, exc.status_code,
        f" -- {exc.response_body}" if exc.response_body else "",
    )
    if exc.status_code == 401:
        return ApiError("Session expired. Please log in again.", status_code=401)
    if detail:
        return ApiError(detail, status_code=exc.status_code)
    return ApiError(
        f"{action} failed (HTTP {exc.status_code}).", status_code=exc.status_code
    )


class IdleApiService:
    """Client for the backend's idle-period endpoints."""

    def __init__(self, api_client: ApiClient) -> None:
        self.api_client = api_client

    # ── Configuration ─────────────────────────────────────────────────────────

    def get_config(self) -> Dict[str, Any]:
        """The signed-in user's idle configuration.

        `{"idle_enabled": bool, "idle_minutes": int}`. The same two fields
        ride along on `GET /auth/me`, which is where the desktop seeds them
        from at login; this endpoint exists so the detector can refresh them
        without re-fetching the whole profile.
        """
        try:
            response = self.api_client.get("/idle-periods/config", timeout=TIMEOUT_FAST)
            return response.json()
        except ApiHttpError as exc:
            raise _explain("Loading the idle configuration", exc)
        except ApiConnectionError:
            raise ApiError("Could not load the idle configuration: network error.")
        except Exception as exc:  # noqa: BLE001
            raise ApiError(f"Could not load the idle configuration: {exc}")

    # ── Reporting ─────────────────────────────────────────────────────────────

    def report_idle_period(
        self,
        time_entry_id: int,
        idle_started_at: str,
        idle_detected_at: str,
        client_event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Report that the configured idle threshold has been reached.

        `idle_started_at` is the last observed input, `idle_detected_at` the
        moment the threshold was crossed — never the end of the idle period,
        which is only known once the user answers the popup.

        `client_event_id` makes the call idempotent: a retry, or a second
        report while one is still pending, returns the existing period rather
        than opening another.
        """
        payload = {
            "time_entry_id": time_entry_id,
            "idle_started_at": idle_started_at,
            "idle_detected_at": idle_detected_at,
        }
        if client_event_id:
            payload["client_event_id"] = client_event_id
        try:
            response = self.api_client.post("/idle-periods", json_data=payload)
            return response.json()
        except ApiHttpError as exc:
            raise _explain("Reporting idle time", exc)
        except ApiConnectionError:
            raise ApiError("Could not report idle time: network error.")
        except Exception as exc:  # noqa: BLE001
            raise ApiError(f"Could not report idle time: {exc}")

    def get_pending_idle_period(self, time_entry_id: int) -> Optional[Dict[str, Any]]:
        """The unresolved idle period for a time entry, or None.

        This is what makes recovery correct after a crash or a restart: a
        pending period lives on the server, so local state is never the only
        record of one. Returns None rather than raising when the backend has
        nothing pending.
        """
        try:
            response = self.api_client.get(
                "/idle-periods/active",
                params={"time_entry_id": time_entry_id},
                timeout=TIMEOUT_FAST,
            )
            data = response.json()
            return data if isinstance(data, dict) and data.get("id") else None
        except ApiHttpError as exc:
            if exc.status_code == 404:
                return None
            raise _explain("Checking for a pending idle period", exc)
        except ApiConnectionError:
            raise ApiError("Could not check for a pending idle period: network error.")
        except Exception as exc:  # noqa: BLE001
            raise ApiError(f"Could not check for a pending idle period: {exc}")

    # ── Resolution ────────────────────────────────────────────────────────────

    def resolve_idle_period(
        self,
        idle_period_id: int,
        keep_idle_time: bool,
        action: str,
        resolved_at: str,
    ) -> Dict[str, Any]:
        """Resolve a pending idle period with the user's answer.

        `action` is "stop" or "resume". The server decides whether the idle
        time counts — only keep + resume does — and, for "stop", stops the
        time entry through its own stop path. Repeating the same answer is
        idempotent there; a different answer after resolution is a 409.
        """
        payload = {
            "keep_idle_time": bool(keep_idle_time),
            "action": action,
            "resolved_at": resolved_at,
        }
        try:
            response = self.api_client.post(
                f"/idle-periods/{idle_period_id}/resolve", json_data=payload
            )
            return response.json()
        except ApiHttpError as exc:
            raise _explain("Resolving the idle period", exc)
        except ApiConnectionError:
            raise ApiError("Could not resolve the idle period: network error.")
        except Exception as exc:  # noqa: BLE001
            raise ApiError(f"Could not resolve the idle period: {exc}")

    def reassign_idle_period(
        self, idle_period_id: int, project_id: int, task_id: int
    ) -> Dict[str, Any]:
        """Attribute this idle period's elapsed time to another project/task.

        The backend validates the project and the task (including that the
        task belongs to the chosen project) against what this user is
        authorised for, writes the destination entry and the offsetting
        deduction in one transaction, and leaves the idle period **pending** —
        the user must still answer the main popup.
        """
        payload = {"project_id": project_id, "task_id": task_id}
        try:
            response = self.api_client.post(
                f"/idle-periods/{idle_period_id}/reassign", json_data=payload
            )
            return response.json()
        except ApiHttpError as exc:
            raise _explain("Reassigning the idle time", exc)
        except ApiConnectionError:
            raise ApiError("Could not reassign the idle time: network error.")
        except Exception as exc:  # noqa: BLE001
            raise ApiError(f"Could not reassign the idle time: {exc}")
