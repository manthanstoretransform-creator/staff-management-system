"""
Handing a verified artifact to the platform's installer, safely.

The problem this solves
-----------------------
A running process holds its own executable and libraries open. On Windows the
Inno Setup installer refuses to run at all while Monitra's named mutex is held
(``packaging/windows/monitra.iss``), and on macOS replacing a mounted bundle
underneath itself is undefined. So the update cannot be applied by the process
being updated — something has to outlive it.

That something is a small helper script, written to the update scratch
directory and launched **detached**. Its whole job is:

    wait for this process to exit  →  run the installer  →  relaunch Monitra

Because the helper only starts installing once Monitra has genuinely exited,
the ordinary shutdown path runs first, unchanged: services stop in reverse
order, the sync queue and the timer's state are already durable in SQLite, the
WAL is checkpointed and the database is closed. Nothing about the update needs
special handling for the timer, the cache, screenshots or activity capture,
because none of it is being interrupted differently from a normal quit — and
``~/.monitra`` is outside the installation directory, so the installer cannot
touch it either way.

Failure leaves a working application
------------------------------------
Every path here is written so that the worst outcome is "the update did not
happen". On Windows, Inno Setup either completes or rolls back its own
transaction, and the helper relaunches whatever is installed afterwards
regardless. On macOS the existing bundle is moved aside rather than deleted,
and is moved back if the copy fails — so a failed copy ends with the previous
version in place and running, never with an empty ``/Applications``.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from core.logging_setup import get_logger
from core.paths import app_dir, is_frozen, is_portable

from .downloader import updates_dir

log = get_logger("updates.install")

#: How long the helper waits for Monitra to exit before giving up, in seconds.
#: Shutdown is bounded by the runtime's own timeouts and completes in well
#: under a second in practice; this is the ceiling that stops a helper waiting
#: forever on a process that will not die, which would leave the installer
#: never running and no explanation anywhere.
EXIT_WAIT_SECONDS = 120


class InstallError(Exception):
    """The handoff could not be started. The application is untouched."""

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


def can_install() -> Optional[str]:
    """Why an in-place install is not possible here, or None if it is.

    Three honest refusals, each of which would otherwise become a confusing
    failure halfway through an update:

    * **Running from source.** There is no installed application to replace.
    * **A portable build.** It is a folder the user unzipped wherever they
      chose; there is no installer, and silently rewriting an arbitrary
      directory is not something to do on the user's behalf.
    * **An unsupported platform.** Linux has no packaged artifact in this
      project, so there is nothing to hand off to.
    """
    if not is_frozen():
        return (
            "Automatic updates are only available in an installed build of "
            "Monitra."
        )
    if is_portable():
        return (
            "This is the portable build of Monitra. Download the new portable "
            "package and replace this folder to update."
        )
    if sys.platform not in ("win32", "darwin"):
        return "Automatic updates are not available on this platform."
    return None


def launch_installer(artifact: Path, version: str) -> None:
    """Start the detached helper that will install `artifact` and relaunch.

    Returns as soon as the helper is running. The caller's next act must be an
    ordinary application quit: the helper is already waiting for this process
    to disappear.

    :raises InstallError: if the helper could not be started, in which case
        nothing has changed and the current installation is still running.
    """
    blocked = can_install()
    if blocked:
        raise InstallError(blocked, detail="install path unavailable")
    if not artifact.is_file():
        raise InstallError(
            "The downloaded update could not be found.",
            detail=f"missing artifact {artifact}",
        )

    if sys.platform == "win32":
        script = _write_windows_helper(artifact, version)
        command = ["cmd.exe", "/c", str(script)]
        # DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP: the helper must not die
        # with us, and must not inherit our console or be reached by a Ctrl+C
        # delivered to this process group as it exits.
        creationflags = 0x00000008 | 0x00000200
        kwargs = {"creationflags": creationflags}
    else:
        script = _write_macos_helper(artifact, version)
        command = ["/bin/bash", str(script)]
        # A new session, so the helper is not in this process's process group
        # and survives it.
        kwargs = {"start_new_session": True}

    try:
        subprocess.Popen(  # noqa: S603 - a script this module just wrote
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(updates_dir()),
            **kwargs,
        )
    except OSError as exc:
        raise InstallError(
            "The update could not be started. Your current version of "
            "Monitra is unaffected.",
            detail=str(exc),
        )

    log.info("installer helper launched for version %s (pid %s)", version, os.getpid())


def _relaunch_target() -> Path:
    """What the helper should start once the installer has finished.

    Resolved from the *running* executable rather than hardcoded, so a build
    installed somewhere unusual still relaunches itself. On macOS the bundle is
    the thing to open, not the binary inside it — opening the inner binary
    directly gives a process with no application identity, which loses the
    tray icon and the TCC permission grants.
    """
    executable = Path(sys.executable).resolve()
    if sys.platform == "darwin":
        for parent in executable.parents:
            if parent.suffix == ".app":
                return parent
    return executable


def _write_windows_helper(artifact: Path, version: str) -> Path:
    """Write the batch file that installs on Windows and relaunches.

    A ``.cmd`` rather than PowerShell on purpose: PowerShell script execution
    is routinely restricted by group policy on managed machines, and an updater
    that works only where the execution policy allows it is an updater that
    fails exactly where IT control is tightest.
    """
    target = _relaunch_target()
    script = updates_dir() / f"apply-update-{version}.cmd"
    # /SILENT (not /VERYSILENT) still shows a progress window, which is the
    # right call: the user asked for this and a visible progress bar is what
    # distinguishes "updating" from "the app vanished". /SP- skips the "this
    # will install..." prompt, /NORESTART stops the installer rebooting the
    # machine, and /CLOSEAPPLICATIONS lets it deal with any straggler holding
    # a file open rather than failing the install.
    script.write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        f"set PID={os.getpid()}\r\n"
        f"set TRIES={EXIT_WAIT_SECONDS}\r\n"
        ":waitloop\r\n"
        'tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul\r\n'
        "if errorlevel 1 goto ready\r\n"
        "set /a TRIES-=1\r\n"
        "if %TRIES% LEQ 0 goto ready\r\n"
        # ping as a sleep: `timeout` needs a console this detached process has
        # deliberately not been given.
        "ping -n 2 127.0.0.1 >nul\r\n"
        "goto waitloop\r\n"
        ":ready\r\n"
        f'start "" /wait "{artifact}" /SILENT /SP- /NORESTART /CLOSEAPPLICATIONS\r\n'
        # Relaunch whatever is installed, whether or not the installer
        # succeeded. Inno rolls its own transaction back on failure, so this
        # starts the previous version rather than nothing at all -- which is
        # the difference between a failed update and a lost application.
        f'start "" "{target}"\r\n'
        # Delete the artifact and then this script. A running .cmd may delete
        # itself; the interpreter has already buffered the line.
        f'del /q "{artifact}" >nul 2>&1\r\n'
        'del /q "%~f0" >nul 2>&1\r\n',
        encoding="ascii",
    )
    return script


def _write_macos_helper(artifact: Path, version: str) -> Path:
    """Write the shell script that installs on macOS and relaunches.

    The DMG is mounted with ``-nobrowse`` so no Finder window appears, the new
    bundle is copied into place beside the old one, and the old one is only
    discarded once the copy has succeeded. If anything fails, the old bundle is
    put back — the user ends up on the version they started on, running.
    """
    bundle = _relaunch_target()
    script = updates_dir() / f"apply-update-{version}.sh"
    script.write_text(
        f"""#!/bin/bash
