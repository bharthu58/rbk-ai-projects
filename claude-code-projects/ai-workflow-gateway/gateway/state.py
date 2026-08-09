import json
from pathlib import Path

from gateway.util import atomic_write_text


class StateStore:
    """Single JSON state file. See DESIGN.md §2/§5 — one atomic write surface
    covering per-project publish/notify state and the IMAP watermark."""

    def __init__(self, path: Path):
        self._path = path
        self._data = self._read()

    def _read(self) -> dict:
        if self._path.is_file():
            return json.loads(self._path.read_text())
        return {"projects": {}, "mailbox": {"uidvalidity": None, "last_uid": 0}}

    def is_pdf_generated(self, project_id: str, filename: str) -> bool:
        return self._data["projects"].get(project_id, {}).get(filename, {}).get("pdf_generated", False)

    def mark_pdf_generated(self, project_id: str, filename: str) -> None:
        entry = self._data["projects"].setdefault(project_id, {}).setdefault(filename, {})
        entry["pdf_generated"] = True
        self._save()

    def is_emailed(self, project_id: str, filename: str) -> bool:
        return self._data["projects"].get(project_id, {}).get(filename, {}).get("emailed", False)

    def mark_emailed(self, project_id: str, filename: str) -> None:
        entry = self._data["projects"].setdefault(project_id, {}).setdefault(filename, {})
        entry["emailed"] = True
        self._save()

    def is_telegram_notified(self, project_id: str, filename: str) -> bool:
        return self._data["projects"].get(project_id, {}).get(filename, {}).get("telegram_notified", False)

    def mark_telegram_notified(self, project_id: str, filename: str) -> None:
        entry = self._data["projects"].setdefault(project_id, {}).setdefault(filename, {})
        entry["telegram_notified"] = True
        self._save()

    def pending_notifications(self, project_id: str) -> list[str]:
        """Filenames with a PDF already generated but at least one notification channel outstanding."""
        return [
            filename
            for filename, entry in self._data["projects"].get(project_id, {}).items()
            if entry.get("pdf_generated") and not (entry.get("emailed") and entry.get("telegram_notified"))
        ]

    def last_checked_run_line(self, project_id: str) -> str | None:
        return self._data.get("accountability", {}).get(project_id, {}).get("last_checked_line")

    def mark_run_line_checked(self, project_id: str, line: str) -> None:
        self._data.setdefault("accountability", {}).setdefault(project_id, {})["last_checked_line"] = line
        self._save()

    def last_pass_run_at(self, pass_name: str) -> str | None:
        return self._data.get("passes", {}).get(pass_name, {}).get("last_run_at")

    def mark_pass_run(self, pass_name: str, when_iso: str) -> None:
        self._data.setdefault("passes", {})[pass_name] = {"last_run_at": when_iso}
        self._save()

    def mailbox_watermark(self) -> tuple[int | None, int]:
        mailbox = self._data["mailbox"]
        return mailbox.get("uidvalidity"), mailbox.get("last_uid", 0)

    def set_mailbox_watermark(self, uidvalidity: int, last_uid: int) -> None:
        self._data["mailbox"]["uidvalidity"] = uidvalidity
        self._data["mailbox"]["last_uid"] = last_uid
        self._save()

    def _save(self) -> None:
        atomic_write_text(self._path, json.dumps(self._data, indent=2, sort_keys=True))
