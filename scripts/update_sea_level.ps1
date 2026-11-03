# Update the sea-level records (UHSLC) from this PC and publish them.
#
# UHSLC drops connections from GitHub-hosted runners, so this runs here, from
# Windows Task Scheduler (scripts\install_sea_level_task.ps1). It calls
#
#   python -m enso.publish --source-type uhslc --status
#
# which pulls, downloads, rebuilds docs\, runs the tests, commits only the
# sea-level files and docs\, and pushes (retrying once after a conflict with
# the SST workflow). See README, "Updates".
#
# By hand:
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\update_sea_level.ps1
#   ... -Python C:\path\to\python.exe     # another interpreter
#   ... -NoPush                           # commit locally only
#
# Python: -Python, else the ENSO_PYTHON environment variable, else the repo's
# own .venv\Scripts\python.exe. Output is appended to logs\update-sea-level.log
# (git-ignored). The exit code is enso.publish's: 0 ok, 1 published but some
# downloads failed, 2 nothing published.

param(
    [string]$Python = $env:ENSO_PYTHON,
    [switch]$NoPush
)

$Repo = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $Repo '.venv\Scripts\python.exe' }
$LogDir = Join-Path $Repo 'logs'
$Log = Join-Path $LogDir 'update-sea-level.log'

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
# Keep the log small: start a new one past 1 MB, keeping one old copy.
if ((Test-Path $Log) -and ((Get-Item $Log).Length -gt 1MB)) {
    Move-Item -Force $Log "$Log.1"
}

$env:PYTHONUNBUFFERED = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Log([string]$msg) {
    $line = '{0}  {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $Log -Value $line -Encoding UTF8
    Write-Host $line
}

Log '=== sea-level update start ==='
if (-not (Test-Path $Python)) {
    Log "FAILED: Python not found at $Python (pass -Python, set ENSO_PYTHON, or create .venv)"
    Log '=== end (exit 2) ==='
    exit 2
}

Set-Location $Repo
$argv = @('-m', 'enso.publish', '--source-type', 'uhslc', '--status')
if ($NoPush) { $argv += '--no-push' }
Log ("> {0} {1}" -f $Python, ($argv -join ' '))
# Native stderr lines arrive as error records; log them as text all the same.
$ErrorActionPreference = 'Continue'
& $Python @argv 2>&1 | ForEach-Object { Log ('  ' + $_.ToString()) }
$code = $LASTEXITCODE

Log ("=== end (exit {0}) ===" -f $code)
exit $code
