import time
from typing import Optional, Callable

class TimerState:
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"

class TimerEngine:
    """Core domain timer engine that maintains state, timing, and project/task associations."""

    def __init__(self, time_provider: Optional[Callable[[], float]] = None) -> None:
        """
        Initialize TimerEngine.
        
        :param time_provider: Custom monotonic time function provider, useful for deterministic unit testing.
        """
        self.time_provider = time_provider or time.monotonic
        self.state: str = TimerState.IDLE
        self.project_id: Optional[int] = None
        self.task_id: Optional[int] = None
        self._start_monotonic: Optional[float] = None
        self._stop_monotonic: Optional[float] = None
        self._elapsed_offset: float = 0.0

    def start(self, project_id: int, task_id: int) -> None:
        """
        Start the timer session for the given project and task.
        
        :param project_id: Target project identifier.
        :param task_id: Target task identifier.
        :raises ValueError: If parameters are invalid or if the timer is already running.
        """
        if self.state == TimerState.RUNNING:
            raise ValueError("Timer is already running.")
        if not project_id:
            raise ValueError("Please select a project.")
        if not task_id:
            raise ValueError("Please select a task.")

        self.project_id = project_id
        self.task_id = task_id
        self._start_monotonic = self.time_provider()
        self._stop_monotonic = None
        self._elapsed_offset = 0.0
        self.state = TimerState.RUNNING

    def elapsed(self) -> float:
        """
        Calculate current elapsed duration in seconds using monotonic clock comparisons.
        
        :return: Floating number of seconds.
        """
        if self.state == TimerState.IDLE:
            return 0.0
        if self.state == TimerState.RUNNING:
            if self._start_monotonic is None:
                return 0.0
            return (self.time_provider() - self._start_monotonic) + self._elapsed_offset
        if self.state == TimerState.STOPPED:
            if self._stop_monotonic is not None and self._start_monotonic is not None:
                return (self._stop_monotonic - self._start_monotonic) + self._elapsed_offset
            return self._elapsed_offset
        return 0.0

    def stop(self) -> float:
        """
        Stop the active timer session and preserve final elapsed time.
        
        :raises ValueError: If the timer is not currently running.
        :return: The final elapsed duration in seconds.
        """
        if self.state != TimerState.RUNNING:
            raise ValueError("Timer is not currently running.")
        
        self._stop_monotonic = self.time_provider()
        self.state = TimerState.STOPPED
        return self.elapsed()

    def reset(self) -> None:
        """Reset the timer engine to a clean IDLE state."""
        self.state = TimerState.IDLE
        self.project_id = None
        self.task_id = None
        self._start_monotonic = None
        self._stop_monotonic = None
        self._elapsed_offset = 0.0
