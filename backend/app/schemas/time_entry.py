from pydantic import BaseModel, ConfigDict, computed_field
from datetime import datetime

from app.core.time_format import elapsed_seconds as _elapsed_seconds, format_hms

class TimeEntryStart(BaseModel):
    project_id: int
    task_id: int
    description: str | None = None
    is_billable: bool | None = None
    #: The instant the user actually pressed Start, from the client.
    #:
    #: The desktop queues start/stop durably and retries them: a request can
    #: land minutes after the event when the machine was offline or the token
    #: had to be refreshed. Stamping the row with the server's `now()` at
    #: *request-processing* time therefore recorded the wrong instant and made
    #: the entry's duration disagree with the one the desktop had been showing
    #: the user. Omitted or implausible values fall back to the server clock;
    #: see TimeEntryService._event_time.
    started_at: datetime | None = None

class TimeEntryStop(BaseModel):
    description: str | None = None
    #: The instant the user actually pressed Stop. Same reasoning as
    #: `TimeEntryStart.started_at` -- and more important here, because a stop
    #: that lands late keeps the entry accruing time until it does.
    stopped_at: datetime | None = None

class TimeEntryRead(BaseModel):
    id: int
    organization_id: int
    user_id: int
    project_id: int
    task_id: int
    start_time: datetime
    end_time: datetime | None
    total_seconds: int
    status: str
    is_manual: bool
    is_billable: bool
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_running(self) -> bool:
        return self.end_time is None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def elapsed_seconds(self) -> int:
        """
        Exact elapsed seconds for this entry.

        `total_seconds` is only written when the timer stops, so a *running*
        entry reports 0 there. This measures a running entry against the
        current UTC instant instead, so callers do not have to wait for the
        timer to stop before they can show its duration.
        """
        if self.end_time is None:
            return _elapsed_seconds(self.start_time)
        return max(0, int(self.total_seconds))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def elapsed_time(self) -> str:
        """`elapsed_seconds` rendered as HH:MM:SS (never wraps past 24h)."""
        return format_hms(self.elapsed_seconds)
