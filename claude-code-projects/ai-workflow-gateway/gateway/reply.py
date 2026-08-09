import email
import imaplib
import logging
import re
from datetime import date
from email.header import decode_header
from email.utils import parseaddr

from gateway.config import GatewayConfig
from gateway.discovery import Project
from gateway.reply_router import resolve_project
from gateway.retry import retry
from gateway.state import StateStore
from gateway.util import atomic_write_text

logger = logging.getLogger(__name__)

_UIDVALIDITY_RE = re.compile(rb"UIDVALIDITY (\d+)")
_UIDNEXT_RE = re.compile(rb"UIDNEXT (\d+)")


def _connect(config: GatewayConfig) -> imaplib.IMAP4_SSL:
    # TLS only, per DESIGN.md §3 — IMAPS, never plaintext IMAP. Connection establishment
    # (DNS/network blip) is the most likely transient failure point, so it's retried;
    # a bad-credentials login failure raises imaplib.IMAP4.error, not OSError, so it
    # is not retried — retrying wrong credentials wouldn't help.
    def _attempt() -> imaplib.IMAP4_SSL:
        imap = imaplib.IMAP4_SSL(config.imap_host, config.imap_port)
        imap.login(config.gmail_address, config.gmail_app_password)
        return imap

    return retry(_attempt)


def process_replies(config: GatewayConfig, registry: dict[str, Project], state: StateStore) -> None:
    imap = _connect(config)
    try:
        imap.select("INBOX")

        current_uidvalidity, uidnext = _status(imap)
        stored_uidvalidity, last_uid = state.mailbox_watermark()

        if stored_uidvalidity is not None and stored_uidvalidity != current_uidvalidity:
            logger.warning(
                "IMAP UIDVALIDITY changed (%s -> %s): mailbox was rebuilt server-side; resetting the "
                "watermark to now rather than reconciling old UIDs (DESIGN.md §5) — anything already "
                "in the mailbox from before this point needs a manual look",
                stored_uidvalidity, current_uidvalidity,
            )
            last_uid = uidnext - 1

        typ, data = imap.uid("search", None, f"UID {last_uid + 1}:*")
        if typ != "OK":
            raise RuntimeError(f"IMAP UID SEARCH failed: {typ} {data}")

        raw_uids = data[0].split() if data and data[0] else []
        # Some IMAP servers return the highest existing UID for an out-of-range "N:*"
        # search instead of an empty result; filter defensively rather than trust it.
        uids = sorted(u for u in (int(x) for x in raw_uids) if u > last_uid)

        for uid in uids:
            try:
                _process_one(imap, uid, registry)
            except Exception:
                logger.error("failed to process reply UID %d", uid, exc_info=True)
            finally:
                state.set_mailbox_watermark(current_uidvalidity, uid)
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def _status(imap: imaplib.IMAP4_SSL) -> tuple[int, int]:
    typ, data = imap.status("INBOX", "(UIDVALIDITY UIDNEXT)")
    if typ != "OK":
        raise RuntimeError(f"IMAP STATUS failed: {typ} {data}")
    blob = data[0]
    uidvalidity = int(_UIDVALIDITY_RE.search(blob).group(1))
    uidnext = int(_UIDNEXT_RE.search(blob).group(1))
    return uidvalidity, uidnext


def _process_one(imap: imaplib.IMAP4_SSL, uid: int, registry: dict[str, Project]) -> None:
    typ, data = imap.uid("fetch", str(uid), "(RFC822)")
    if typ != "OK" or not data or data[0] is None:
        logger.warning("UID %d: fetch failed, treating as unprocessed", uid)
        return

    msg = email.message_from_bytes(data[0][1])
    subject = _decode_header(msg.get("Subject", ""))
    from_header = msg.get("From", "")

    project = resolve_project(subject, from_header, registry)
    if project is None:
        logger.warning("UID %d: no routable project (subject=%r, from=%r)", uid, subject, from_header)
        return

    body = _extract_plain_text(msg)
    if body is None:
        logger.warning("UID %d: no text/plain body found, skipping", uid)
        return

    _write_reply(project, subject, from_header, body)
    logger.info("UID %d: routed reply into %s/Inbox/", uid, project.project_id)


def _decode_header(raw: str) -> str:
    return "".join(
        part.decode(encoding or "utf-8", errors="replace") if isinstance(part, bytes) else part
        for part, encoding in decode_header(raw)
    )


def _extract_plain_text(msg: email.message.Message) -> str | None:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and part.get_content_disposition() != "attachment":
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                return payload.decode(charset, errors="replace") if payload is not None else None
        return None

    if msg.get_content_type() == "text/plain":
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        return payload.decode(charset, errors="replace") if payload is not None else None

    return None


def _write_reply(project: Project, subject: str, from_header: str, body: str) -> None:
    inbox_dir = project.path / "Inbox"
    today = date.today().isoformat()

    filename = f"{today}-email-reply.md"
    path = inbox_dir / filename
    suffix = 2
    while path.exists():
        filename = f"{today}-email-reply-{suffix}.md"
        path = inbox_dir / filename
        suffix += 1

    content = (
        "# Email Reply\n\n"
        f"- **Project:** {project.project_id}\n"
        f"- **Date:** {today}\n"
        f"- **Original Subject:** {subject}\n"
        f"- **From:** {parseaddr(from_header)[1]}\n\n"
        "---\n\n"
        f"{body.strip()}\n"
    )
    atomic_write_text(path, content)
