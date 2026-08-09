import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# `YYYY-MM-DD HH:MM | <task-id> | ok|partial|failed | <expected artifact paths> | <one-line note>`
# per AI-Operating-Environment.md → Run Accountability. Shared by gateway.accountability
# (single newest line, project-wide) and gateway.command_center (newest line per task).
_RUN_LINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\s+\S+\s*\|")
_NO_ARTIFACT_PLACEHOLDERS = {"", "-", "—", "n/a", "na"}


@dataclass(frozen=True)
class RunLine:
    raw: str
    date: str
    time: str
    task_id: str
    status: str
    artifacts: list[str]
    note: str

    @property
    def timestamp(self) -> datetime | None:
        try:
            return datetime.strptime(f"{self.date} {self.time}", "%Y-%m-%d %H:%M")
        except ValueError:
            pass
        try:
            # Backfill lines may carry an unparseable time (e.g. "??:??") — fall back
            # to date-only precision rather than treating the whole line as unusable.
            return datetime.strptime(self.date, "%Y-%m-%d")
        except ValueError:
            return None


def parse_run_lines(runs_path: Path) -> list[RunLine]:
    if not runs_path.is_file():
        return []

    lines: list[RunLine] = []
    for raw in runs_path.read_text().splitlines():
        stripped = raw.strip()
        if not _RUN_LINE_RE.match(stripped):
            continue

        fields = [f.strip() for f in stripped.split("|")]
        if len(fields) < 5:
            continue

        ts_parts = fields[0].split(None, 1)
        date_str = ts_parts[0]
        time_str = ts_parts[1] if len(ts_parts) > 1 else ""

        artifacts = [
            token.strip()
            for token in fields[3].split(",")
            if token.strip().lower() not in _NO_ARTIFACT_PLACEHOLDERS
        ]

        lines.append(
            RunLine(
                raw=stripped,
                date=date_str,
                time=time_str,
                task_id=fields[1],
                status=fields[2].lower(),
                artifacts=artifacts,
                note=fields[4],
            )
        )
    return lines


def newest_line(lines: list[RunLine]) -> RunLine | None:
    """Newest at the bottom of the file (AI-Operating-Environment.md convention)."""
    return lines[-1] if lines else None


def newest_line_per_task(lines: list[RunLine]) -> dict[str, RunLine]:
    result: dict[str, RunLine] = {}
    for line in lines:
        result[line.task_id] = line  # later (= newer) entries overwrite earlier ones
    return result
