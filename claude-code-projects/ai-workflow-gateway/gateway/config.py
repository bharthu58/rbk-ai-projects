import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = ("workspace_root", "smtp_host", "smtp_port", "imap_host", "imap_port")
_REQUIRED_ENV_KEYS = ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class GatewayConfig:
    workspace_root: Path
    smtp_host: str
    smtp_port: int
    imap_host: str
    imap_port: int
    telegram_chat_id: str
    gmail_address: str
    gmail_app_password: str
    telegram_bot_token: str


def load_config(config_path: Path) -> GatewayConfig:
    if not config_path.is_file():
        raise ConfigError(f"config file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text()) or {}

    missing = [key for key in _REQUIRED_KEYS if not raw.get(key)]
    if missing:
        raise ConfigError(f"{config_path}: missing required key(s): {', '.join(missing)}")

    workspace_root = Path(raw["workspace_root"]).expanduser()
    if not workspace_root.is_dir():
        raise ConfigError(
            f"workspace_root does not exist or is not a directory: {workspace_root} "
            "(is Google Drive for Desktop running and signed in?)"
        )

    env = _load_env_file(config_path.parent / ".env")
    blank_env = [key for key in _REQUIRED_ENV_KEYS if not env.get(key)]
    if blank_env:
        logger.warning(
            "%s is missing or has blank value(s) for: %s — required for email and reply processing",
            config_path.parent / ".env",
            ", ".join(blank_env),
        )
    if not env.get("TELEGRAM_BOT_TOKEN") or not raw.get("telegram_chat_id"):
        logger.info(
            "Telegram not configured (telegram_bot_token and/or telegram_chat_id blank) — "
            "Telegram notifications are optional and will be skipped"
        )

    return GatewayConfig(
        workspace_root=workspace_root,
        smtp_host=raw["smtp_host"],
        smtp_port=int(raw["smtp_port"]),
        imap_host=raw["imap_host"],
        imap_port=int(raw["imap_port"]),
        telegram_chat_id=str(raw.get("telegram_chat_id") or ""),
        gmail_address=env.get("GMAIL_ADDRESS", ""),
        gmail_app_password=env.get("GMAIL_APP_PASSWORD", ""),
        telegram_bot_token=env.get("TELEGRAM_BOT_TOKEN", ""),
    )


def _load_env_file(env_path: Path) -> dict[str, str]:
    if not env_path.is_file():
        logger.warning("no .env file found at %s", env_path)
        return {}

    values: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values
