import logging
import re
import time
from pathlib import Path

from gateway.discovery import Project
from gateway.publisher import render
from gateway.state import StateStore
from gateway.util import atomic_write_bytes

logger = logging.getLogger(__name__)

_STABILITY_CHECKS = 2
_STABILITY_INTERVAL_SECONDS = 1.0

# Google Drive for Desktop's own sync-conflict naming, e.g. "pipeline (1).md"
# alongside "pipeline.md". This is not a new report — it's a conflict copy of an
# existing one — so treating it as one produced a duplicate PDF + duplicate
# notification for the same underlying report (see runs.md 2026-08-07 incident).
_CONFLICT_COPY_RE = re.compile(r"^(?P<stem>.+) \(\d+\)$")


def publish_reports(project: Project, state: StateStore) -> None:
    reports_dir = project.path / "Reports"
    if not reports_dir.is_dir():
        return

    published_dir = reports_dir / "published"

    for md_path in sorted(reports_dir.glob("*.md")):
        filename = md_path.name

        if state.is_pdf_generated(project.project_id, filename):
            continue

        if _is_sync_conflict_copy(reports_dir, md_path):
            # Reports/ is Project Worker-owned (writer map, AI-Operating-Environment.md) —
            # the gateway detects and skips this, it doesn't delete/rename the source file.
            logger.warning(
                "%s/%s: looks like a Drive sync-conflict duplicate of an existing report, "
                "skipping publish/notify until the source file is reconciled",
                project.project_id, filename,
            )
            continue

        try:
            _publish_one(project, state, published_dir, md_path)
        except Exception:
            # One bad report must not block the rest of this project's publish pass
            # (DESIGN.md §5 Isolation) — a bug in one file shouldn't stall every other report.
            logger.error("publish failed for %s/%s", project.project_id, filename, exc_info=True)


def _is_sync_conflict_copy(reports_dir: Path, md_path: Path) -> bool:
    match = _CONFLICT_COPY_RE.match(md_path.stem)
    if not match:
        return False
    return (reports_dir / f"{match.group('stem')}.md").is_file()


def _publish_one(project: Project, state: StateStore, published_dir: Path, md_path: Path) -> None:
    filename = md_path.name

    if not _is_stable(md_path):
        logger.info("%s/%s: not yet stable (Drive sync?), will retry next run", project.project_id, filename)
        return

    pdf_bytes = render(md_path.read_text())

    pdf_path = published_dir / (md_path.stem + ".pdf")
    atomic_write_bytes(pdf_path, pdf_bytes)

    state.mark_pdf_generated(project.project_id, filename)
    logger.info("published %s/%s -> %s", project.project_id, filename, pdf_path.relative_to(project.path))


def _is_stable(path: Path, checks: int = _STABILITY_CHECKS, interval: float = _STABILITY_INTERVAL_SECONDS) -> bool:
    prev = None
    for _ in range(checks + 1):
        try:
            stat = path.stat()
        except FileNotFoundError:
            return False
        current = (stat.st_size, stat.st_mtime)
        if prev is not None and current != prev:
            return False
        prev = current
        time.sleep(interval)
    return True