# Monitra update helper for {version}. Written by the running application and
# deleted by itself at the end; safe to remove at any time.
set -u

PID={os.getpid()}
DMG={_sh_quote(str(artifact))}
BUNDLE={_sh_quote(str(bundle))}
BACKUP="$BUNDLE.previous"
TRIES={EXIT_WAIT_SECONDS}

# Wait for Monitra to exit. A mounted bundle must not be replaced underneath a
# running process.
while kill -0 "$PID" 2>/dev/null && [ "$TRIES" -gt 0 ]; do
  sleep 1
  TRIES=$((TRIES - 1))
done

MOUNT=$(mktemp -d /tmp/monitra-update.XXXXXX)
cleanup() {{
  hdiutil detach "$MOUNT" -quiet 2>/dev/null || true
  rmdir "$MOUNT" 2>/dev/null || true
  rm -f "$DMG"
  rm -f "$0"
}}

if ! hdiutil attach -nobrowse -quiet -mountpoint "$MOUNT" "$DMG"; then
  # Nothing has been touched; the installed application is exactly as it was.
  open "$BUNDLE" 2>/dev/null || true
  cleanup
  exit 1
fi

NEW="$MOUNT/Monitra.app"
if [ ! -d "$NEW" ]; then
  open "$BUNDLE" 2>/dev/null || true
  cleanup
  exit 1
fi

# Move the old bundle aside rather than deleting it, so there is something to
# put back. This is the step that guarantees a failed update still leaves a
# working application.
rm -rf "$BACKUP"
if [ -d "$BUNDLE" ] && ! mv "$BUNDLE" "$BACKUP"; then
  open "$BUNDLE" 2>/dev/null || true
  cleanup
  exit 1
fi

if cp -R "$NEW" "$BUNDLE"; then
  rm -rf "$BACKUP"
else
  # Put the previous version back and start it. The user keeps a working
  # Monitra; only the update failed.
  rm -rf "$BUNDLE"
  mv "$BACKUP" "$BUNDLE" 2>/dev/null || true
fi

open "$BUNDLE" 2>/dev/null || true
cleanup
exit 0
""",
        encoding="utf-8",
    )
    script.chmod(0o700)
    return script


def _sh_quote(value: str) -> str:
    """Single-quote a value for the shell, escaping embedded quotes.

    Paths here come from `sys.executable` and from a filename this application
    chose, so neither is attacker-controlled — but quoting a path that goes
    into a generated script is not a place to rely on that staying true.
    """
    return "'" + value.replace("'", "'\\''") + "'"
