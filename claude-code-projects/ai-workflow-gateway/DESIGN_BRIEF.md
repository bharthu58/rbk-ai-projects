Project: AI Workflow Gateway

Objective
Build a lightweight, reliable Python application that serves as the infrastructure between Claude Cowork and the outside world.
Follow the KISS principle throughout. Optimize for simplicity, reliability, maintainability, and low operational overhead. This is intended to be long-lived infrastructure, not a one-off script.

Architecture

* Host: Local Windows machine, triggered by Windows Task Scheduler (not dependent on Claude Cowork's own scheduler or the Cowork app being open).
* Language: Python
* Canonical report format: Markdown
* Published format: PDF (initially)
* Notifications: Email + Telegram
* User feedback: Email replies only (Telegram is notification-only)
* Google Drive access: via the local Google Drive for Desktop sync folder, using plain filesystem I/O — no Google Drive API, no OAuth client, no Google Cloud project. Drive remains the canonical store; the local sync folder is this gateway's operating surface. Note the one real dependency this creates: Drive for Desktop must stay running and signed in, and there is sync latency (typically seconds) between a file appearing locally and it being durable in Drive — the gateway should tolerate this (e.g. brief retry/backoff before treating a file as missing) rather than assume instant consistency.

  > **Amendment (2026-08-07, career-agent):** for `career-agent`, `workspace_root` now points at an ordinary local NTFS folder (`E:\RBK_AUR_DSKTP_AI\Workspace`, WSL `/mnt/e/RBK_AUR_DSKTP_AI/Workspace`) rather than the Drive Stream sync folder. Writes there are immediately consistent — there is no propagation window, so Drive is no longer the *canonical store* for this project's authority/consistency. Google Drive for Desktop still mirrors this folder to the cloud continuously, so it remains the durability backstop (off-machine backup), just not the source of truth. The retry/backoff-before-missing behavior described above is harmless to keep but is no longer load-bearing here — on this path a missing file is missing, not "still propagating."
* Email transport: a single app password on the Gmail account, used for both SMTP (send) and IMAP (read replies). Do not use the Gmail API for either direction — it would require registering an OAuth client in a Google Cloud project, which this design deliberately avoids. Store the app password and the Telegram bot token in local configuration (e.g. an untracked `.env` or config file, gitignored, readable only by the gateway process) — not inside any Claude Cowork-managed Drive file, to keep credentials out of a synced/shared location.

Claude Cowork Project Structure
Every project follows this structure:

```text
<Project>/
    Inbox/
    Reports/
    State/
    Archive/
    project.yaml (optional)
```

Claude Cowork writes canonical Markdown reports into `Reports/`.
Markdown is the system of record.

Ownership boundaries (read this before designing responsibilities)
Claude Cowork already owns, per its own operating contract: producing canonical Markdown reports in `Reports/`, organizing/reorganizing project artifacts, and retention — some scheduled tasks (e.g. the career-search daily brief) already move their own reports older than 7 days into `Reports/archive` on their own schedule. The gateway must not duplicate or race against this. Concretely:

* The gateway treats `Reports/` as **read-only** for source Markdown. It never moves, renames, reorganizes, or deletes anything under `Reports/` that Claude wrote, including archiving.
* The gateway writes its own outputs (PDFs, and later HTML) to a gateway-owned subfolder it fully controls, e.g. `Reports/published/`. Nothing else should write there.
* The gateway writes reply-derived Markdown only into `Inbox/`, never into `Reports/` or `State/State.md`.
* The gateway maintains its own state (see below) separate from `State/State.md`, which is Claude's file.

Gateway Responsibilities
The gateway shall:

1. Monitor project folders (via the local Drive-for-Desktop sync path) for newly generated Markdown reports in each project's `Reports/`.
2. Generate a PDF version of each new report and write it to that project's `Reports/published/` (never modify or move the source Markdown or anything else in `Reports/`).
3. Send:
   * an email containing a brief summary and links to (or attachments of) the Markdown and PDF reports.
   * a concise Telegram notification indicating a new report is available.
4. Process email replies (via IMAP, same app-password account) and convert them into Markdown files placed in the correct project's `Inbox/`. Since one mailbox serves multiple projects, every outbound notification email must embed a project identifier in the subject line (e.g. `[career-agent] New brief: 2026-08-06`), and the reply processor must parse that tag from the subject (handling the "Re:" prefix) to route the resulting Inbox/ file to the right project. If no project tag can be resolved, log it and leave the message unprocessed rather than guessing.
5. Maintain clean logging, error handling, and configuration.
6. Support multiple independent projects using a common configuration, where each project is a folder under the Workspace root containing its own `project.yaml`.

State & idempotency (make this explicit in the design, not implicit in code)
* Per project, maintain a gateway-owned state file (e.g. `State/gateway-state.json` — a distinct filename from Claude's `State/State.md`, or store it outside the Drive-synced tree entirely if you'd rather keep gateway state off Drive) tracking: which reports have been published (PDF generated + notified), and the last IMAP UID/timestamp processed for replies.
* Design explicitly for catch-up: if the Windows machine was off or the task didn't run for a period, the next run must process every unpublished report and every unread reply since the last successful run — not just the newest one. This mirrors how Claude Cowork's own scheduled tasks behave (they catch up on next launch rather than skipping missed runs), so the whole system has one consistent mental model.
* Pin a minimal schema for reply-derived Inbox/ files now, e.g. filename `YYYY-MM-DD-email-reply.md` with a short header (project, date, original subject) followed by the reply body, so Claude can parse these reliably on its next run.

project.yaml coordination
Existing projects (e.g. career-agent) have a `project.yaml` written under the assumption that no gateway exists yet — fields like `delivery_mode: fallback` and `email_send: unavailable`. The gateway should read a project's `project.yaml` and only act on a project once it's marked as opted in (define a field for this, e.g. `gateway_enabled: true`); until then, skip it. This is a manual, explicit opt-in step per project — do not have the gateway silently activate itself for every folder it finds under the Workspace root. Document in the design how a project's `project.yaml` fields are expected to change once the gateway is live for it (e.g. `delivery_mode: fallback` → `live`, `email_send: unavailable` → `available`), even though flipping those fields is Claude's/the user's job, not the gateway's.

Constraints
The gateway is infrastructure only. It must not perform AI reasoning or modify Claude Cowork's workflow.

Deliverables
Before writing code, produce:

1. Overall architecture.
2. Directory structure (including where gateway state and config live, both locally and — if any — within the Drive-synced tree).
3. Configuration model (per-project opt-in, project discovery, credential storage, multi-project reply-routing scheme).
4. Component diagram.
5. End-to-end workflow (including the catch-up/idempotency behavior above).
6. Phased implementation plan.

Once the design is approved, implement the solution incrementally in small, testable phases.

Throughout the project:

* Prefer configuration over hardcoding.
* Keep components loosely coupled.
* Minimize dependencies.
* Produce clean, well-documented, production-quality code.
* Justify any added complexity against the KISS principle.