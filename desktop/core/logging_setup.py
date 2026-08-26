"""
core.logging_setup — Structured runtime logging for Monitra.

Every record carries the fields the stability audit requires:
    timestamp, process id, thread name, thread id, logger/service name,
    session generation, and (where supplied) an operation id.

Session generation is a process-global counter that increments on every
login/logout. Stale asynchronous work compares its captured generation
against the current one and drops itself instead of mutating newer state
(see STEP 14 of the stability spec).

Usage:
    from core.logging_setup import configure_logging, get_logger, session_generation
    configure_logging()
    log = get_logger("sync")
    log.info("enqueued", extra={"op": operation_id})
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import threading
from pathlib import Path
from typing import Optional

# ── Session generation ────────────────────────────────────────────────────────

_generation_lock = threading.Lock()
_generation = 0


def session_generation() -> int:
    """Return the current session generation."""
    return _generation


def bump_session_generation() -> int:
    """
    Increment and return the session generation.

    Called on login and on logout. Any in-flight work captured an older
    generation and must discard its result rather than apply it.
    """
    global _generation
    with _generation_lock:
        _generation += 1
        return _generation


# ── Formatting ────────────────────────────────────────────────────────────────

class _RuntimeFormatter(logging.Formatter):
    """Formatter that injects runtime context into every record."""

    default_time_format = "%Y-%m-%d %H:%M:%S"
    default_msec_format = "%s.%03d"

    def format(self, record: logging.LogRecord) -> str:
        thread = threading.current_thread()
        record.pid = os.getpid()
        record.tname = thread.name
        record.tid = thread.ident
        record.gen = session_generation()
        if not hasattr(record, "op"):
            record.op = "-"
        return super().format(record)


_FORMAT = (
    "%(asctime)s pid=%(pid)d thread=%(tname)s/%(tid)s gen=%(gen)d "
    "op=%(op)s %(levelname)-7s %(name)-22s %(message)s"
)


def log_dir() -> Path:
    """Return the Monitra log directory, creating it if needed."""
    d = Path.home() / ".monitra" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


_configured = False


def configure_logging(level: Optional[int] = None, to_file: bool = True) -> None:
    """
    Configure root logging once per process.

    :param level: Log level; defaults to MONITRA_LOG_LEVEL env var or INFO.
    :param to_file: Also write a rotating log to ~/.monitra/logs/monitra.log.
    """
    global _configured
    if _configured:
        return

    if level is None:
        level = getattr(logging, os.getenv("MONITRA_LOG_LEVEL", "INFO").upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = _RuntimeFormatter(_FORMAT)

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    if to_file:
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                log_dir() / "monitra.log",
                maxBytes=4 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError:
            # Logging must never prevent the application from starting.
            pass

    # httpx logs every request at INFO; that is noise at our volume.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the `monitra` root."""
    return logging.getLogger(f"monitra.{name}")


def install_excepthook() -> None:
    """
    Route otherwise-unhandled exceptions to the log instead of losing them.

    The audit found exceptions being swallowed inside worker callbacks; this
    guarantees anything that escapes is recorded with a full traceback.
    """
    log = get_logger("excepthook")

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        log.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = _hook

    def _thread_hook(args):
        log.critical(
            "Unhandled exception in thread %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _thread_hook
