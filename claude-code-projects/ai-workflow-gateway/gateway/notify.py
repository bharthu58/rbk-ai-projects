import logging

from gateway.config import GatewayConfig
from gateway.discovery import Project
from gateway.notifier import send_report_email, send_telegram_notification
from gateway.state import StateStore

logger = logging.getLogger(__name__)


def notify_reports(config: GatewayConfig, project: Project, state: StateStore) -> None:
    reports_dir = project.path / "Reports"
    published_dir = reports_dir / "published"

    for filename in sorted(state.pending_notifications(project.project_id)):
        try:
            _notify_one(config, project, state, reports_dir, published_dir, filename)
        except Exception:
            # One bad report must not block notifications for the rest (DESIGN.md §5 Isolation).
            logger.error("notification failed for %s/%s", project.project_id, filename, exc_info=True)


def _notify_one(config, project: Project, state: StateStore, reports_dir, published_dir, filename: str) -> None:
    md_path = reports_dir / filename
    pdf_path = published_dir / (md_path.stem + ".pdf")

    if not md_path.is_file() or not pdf_path.is_file():
        logger.error(
            "%s/%s: marked pdf_generated but source/pdf missing on disk, skipping this run",
            project.project_id, filename,
        )
        return

    if not state.is_emailed(project.project_id, filename):
        if not project.notify_email_to:
            logger.error("%s/%s: notify.email_to not configured, cannot email", project.project_id, filename)
        else:
            send_report_email(config, project, md_path, pdf_path)
            state.mark_emailed(project.project_id, filename)
            logger.info("emailed %s/%s to %s", project.project_id, filename, project.notify_email_to)

    if not state.is_telegram_notified(project.project_id, filename):
        if not config.telegram_bot_token or not config.telegram_chat_id:
            # Telegram is optional (DESIGN.md §3) — mark done rather than leaving this
            # filename permanently "pending," which would otherwise retry and fail every
            # single run forever for a channel the user deliberately hasn't configured.
            logger.info(
                "%s/%s: Telegram not configured, skipping (optional)", project.project_id, filename
            )
            state.mark_telegram_notified(project.project_id, filename)
        else:
            send_telegram_notification(config, project, md_path)
            state.mark_telegram_notified(project.project_id, filename)
            logger.info("telegram-notified %s/%s", project.project_id, filename)
