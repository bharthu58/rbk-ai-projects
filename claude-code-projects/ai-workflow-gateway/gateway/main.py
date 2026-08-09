import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from gateway.accountability import check_run_accountability
from gateway.command_center import run_command_center
from gateway.config import ConfigError, load_config
from gateway.discovery import discover_projects
from gateway.logging_setup import setup_logging
from gateway.notify import notify_reports
from gateway.publish import publish_reports
from gateway.reply import process_replies
from gateway.state import StateStore

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Workflow Gateway")
    parser.add_argument("--config", required=True, type=Path, help="path to runtime config.yaml")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = args.config.expanduser().resolve()
    setup_logging(config_path.parent / "logs")

    try:
        config = load_config(config_path)
    except ConfigError as exc:
        logger.critical("config error: %s", exc)
        return 1

    try:
        projects = discover_projects(config.workspace_root)
    except Exception:
        logger.critical("discovery failed", exc_info=True)
        return 1

    if projects:
        logger.info(
            "discovery complete: %d active project(s): %s",
            len(projects),
            ", ".join(p.project_id for p in projects),
        )
    else:
        logger.info("discovery complete: no active projects — nothing to do this run")

    state = StateStore(config_path.parent / "state" / "gateway-state.json")
    for project in projects:
        try:
            publish_reports(project, state)
        except Exception:
            # One project's failure must not block the others (DESIGN.md §5 Isolation).
            logger.error("publish pass failed for %s", project.project_id, exc_info=True)
    state.mark_pass_run("publish", datetime.now().astimezone().isoformat())

    for project in projects:
        try:
            check_run_accountability(config, project, state)
        except Exception:
            # Detection for one project must not block accountability checks for the others
            # (same isolation principle as the publish/notify passes, DESIGN.md §5).
            logger.error("accountability check failed for %s", project.project_id, exc_info=True)
    state.mark_pass_run("accountability", datetime.now().astimezone().isoformat())

    if not config.gmail_app_password:
        # Email is the mandatory channel; Telegram is optional and gated separately
        # inside notify_reports (DESIGN.md §3) so it never blocks email.
        logger.warning("skipping notification pass: Gmail credentials not configured in runtime/.env")
    else:
        for project in projects:
            try:
                notify_reports(config, project, state)
            except Exception:
                logger.error("notify pass failed for %s", project.project_id, exc_info=True)
        state.mark_pass_run("notify", datetime.now().astimezone().isoformat())

    if not config.gmail_app_password:
        logger.warning("skipping reply pass: Gmail credentials not configured in runtime/.env")
    else:
        try:
            process_replies(config, {p.project_id: p for p in projects}, state)
        except Exception:
            logger.error("reply pass failed", exc_info=True)

    try:
        run_command_center(config.workspace_root, state, config_path.parent / "logs" / "gateway.log")
    except Exception:
        # The board is a derived convenience — a failure here must not fail the whole run.
        logger.error("command center generation failed", exc_info=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
