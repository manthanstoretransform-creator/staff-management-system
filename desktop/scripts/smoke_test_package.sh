#!/usr/bin/env bash
#
# Verify that the packaged Monitra.app actually starts and shuts down cleanly.
#
# The macOS counterpart of scripts/smoke_test_package.ps1; see that script for
# what this class of test is for and what it deliberately does not prove.
#
# Note this runs the binary inside the bundle directly rather than via `open`,
# so the exit code is this script's to check. Launching through `open` returns
# as soon as the app is handed to launchd, which would make a crash look like
# a success.
#
# Usage (from desktop/):
#     ./scripts/smoke_test_package.sh [seconds]

set -euo pipefail

DESKTOP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DESKTOP_ROOT"

SECONDS_TO_RUN="${1:-12}"
APP="$DESKTOP_ROOT/dist/Monitra.app"
BINARY="$APP/Contents/MacOS/Monitra"

[[ -x "$BINARY" ]] || {
    echo "error: $BINARY not found. Run ./scripts/build_macos.sh first." >&2
    exit 1
}

# An isolated data directory: the smoke test must never touch a real
# installation's database, sync queue or logs on the same machine.
DATA_DIR="${MONITRA_DATA_DIR:-$(mktemp -d)/monitra-smoke}"
rm -rf "$DATA_DIR"
mkdir -p "$DATA_DIR"

echo "==> Smoke-testing $BINARY"
echo "    data dir: $DATA_DIR"
echo "    runtime : ${SECONDS_TO_RUN}s"

export MONITRA_DATA_DIR="$DATA_DIR"
export MONITRA_SELFTEST_SECONDS="$SECONDS_TO_RUN"
export MONITRA_LOG_LEVEL=INFO

TIMEOUT=$(( SECONDS_TO_RUN + 60 ))
EXIT_CODE=0

# No `timeout` on stock macOS, so the watchdog is done by hand: run the app in
# the background, poll for it, and kill it if it outlives the budget -- a hang
# is one of the failures being tested for.
"$BINARY" &
APP_PID=$!
WAITED=0
while kill -0 "$APP_PID" 2>/dev/null; do
    if (( WAITED >= TIMEOUT )); then
        kill -9 "$APP_PID" 2>/dev/null || true
        echo "error: Monitra did not exit within ${TIMEOUT}s -- it hung on startup or shutdown." >&2
        exit 1
    fi
    sleep 1
    WAITED=$(( WAITED + 1 ))
done
wait "$APP_PID" || EXIT_CODE=$?

echo "    exit code: $EXIT_CODE"

# ── Assertions ───────────────────────────────────────────────────────────────
LOG_FILE="$DATA_DIR/logs/monitra.log"
if [[ ! -f "$LOG_FILE" ]]; then
    echo "error: no log at $LOG_FILE -- the application did not reach startup." >&2
    exit 1
fi

if [[ $EXIT_CODE -ne 0 ]]; then
    cat "$LOG_FILE"
    echo "error: Monitra exited with code $EXIT_CODE (expected 0)." >&2
    exit 1
fi

if ! grep -qE 'Monitra .* starting' "$LOG_FILE"; then
    cat "$LOG_FILE"
    echo "error: the startup line is missing -- the runtime did not initialise." >&2
    exit 1
fi

for pattern in 'ModuleNotFoundError' 'ImportError' 'Library not loaded' \
               'Failed to execute script' 'CRITICAL' 'terminate()'; do
    if grep -qF "$pattern" "$LOG_FILE"; then
        cat "$LOG_FILE"
        echo "error: the packaged application logged '$pattern'." >&2
        exit 1
    fi
done

# The database must live in the data directory, never inside the .app bundle:
# a bundle is replaced wholesale on update and is read-only on a signed,
# Gatekeeper-validated install.
if [[ ! -f "$DATA_DIR/cache.db" ]]; then
    echo "error: no cache.db in $DATA_DIR -- local storage did not initialise there." >&2
    exit 1
fi
if find "$APP" -name '*.db' -print -quit | grep -q .; then
    echo "error: a database was written inside the application bundle." >&2
    exit 1
fi

# The bundle must carry the metadata macOS needs. A missing usage description
# means the corresponding permission is refused at runtime with no prompt the
# user could act on.
PLIST="$APP/Contents/Info.plist"
for key in CFBundleIdentifier CFBundleShortVersionString \
           NSScreenCaptureUsageDescription NSInputMonitoringUsageDescription; do
    /usr/libexec/PlistBuddy -c "Print :$key" "$PLIST" >/dev/null 2>&1 || {
        echo "error: Info.plist is missing $key." >&2
        exit 1
    }
done

echo
echo "==> Smoke test passed"
echo "    started, ran for ${SECONDS_TO_RUN}s, shut down cleanly, wrote its data to $DATA_DIR"
