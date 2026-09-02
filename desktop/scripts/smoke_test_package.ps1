<#
.SYNOPSIS
    Verify that the packaged Monitra.exe actually starts and shuts down cleanly.

.DESCRIPTION
    Runs the real packaged executable -- not the source tree -- for a few
    seconds and asserts that it booted its full runtime and exited cleanly.

    This catches the entire class of failure that packaging *introduces* and
    that no test run from source can see: a Qt DLL stripped by the spec's
    binary filter that turned out to be needed, a lazily-imported module
    (pynput, tzdata) PyInstaller's static analysis did not follow, a resource
    path that resolved into the source tree, or a configuration that only
    exists on the developer's machine. Every one of those produces a build
    that compiles perfectly and dies on launch.

    It is a smoke test and says so: it proves the application starts, reaches
    a running runtime and shuts down without escalating. It does NOT prove
    login, tracking or sync work against a backend -- that is the end-to-end
    checklist in BUILD.md, which needs real credentials and a real desktop.

.PARAMETER Seconds
    How long to let the application run before asking it to quit.

.EXAMPLE
    .\scripts\smoke_test_package.ps1
#>
[CmdletBinding()]
param(
    [int]$Seconds = 12
)

$ErrorActionPreference = 'Stop'

$DesktopRoot = Split-Path -Parent $PSScriptRoot
Set-Location $DesktopRoot

$Exe = Join-Path $DesktopRoot 'dist\Monitra\Monitra.exe'
if (-not (Test-Path $Exe)) {
    throw "$Exe not found. Run .\scripts\build_windows.ps1 first."
}

# An isolated data directory, so the smoke test can never read or damage a
# real installation's database, sync queue or logs on the same machine.
$DataDir = if ($env:MONITRA_DATA_DIR) { $env:MONITRA_DATA_DIR }
           else { Join-Path ([System.IO.Path]::GetTempPath()) "monitra-smoke-$PID" }
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $DataDir
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

Write-Host "==> Smoke-testing $Exe" -ForegroundColor Cyan
Write-Host "    data dir: $DataDir"
Write-Host "    runtime : ${Seconds}s"

$env:MONITRA_DATA_DIR = $DataDir
$env:MONITRA_SELFTEST_SECONDS = $Seconds
$env:MONITRA_LOG_LEVEL = 'INFO'

# Generous relative to $Seconds: a hang is the failure being tested for, and
# the timeout has to be long enough that a slow runner is not mistaken for one.
$TimeoutSeconds = $Seconds + 60

$process = Start-Process -FilePath $Exe -PassThru
if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    $process.Kill($true)
    throw "Monitra.exe did not exit within ${TimeoutSeconds}s -- it hung on startup or shutdown."
}

$exitCode = $process.ExitCode
Write-Host "    exit code: $exitCode"

# ── Assertions ──────────────────────────────────────────────────────────────
$LogFile = Join-Path $DataDir 'logs\monitra.log'
if (-not (Test-Path $LogFile)) {
    throw "no log was written to $LogFile -- the application did not reach startup."
}
$Log = Get-Content $LogFile -Raw

if ($exitCode -ne 0) {
    Write-Host $Log
    throw "Monitra.exe exited with code $exitCode (expected 0)."
}

# Proves the runtime booted, not merely that a window appeared.
if ($Log -notmatch 'Monitra .* starting') {
    Write-Host $Log
    throw "the startup line is missing from the log -- the runtime did not initialise."
}

# The failure that packaging most often causes, and the one a "did it launch?"
# check misses entirely: an import that only fails inside the frozen build.
foreach ($pattern in @('ModuleNotFoundError', 'ImportError', 'DLL load failed',
                       'Failed to execute script', 'CRITICAL')) {
    if ($Log -match $pattern) {
        Write-Host $Log
        throw "the packaged application logged '$pattern'."
    }
}

# Shutdown must be deterministic. Escalating to terminate() is the specific
# regression the runtime rebuild removed and must never come back.
if ($Log -match 'terminate\(\)') {
    Write-Host $Log
    throw "shutdown escalated to terminate() -- a service did not stop deterministically."
}

# The database must be created in the data directory, not beside the .exe.
if (-not (Test-Path (Join-Path $DataDir 'cache.db'))) {
    throw "no cache.db in $DataDir -- local storage did not initialise there."
}
$StrayDb = Get-ChildItem (Join-Path $DesktopRoot 'dist\Monitra') -Filter '*.db' -Recurse -ErrorAction SilentlyContinue
if ($StrayDb) {
    throw "a database was written inside the installation directory: $($StrayDb.FullName)"
}

Write-Host ""
Write-Host "==> Smoke test passed" -ForegroundColor Green
Write-Host "    started, ran for ${Seconds}s, shut down cleanly, wrote its data to $DataDir"
