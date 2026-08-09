import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Project:
    project_id: str
    path: Path
    notify_email_to: str | None


@dataclass(frozen=True)
class BoardProject:
    """A project as the Command Center sees it — broader than `Project`: every
    top-level Workspace dir with a project.yaml, not only gateway_enabled ones."""

    project_id: str
    title: str
    path: Path
    cadence: list[dict]
    retention: dict
    storage_mode: str | None


def discover_projects(workspace_root: Path) -> list[Project]:
    candidates: dict[str, list[Project]] = {}

    for entry in sorted(workspace_root.iterdir()):
        if not entry.is_dir():
            continue

        project_yaml = entry / "project.yaml"
        if not project_yaml.is_file():
            continue

        try:
            raw = yaml.safe_load(project_yaml.read_text()) or {}
        except yaml.YAMLError as exc:
            logger.warning("skipping %s: could not parse project.yaml (%s)", entry.name, exc)
            continue

        if raw.get("gateway_enabled") is not True:
            logger.info("skipping %s: gateway_enabled is not true", entry.name)
            continue

        project_id = raw.get("project")
        if not project_id:
            logger.error("skipping %s: gateway_enabled is true but 'project' key is missing/empty", entry.name)
            continue

        notify_email_to = (raw.get("notify") or {}).get("email_to")
        if not notify_email_to:
            logger.warning("%s: gateway_enabled is true but notify.email_to is not set", entry.name)

        candidates.setdefault(project_id, []).append(
            Project(project_id=project_id, path=entry, notify_email_to=notify_email_to)
        )

    active: list[Project] = []
    for project_id, projects in candidates.items():
        if len(projects) > 1:
            paths = ", ".join(str(p.path) for p in projects)
            logger.error(
                "project_id collision on '%s' across [%s] — all of them skipped this run", project_id, paths
            )
            continue
        active.append(projects[0])

    return active


def discover_all_projects(workspace_root: Path) -> list[BoardProject]:
    """Command Center active-project rule (SPEC in aoe-gateway/State.md): every
    top-level Workspace dir containing project.yaml, excluding Archive/ — no
    gateway_enabled gate, unlike `discover_projects` above."""
    projects: list[BoardProject] = []

    for entry in sorted(workspace_root.iterdir()):
        if not entry.is_dir() or entry.name == "Archive":
            continue

        project_yaml = entry / "project.yaml"
        if not project_yaml.is_file():
            continue

        try:
            raw = yaml.safe_load(project_yaml.read_text()) or {}
        except yaml.YAMLError as exc:
            logger.warning("command center: skipping %s: could not parse project.yaml (%s)", entry.name, exc)
            continue

        project_id = raw.get("project") or entry.name
        title = raw.get("title") or project_id

        retention = raw.get("retention")
        if not isinstance(retention, dict):
            # career-agent uses a flat `retention_days` key rather than a nested
            # `retention:` block — normalize both shapes to a dict for display.
            retention_days = raw.get("retention_days")
            retention = {"retention_days": retention_days} if retention_days is not None else {}

        projects.append(
            BoardProject(
                project_id=project_id,
                title=title,
                path=entry,
                cadence=raw.get("cadence") or [],
                retention=retention,
                storage_mode=(raw.get("storage") or {}).get("mode"),
            )
        )

    return projects
