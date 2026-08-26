"""
background_services — Monitra's owned background runtime.

Every long-running service lives here and is owned by the ApplicationRuntime's
ServiceManager. UI and feature modules must not import service internals; they
use `background_services.public_api`.

See ARCHITECTURE.md for the ownership model and DO_NOT_DO.md for the
anti-patterns this layer exists to prevent.
"""
