import json
import smtplib
import urllib.error
import urllib.request
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from gateway.config import GatewayConfig
from gateway.discovery import Project
from gateway.retry import retry


def send_report_email(config: GatewayConfig, project: Project, md_path: Path, pdf_path: Path) -> None:
    msg = EmailMessage()
    msg["Subject"] = f"[{project.project_id}] New report: {md_path.stem} ({date.today().isoformat()})"
    msg["From"] = config.gmail_address
    msg["To"] = project.notify_email_to
    msg.set_content(
        f"A new report is available for project '{project.project_id}'.\n\n"
        f"Report: {md_path.stem}\n\n"
        "The Markdown source and PDF are attached.\n\n"
        "Reply to this email to send feedback back into the project's Inbox/."
    )
    msg.add_attachment(md_path.read_bytes(), maintype="text", subtype="markdown", filename=md_path.name)
    msg.add_attachment(pdf_path.read_bytes(), maintype="application", subtype="pdf", filename=pdf_path.name)

    _send_via_smtp(config, msg)


def _send_via_smtp(config: GatewayConfig, msg: EmailMessage) -> None:
    # TLS only, per DESIGN.md §3 — SMTPS (465) or STARTTLS (587/other), never plaintext.
    def _attempt() -> None:
        if config.smtp_port == 465:
            with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=30) as smtp:
                smtp.login(config.gmail_address, config.gmail_app_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(config.gmail_address, config.gmail_app_password)
                smtp.send_message(msg)

    retry(_attempt)


def send_telegram_notification(config: GatewayConfig, project: Project, md_path: Path) -> None:
    text = f"{project.project_id}: new report available — {md_path.stem}"
    _send_telegram_text(config, text)


def send_alert_email(config: GatewayConfig, project: Project, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = f"[{project.project_id}] {subject}"
    msg["From"] = config.gmail_address
    msg["To"] = project.notify_email_to
    msg.set_content(body)

    _send_via_smtp(config, msg)


def send_telegram_alert(config: GatewayConfig, project: Project, text: str) -> None:
    _send_telegram_text(config, f"{project.project_id}: {text}")


def _send_telegram_text(config: GatewayConfig, text: str) -> None:
    payload = json.dumps({"chat_id": config.telegram_chat_id, "text": text}).encode()
    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )

    def _attempt() -> dict:
        # HTTPError (bad token, malformed request, ...) is converted to RuntimeError here,
        # which is not in retry()'s default retryable set — a 4xx/5xx is not a transient
        # network blip, so it's deliberately not retried, unlike a raw connection failure.
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Telegram API HTTP {exc.code}: {exc.read().decode(errors='replace')}") from exc

    body = retry(_attempt)
    if not body.get("ok"):
        raise RuntimeError(f"Telegram API returned ok=false: {body}")
