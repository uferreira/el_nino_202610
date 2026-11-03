# Install (or remove) the Windows scheduled task that runs
# scripts\update_sea_level.ps1 every 5 days. Run it once, as yourself, in a
# normal (not elevated) PowerShell:
#
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\install_sea_level_task.ps1
#   ... -At 08:00                          # start time (default 07:30, local time)
#   ... -Python C:\path\to\python.exe      # fixed interpreter (default: see update_sea_level.ps1)
#   ... -WakeToRun                         # wake the PC from sleep to run it
#   ... -Remove                            # uninstall
#
# Settings:
# * every 5 days at -At, counted from today;
# * "Run task as soon as possible after a scheduled start is missed", so a
#   PC that was off or asleep catches up when it is next on;
# * only when a network connection is available; at most 1 hour; a run that
#   is still going is not started twice;
# * runs as the current user, only while that user is logged on, because git
#   push uses that user's stored credentials (Git Credential Manager).

param(
    [string]$At = '07:30',
    [string]$Python = '',
    [string]$TaskName = 'el_nino_202610 sea level update',
    [switch]$WakeToRun,
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed task '$TaskName'."
    exit 0
}

$Script = Join-Path $PSScriptRoot 'update_sea_level.ps1'
$Repo = Split-Path -Parent $PSScriptRoot
$arg = "-NoProfile -ExecutionPolicy Bypass -File `"$Script`""
if ($Python) { $arg += " -Python `"$Python`"" }

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg -WorkingDirectory $Repo
$trigger = New-ScheduledTaskTrigger -Daily -DaysInterval 5 -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun:$WakeToRun
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force `
    -Description 'Downloads UHSLC sea level, rebuilds docs, commits and pushes (el_nino_202610).' | Out-Null

$info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Host "Installed task '$TaskName' for $user."
Write-Host "Next run: $($info.NextRunTime). Log: $(Join-Path $Repo 'logs\update-sea-level.log')"
Write-Host "Run it now with: Start-ScheduledTask -TaskName '$TaskName'"
