import re
from email.utils import parseaddr

from gateway.discovery import Project

_REPLY_PREFIX = re.compile(r"^\s*(?:re|fwd|fw)\s*:\s*", re.IGNORECASE)
_TAG = re.compile(r"\[([^\]]+)\]")


def strip_reply_prefixes(subject: str) -> str:
    """Strip a leading Re:/Fwd:/Fw: chain, e.g. 'Re: Re: Fwd: [x] y' -> '[x] y'."""
    while True:
        stripped = _REPLY_PREFIX.sub("", subject, count=1)
        if stripped == subject:
            return subject
        subject = stripped


def extract_project_tag(subject: str) -> str | None:
    match = _TAG.search(strip_reply_prefixes(subject))
    return match.group(1) if match else None


def resolve_project(subject: str, from_header: str, registry: dict[str, Project]) -> Project | None:
    """Tag match alone is not authentication (DESIGN.md §3) — the sender must also
    match the project's configured notify.email_to, or this returns None."""
    tag = extract_project_tag(subject)
    if not tag:
        return None

    project = registry.get(tag)
    if project is None or not project.notify_email_to:
        return None

    sender = parseaddr(from_header)[1].lower()
    if sender != project.notify_email_to.lower():
        return None

    return project
