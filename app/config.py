import json
import logging
import os
from pathlib import Path

import keyring

from app.models import AppConfig

logger = logging.getLogger(__name__)


def _default_app_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "VoiceCanvas"


def _legacy_app_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "VoiceMax"


def get_app_dir() -> Path:
    override = os.environ.get("VOICEMAX_APP_DIR")
    if override:
        base = Path(override)
        base.mkdir(parents=True, exist_ok=True)
        return base

    current = _default_app_dir()
    legacy = _legacy_app_dir()
    if current.exists():
        return current
    if legacy.exists():
        try:
            return legacy.replace(current)
        except OSError:
            logger.exception("无法将 VoiceMax 数据目录迁移到 VoiceCanvas，继续使用旧目录")
            return legacy
    current.mkdir(parents=True, exist_ok=True)
    return current


def get_config_path() -> Path:
    return get_app_dir() / "config.json"


def load_config() -> AppConfig:
    path = get_config_path()
    if not path.exists():
        return AppConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return AppConfig()
    return AppConfig(**data)


def save_config(config: AppConfig) -> None:
    path = get_config_path()
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")


KEYRING_SERVICE = "VoiceCanvas"
LEGACY_KEYRING_SERVICE = "VoiceMax"
KEYRING_USERNAME = "minimax_api_key"
KEYRING_CLEARED_SENTINEL = "__VOICECANVAS_CLEARED__"


def get_api_key() -> str | None:
    current = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    if current == KEYRING_CLEARED_SENTINEL:
        return None
    if current is not None:
        return current
    legacy = keyring.get_password(LEGACY_KEYRING_SERVICE, KEYRING_USERNAME)
    if legacy is None:
        return None
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, legacy)
    except keyring.errors.KeyringError:
        logger.exception("无法将 VoiceMax API Key 迁移到 VoiceCanvas，继续使用旧凭据")
    return legacy


def set_api_key(api_key: str) -> None:
    keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, api_key)


def delete_api_key() -> None:
    keyring.set_password(
        KEYRING_SERVICE,
        KEYRING_USERNAME,
        KEYRING_CLEARED_SENTINEL,
    )
