from typing import Optional, Dict, Any
from app.api.client import ApiClient
from app.api.exceptions import ApiError, ApiHttpError, ApiConnectionError

class TimeEntryService:
    """Service layer coordinating communication with backend time entry endpoints."""

    def __init__(self, api_client: ApiClient) -> None:
        """
        Initialize TimeEntryService.
        
        :param api_client: Shared ApiClient instance.
        """
        self.api_client = api_client

    def start_time_entry(
        self, project_id: int, task_id: int, started_at: Optional[str] = None
    ) -> int:
        """
        Create a new time entry on the backend for the selected project and task.

        :param project_id: Project identifier.
        :param task_id: Task identifier.
        :param started_at: ISO-8601 UTC instant the user actually pressed
            Start. Sent so a queued or retried start records when the timer
            really began rather than when the request happened to reach the
            API -- the two differ by the whole time the action spent in the
            offline queue.
        :raises ApiError: On session expiry (401), active timer conflict (409), validation errors, or network drop.
        :return: Created time entry database ID.
        """
        payload = {
            "project_id": project_id,
            "task_id": task_id,
            "description": None,
            "is_billable": None
        }
        if started_at:
            payload["started_at"] = started_at
        try:
            response = self.api_client.post("/time-entries/start", json_data=payload)
            data = response.json()
            entry_id = data.get("id")
            if not entry_id:
                raise ApiError("Successfully communicated with backend, but response was missing time entry ID.")
            return entry_id
        except ApiHttpError as e:
            if e.status_code == 401:
                raise ApiError("Session expired. Please log in again.", status_code=401)
            if e.status_code == 409:
                raise ApiError("User already has an active timer.", status_code=409)
            if e.status_code == 422:
                raise ApiError("Validation error occurred during time entry start.", status_code=422)
            raise ApiError(f"Failed to start timer on backend: HTTP {e.status_code}.", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to start timer: Network connection error.")
        except Exception as e:
            raise ApiError(f"Failed to start timer: {str(e)}")

    def stop_time_entry(
        self,
        entry_id: int,
        timeout: Optional[float] = None,
        stopped_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Stop/finalize the specified active time entry on the backend.

        :param entry_id: Time entry database ID.
        :param timeout: Optional custom timeout in seconds.
        :param stopped_at: ISO-8601 UTC instant the user actually pressed
            Stop. This matters more than `started_at`: a stop that is retried
            for minutes used to leave the entry accruing until it landed, so
            the backend's duration exceeded the one the desktop had shown.
        :raises ApiError: On session expiry (401), timer not found (404), already stopped (409), or network drop.
        :return: Response dictionary of finalized time entry details.
        """
        payload = {
            "description": None
        }
        if stopped_at:
            payload["stopped_at"] = stopped_at
        try:
            response = self.api_client.post(f"/time-entries/{entry_id}/stop", json_data=payload, timeout=timeout)
            return response.json()
        except ApiHttpError as e:
            if e.status_code == 401:
                raise ApiError("Session expired. Please log in again.", status_code=401)
            if e.status_code == 404:
                raise ApiError("Active timer not found on backend.", status_code=404)
            if e.status_code == 409:
                raise ApiError("Timer is already stopped.", status_code=409)
            raise ApiError(f"Failed to stop timer on backend: HTTP {e.status_code}.", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to stop timer: Network connection error.")
        except Exception as e:
            raise ApiError(f"Failed to stop timer: {str(e)}")

    def record_app_usage(self, time_entry_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Record a single application usage event on the backend.
        """
        try:
            response = self.api_client.post(f"/time-entries/{time_entry_id}/app-usage", json_data=payload)
            return response.json()
        except ApiHttpError as e:
            raise ApiError(f"Failed to record app usage: HTTP {e.status_code}", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to record app usage: Network connection error")
        except Exception as e:
            raise ApiError(f"Failed to record app usage: {str(e)}")

    def batch_sync_app_usage(self, time_entry_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Batch upload application usage events.
        """
        try:
            response = self.api_client.post(f"/time-entries/{time_entry_id}/app-usage/batch", json_data=payload)
            return response.json()
        except ApiHttpError as e:
            raise ApiError(f"Failed to batch sync app usage: HTTP {e.status_code}", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to batch sync app usage: Network connection error")
        except Exception as e:
            raise ApiError(f"Failed to batch sync app usage: {str(e)}")

    def get_app_usage(self, time_entry_id: int) -> Dict[str, Any]:
        """
        Get detailed app usage logs.
        """
        try:
            response = self.api_client.get(f"/time-entries/{time_entry_id}/app-usage")
            return response.json()
        except ApiHttpError as e:
            raise ApiError(f"Failed to retrieve app usage: HTTP {e.status_code}", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to retrieve app usage: Network connection error")
        except Exception as e:
            raise ApiError(f"Failed to retrieve app usage: {str(e)}")

    def get_app_usage_summary(self, time_entry_id: int) -> Dict[str, Any]:
        """
        Get aggregated summary for a specific time entry.
        """
        try:
            response = self.api_client.get(f"/time-entries/{time_entry_id}/app-usage/summary")
            return response.json()
        except ApiHttpError as e:
            raise ApiError(f"Failed to retrieve app usage summary: HTTP {e.status_code}", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to retrieve app usage summary: Network connection error")
        except Exception as e:
            raise ApiError(f"Failed to retrieve app usage summary: {str(e)}")

    def create_manual_time_entry(
        self,
        project_id: int,
        task_id: int,
        work_date: str,
        total_seconds: int,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        description: Optional[str] = None,
        is_billable: bool = True,
    ) -> Dict[str, Any]:
        """
        Log a completed work session after the fact, distinct from the live
        Start/Stop timer above.

        Reuses the backend's existing manual-entry endpoint (the same bare
        path convention as /time-entries/start above) rather than a new one:
        it already validates the project/task, computes total_seconds from
        start_time/end_time when both are given, rejects overlap with an
        existing session, and defaults approval_status to 'pending' -- none
        of that is duplicated here.

        :param work_date: ISO date string (YYYY-MM-DD).
        :param start_time: ISO 8601 UTC datetime string, e.g. from
            datetime.isoformat(). Optional; if omitted (with end_time), the
            backend derives the slot from work_date + total_seconds instead.
        :param end_time: ISO 8601 UTC datetime string, paired with start_time.
        :raises ApiError: On session expiry (401), an overlapping time slot
            (409), validation errors (400/422), or network drop.
        :return: The created manual time entry (approval_status='pending').
        """
        payload = {
            "project_id": project_id,
            "task_id": task_id,
            "work_date": work_date,
            "total_seconds": total_seconds,
            "description": description,
            "is_billable": is_billable,
        }
        if start_time is not None and end_time is not None:
            payload["start_time"] = start_time
            payload["end_time"] = end_time
        try:
            response = self.api_client.post("/manual-time-entries", json_data=payload)
            return response.json()
        except ApiHttpError as e:
            if e.status_code == 401:
                raise ApiError("Session expired. Please log in again.", status_code=401)
            if e.status_code == 409:
                raise ApiError(
                    "This time slot overlaps an existing time entry.", status_code=409
                )
            if e.status_code in (400, 422):
                raise ApiError(f"Could not log this entry: {e.response_body}", status_code=e.status_code)
            raise ApiError(f"Failed to save manual time entry: HTTP {e.status_code}.", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to save manual time entry: Network connection error.")
        except Exception as e:
            raise ApiError(f"Failed to save manual time entry: {str(e)}")

    def batch_sync_url_usage(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Batch upload browser URL usage events.
        """
        try:
            response = self.api_client.post("/url-usage/batch", json_data=payload)
            return response.json()
        except ApiHttpError as e:
            raise ApiError(f"Failed to batch sync URL usage: HTTP {e.status_code}", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to batch sync URL usage: Network connection error")
        except Exception as e:
            raise ApiError(f"Failed to batch sync URL usage: {str(e)}")

    def batch_sync_activity(self, time_entry_id: Optional[int], payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Batch upload activity samples.

        The entry id comes first, as it does on every other per-entry upload
        here (record_unwanted_activity, record_adjustment) and as SyncService
        has always called it. With payload first, the caller's positional
        `upload(entry_id, batch)` put the samples dict into the URL path and
        the entry id into the body, so every batch was rejected with a 422
        and no activity ever reached the backend.
        """
        try:
            if time_entry_id:
                try:
                    response = self.api_client.post(f"/time-entries/{time_entry_id}/activity/batch", json_data=payload)
                    return response.json()
                except ApiHttpError as e:
                    if e.status_code != 404:
                        raise
            try:
                response = self.api_client.post("/api/v1/time-entry-activities/batch", json_data=payload)
            except ApiHttpError as e:
                if e.status_code == 404:
                    response = self.api_client.post("/time-entry-activities/batch", json_data=payload)
                else:
                    raise
            return response.json()
        except ApiHttpError as e:
            raise ApiError(f"Failed to batch sync activity: HTTP {e.status_code}", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to batch sync activity: Network connection error")
        except Exception as e:
            raise ApiError(f"Failed to batch sync activity: {str(e)}")

    def record_unwanted_activity(self, time_entry_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Record one unwanted-activity detection event.
        """
        try:
            response = self.api_client.post(
                f"/time-entries/{time_entry_id}/unwanted-activity", json_data=payload
            )
            return response.json()
        except ApiHttpError as e:
            raise ApiError(f"Failed to record unwanted activity: HTTP {e.status_code}", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to record unwanted activity: Network connection error")
        except Exception as e:
            raise ApiError(f"Failed to record unwanted activity: {str(e)}")

    def record_adjustment(self, time_entry_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Record a time deduction (auditable adjustment; the entry's own
        total_seconds is never modified).
        """
        try:
            response = self.api_client.post(
                f"/time-entries/{time_entry_id}/adjustments", json_data=payload
            )
            return response.json()
        except ApiHttpError as e:
            raise ApiError(f"Failed to record adjustment: HTTP {e.status_code}", status_code=e.status_code)
        except ApiConnectionError:
            raise ApiError("Failed to record adjustment: Network connection error")
        except Exception as e:
            raise ApiError(f"Failed to record adjustment: {str(e)}")

