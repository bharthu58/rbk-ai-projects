import logging

from gateway.config import GatewayConfig
from gateway.discovery import Project
from gateway.notifier import send_alert_email, send_telegram_alert
from gateway.runs_log import newest_line, parse_run_lines
from gateway.state import StateStore

logger = logging.getLogger(__name__)


def check_run_accountability(config: GatewayConfig, project: Project, state: StateStore) -> None:
    """Detection only, per the contract — the Orchestrator verifies declared artifacts
    exist and alerts on absence; diagnosing *why* belongs to the Project Worker."""
    runs_path = project.path / "State" / "runs.md"
    line = newest_line(parse_run_lines(runs_path))
    if line is None:
        return

    if state.last_checked_run_line(project.project_id) == line.raw:
        return  # already checked since this line was appended

    missing = [a for a in line.artifacts if not (project.path / a).is_file()]
    if not missing:
        state.mark_run_line_checked(project.project_id, line.raw)
        return

    _alert(config, project, line.raw, missing)
    state.mark_run_line_checked(project.project_id, line.raw)


def _alert(config: GatewayConfig, project: Project, line: str, missing: list[str]) -> None:
    body = (
        f"Run accountability check for '{project.project_id}' found declared artifact(s) missing on disk.\n\n"
        f"Run log line: {line}\n"
        f"Missing: {', '.join(missing)}\n\n"
        "This is a detection-only alert — the gateway does not diagnose the cause."
    )
    logger.warning("%s: missing declared artifact(s): %s (line: %s)", project.project_id, missing, line)

    if config.gmail_app_password and project.notify_email_to:
        send_alert_email(config, project, "Run accountability alert: missing artifact(s)", body)
    else:
        logger.error("%s: cannot email accountability alert (no credentials/notify.email_to configured)", project.project_id)

    if config.telegram_bot_token and config.telegram_chat_id:
        send_telegram_alert(config, project, f"run accountability alert — missing artifact(s): {', '.join(missing)}")
