#!/usr/bin/env python
"""
check_architecture — Enforce Monitra's runtime ownership boundary.

The desktop application was destabilised by feature and UI code owning runtime
concerns: widgets creating and destroying QThreads, a dialog spawning
long-running workers, several modules running their own sync loops, and more
than one component counting elapsed seconds. Those are not stylistic problems;
each one produced a specific production failure documented in DO_NOT_DO.md.

This script makes the boundary mechanical. Run it in CI and from pre-commit:

    python tools/check_architecture.py

Exit status is non-zero if any rule is violated.
"""
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

DESKTOP_ROOT = Path(__file__).resolve().parent.parent

#: Packages permitted to manage threads and service lifetimes.
INFRASTRUCTURE_PACKAGES = ("core", "background_services", "storage")

#: Directories excluded from the scan.
# ".venv-build" is the packaging virtualenv (see .gitignore). It is
# third-party code, not ours, and PySide6's own QtAsyncio module legitimately
# creates QThreads -- scanning it reported violations that no change to this
# project could ever fix. The rules themselves are untouched.
EXCLUDED = {
    ".venv", ".venv-build", "venv", "__pycache__", "tests", "tools",
    "build", "dist",
}

#: Qt names that constitute owning a thread or a background loop.
FORBIDDEN_QT_NAMES = {
    "QThread": "create or subclass QThread",
    "QThreadPool": "manage a thread pool",
    "QRunnable": "define background runnables",
}

#: Modules deleted during the stability rebuild. Importing them means a merge
#: has resurrected a competing implementation.
REMOVED_MODULES = {
    "sync.sync_queue": "background_services.sync.SyncService",
    "sync.network_monitor": "background_services.network.NetworkService",
    "tracking.manager": "background_services.timer.TimerService",
    "tracking.app_usage_tracker": "background_services.activity.app_usage_service",
    "ui.notification_manager": "background_services.notifications.NotificationService",
    "ui.workers": "BackgroundApi.run_in_background",
    "app.timer.engine": "background_services.timer.TimerService",
    "app.timer": "background_services.timer.TimerService",
}


@dataclass
class Violation:
    path: Path
    line: int
    rule: str
    detail: str

    def __str__(self) -> str:
        rel = self.path.relative_to(DESKTOP_ROOT).as_posix()
        return f"{rel}:{self.line}: [{self.rule}] {self.detail}"


def module_name(path: Path) -> str:
    return path.relative_to(DESKTOP_ROOT).with_suffix("").as_posix().replace("/", ".")


def is_infrastructure(path: Path) -> bool:
    parts = path.relative_to(DESKTOP_ROOT).parts
    return bool(parts) and parts[0] in INFRASTRUCTURE_PACKAGES


def python_files() -> Iterable[Path]:
    for path in DESKTOP_ROOT.rglob("*.py"):
        if any(part in EXCLUDED for part in path.relative_to(DESKTOP_ROOT).parts):
            continue
        yield path


def imported_names(tree: ast.AST):
    """Yield (line, dotted_name) for every import in the module."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.lineno, node.module
            for alias in node.names:
                yield node.lineno, f"{node.module}.{alias.name}"


def check_file(path: Path) -> List[Violation]:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [Violation(path, exc.lineno or 0, "syntax", f"could not parse: {exc.msg}")]

    violations: List[Violation] = []
    infra = is_infrastructure(path)
    name = module_name(path)

    for line, imported in imported_names(tree):
        # Rule 1: removed modules must stay removed.
        for removed, replacement in REMOVED_MODULES.items():
            if imported == removed or imported.startswith(removed + "."):
                if name.startswith(removed):
                    continue
                violations.append(Violation(
                    path, line, "removed-module",
                    f"`{imported}` was removed during the stability rebuild; use {replacement}",
                ))

        # Rule 2: only infrastructure may import Qt threading primitives.
        if not infra and imported.startswith("PySide6.QtCore"):
            continue  # names checked below, not the module import itself

        # Rule 3: feature code must not import service implementations. It goes
        # through background_services.public_api.
        if (
            not infra
            and imported.startswith("background_services.")
            and not imported.startswith("background_services.public_api")
        ):
            violations.append(Violation(
                path, line, "service-internals",
                f"`{imported}` is a service internal; import from "
                f"background_services.public_api instead",
            ))

    if not infra:
        # Rule 4: no thread ownership outside the infrastructure layer.
        for node in ast.walk(tree):
            target = None
            if isinstance(node, ast.Name):
                target = node.id
            elif isinstance(node, ast.Attribute):
                target = node.attr
            if target in FORBIDDEN_QT_NAMES:
                violations.append(Violation(
                    path, getattr(node, "lineno", 0), "thread-ownership",
                    f"`{target}` — feature and UI modules must not "
                    f"{FORBIDDEN_QT_NAMES[target]}; use "
                    f"BackgroundApi.run_in_background()",
                ))

    return violations


def main() -> int:
    violations: List[Violation] = []
    scanned = 0
    for path in python_files():
        scanned += 1
        violations.extend(check_file(path))

    if violations:
        print(f"Architecture boundary violations ({len(violations)}):\n")
        for violation in sorted(violations, key=lambda v: (str(v.path), v.line)):
            print(f"  {violation}")
        print(
            "\nSee ARCHITECTURE.md for the ownership model and DO_NOT_DO.md for "
            "why each rule exists."
        )
        return 1

    print(f"Architecture boundaries OK ({scanned} files scanned).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
