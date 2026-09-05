# Registers the AI Workflow Gateway as a Windows Task Scheduler job.
# Run this from a normal (non-admin) PowerShell prompt on the Windows host.
#
# Per DESIGN.md: the task shells into WSL to run the gateway in place — no
# second Windows-native checkout, no code duplication. Runs only when logged
# on (the conservative default — see DESIGN.md's "to verify" list) every 12
# hours (twice daily), and catches up automatically if the machine was off or
# asleep, since the gateway's own state file (not Task Scheduler) tracks
# progress.

$TaskName    = "AI Workflow Gateway"
$WslDistro   = "Ubuntu"
$VenvPython  = "/home/bharthu/repos/github/rbk-ai-projects/claude-code-projects/ai-workflow-gateway/runtime/venv/bin/python"
$ConfigPath  = "/home/bharthu/repos/github/rbk-ai-projects/claude-code-projects/ai-workflow-gateway/runtime/config.yaml"

$Action = New-ScheduledTaskAction -Execute "wsl.exe" `
    -Argument "-d $WslDistro -- $VenvPython -m gateway.main --config $ConfigPath"

# NOTE: do not pass -RepetitionDuration ([TimeSpan]::MaxValue) here — it serializes to
# an out-of-range ISO 8601 duration ("P99999999DT23H59M59S") that Register-ScheduledTask
# rejects with "The task XML contains a value which is incorrectly formatted or out of
# range." Omitting -RepetitionDuration entirely on a -Once trigger with -RepetitionInterval
# set is the documented way to get indefinite repetition.
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Hours 12)

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
        -Description "Publishes Claude Cowork reports to PDF and sends email/Telegram notifications. See DESIGN.md." `
        -Force -ErrorAction Stop | Out-Null
} catch {
    Write-Error "Failed to register '$TaskName': $_"
    exit 1
}

Write-Host "Registered '$TaskName'. Verify with: Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "Test it now with: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Then check: \\wsl`$\$WslDistro\home\bharthu\repos\github\rbk-ai-projects\claude-code-projects\ai-workflow-gateway\runtime\logs\gateway.log"
