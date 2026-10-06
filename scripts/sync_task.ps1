<#
.SYNOPSIS
    Register (or remove) a Windows scheduled task that syncs CricIQ's data every 6 hours.

.DESCRIPTION
    The task runs `uv run criciq-data sync` in this repository every six hours while
    you are logged in, appending its output to data/sync/sync.log. Check the result
    with `just sync-status`. A sync that finds nothing new takes under a minute; one
    that brings new matches rebuilds, validates and scores them (about two minutes).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/sync_task.ps1
    powershell -ExecutionPolicy Bypass -File scripts/sync_task.ps1 -RunOnce
    powershell -ExecutionPolicy Bypass -File scripts/sync_task.ps1 -Remove
#>
param(
    [switch]$Remove,
    [switch]$RunOnce,
    [string]$TaskName = "CricIQ data sync",
    [int]$EveryHours = 6
)

$ErrorActionPreference = "Stop"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Output "Removed the scheduled task '$TaskName'."
    return
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
    $uv = Join-Path $env:APPDATA "Python\Python312\Scripts\uv.exe"
}
if (-not (Test-Path $uv)) {
    throw "uv not found; install it (py -3.12 -m pip install --user uv) and try again."
}
$log = Join-Path $repo "data\sync\sync.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null

$command = "Set-Location -LiteralPath '$repo'; " +
    "`$env:PYTHONIOENCODING = 'utf-8'; " +
    "Add-Content -LiteralPath '$log' -Encoding utf8 -Value ('==== ' + (Get-Date -Format s)); " +
    "& '$uv' run criciq-data sync *>&1 | Out-File -LiteralPath '$log' -Append -Encoding utf8"
if ($RunOnce) {
    # Run exactly what the task runs, once, now (to check it before scheduling).
    powershell.exe -NoProfile -NonInteractive -Command $command
    Get-Content -LiteralPath $log -Tail 8
    return
}
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -Command `"$command`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) `
    -RepetitionInterval (New-TimeSpan -Hours $EveryHours)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Brings CricIQ's cricket data up to date from Cricsheet (criciq-data sync)." `
    -Force | Out-Null
Write-Output "Registered '$TaskName': every $EveryHours hours from $((Get-Date).AddMinutes(5)), log in $log"
