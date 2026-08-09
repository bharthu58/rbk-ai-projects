@echo off
REM Alternative to register-task.ps1, using schtasks.exe instead of PowerShell.
REM Run from a normal (non-admin) Command Prompt on the Windows host.
REM /rl limited = runs with the current user's normal (non-admin) rights.

schtasks /create /tn "AI Workflow Gateway" ^
  /tr "wsl.exe -d Ubuntu -- /home/bharthu/repos/github/rbk-ai-projects/claude-code-projects/ai-workflow-gateway/runtime/venv/bin/python -m gateway.main --config /home/bharthu/repos/github/rbk-ai-projects/claude-code-projects/ai-workflow-gateway/runtime/config.yaml" ^
  /sc hourly /mo 1 /rl limited /f

echo.
echo Registered. Test it now with: schtasks /run /tn "AI Workflow Gateway"
echo Then check: \\wsl$\Ubuntu\home\bharthu\repos\github\rbk-ai-projects\claude-code-projects\ai-workflow-gateway\runtime\logs\gateway.log
