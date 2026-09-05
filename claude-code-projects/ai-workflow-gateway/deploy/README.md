# Registering the Windows Task Scheduler job

These scripts must be run **from the Windows side** (PowerShell or Command
Prompt on the actual Windows host) — they can't be run from inside WSL,
since Task Scheduler is a Windows service. Pick one:

- `register-task.ps1` (PowerShell, clearer to read/edit) — **note:** on this
  machine's default execution policy, running it directly fails with
  `PSSecurityException: UnauthorizedAccess`. Either use `register-task.bat`
  below, or unblock/allow the script first (e.g. `Unblock-File
  .\register-task.ps1`, or run once with
  `powershell -ExecutionPolicy Bypass -File .\register-task.ps1`).
- `register-task.bat` (schtasks.exe — **recommended on this machine**, confirmed
  working where the `.ps1` hit the execution-policy error above)

Both register a task named **AI Workflow Gateway** that runs every 12
hours (twice daily), only while you're logged on (see "Open items" below),
shelling into WSL to run the gateway in place.

## Steps

1. Open PowerShell (or Command Prompt) as your normal user — no admin rights needed.
2. `cd` to this `deploy/` folder via its `\\wsl$\Ubuntu\...` path, or copy the
   script content and run it directly.
3. Run `register-task.ps1` (or `register-task.bat`).
4. Trigger it once manually to confirm it works end-to-end:
   - PowerShell: `Start-ScheduledTask -TaskName "AI Workflow Gateway"`
   - schtasks: `schtasks /run /tn "AI Workflow Gateway"`
5. Check `runtime/logs/gateway.log` (via `\\wsl$\Ubuntu\home\bharthu\repos\github\rbk-ai-projects\claude-code-projects\ai-workflow-gateway\runtime\logs\gateway.log`) for a normal discovery/publish/notify/reply log, same as every manual run so far.
6. Open Task Scheduler's GUI (`taskschd.msc`) → find "AI Workflow Gateway" →
   check the "Last Run Result" column after a scheduled run happens on its
   own (next 12-hour mark) — this is how you confirm it's really running
   unattended, not just when manually triggered.

## Open items (DESIGN.md's "to verify" list)

Both scripts default to **"only when logged on"** deliberately — this is
the conservative default until these are confirmed on your actual machine:

1. **Exit code propagation**: does a non-zero exit from the gateway (e.g. a
   config error) show up as a failed run in Task Scheduler's history? Force
   one by temporarily renaming `runtime/config.yaml` and checking the
   "Last Run Result" column.
2. **Unattended autostart**: if you later want this to run even when not
   logged in, switch the task's logon type to "Run whether user is logged
   on or not" in the GUI and confirm the WSL distro actually starts under
   that mode — it's known to be flakier than the logged-on case on some
   WSL/Windows version combinations.

## Once confirmed reliably running on its own

Per DESIGN.md §3, flip in each live project's `project.yaml`:
- `delivery_mode: fallback` → `live`
- `email_send: unavailable` → `available`

These were deliberately left as `fallback`/`unavailable` for `career-agent`
even after its first manual run, specifically because the schedule wasn't
proven unattended yet.
