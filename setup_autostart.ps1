
$TaskName = "GoldAlgoBot"
$ScriptPath = "$PSScriptRoot\run_bot.bat"

Write-Host "Setting up $TaskName to run at startup..."

# 1. Create Action
$Action = New-ScheduledTaskAction -Execute $ScriptPath

# 2. Create Trigger (At System Startup)
$Trigger = New-ScheduledTaskTrigger -AtStartup

# 3. Create Settings (Continuous run, don't stop)
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Days 3650) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

# 4. Principal (Run as SYSTEM to allow logged-off execution)
# Note: running as SYSTEM means it runs in background session 0.
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# 5. Register
try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force
    Write-Host "SUCCESS: Task '$TaskName' registered."
    Write-Host "It will start automatically on next reboot."
    Write-Host "To start immediately, run: Start-ScheduledTask -TaskName '$TaskName'"
} catch {
    Write-Error "FAILED to register task. Ensure you are running PowerShell as Administrator."
    Write-Error $_
}
