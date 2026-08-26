"""
core — Monitra application runtime infrastructure.

This package owns process lifecycle, service ownership, worker threading and
structured logging. Nothing in `ui/` or `features` may manage QThreads,
background QTimers or service lifetimes directly; they go through the public
APIs exposed by `background_services.public_api`.

See ARCHITECTURE.md and DO_NOT_DO.md.
"""
