import json

import pytest
from pydantic import ValidationError

from app.config import get_app_dir, get_config_path, load_config, save_config
from app.models import AppConfig


def test_get_app_dir_creates_directory(isolated_app_dir):
    result = get_app_dir()

    assert result == isolated_app_dir
    assert result.exists()


def test_load_config_returns_defaults_when_missing(isolated_app_dir):
    config = load_config()

    assert config.default_model == "speech-2.8-hd"
    assert config.default_format == "mp3"
    assert config.default_sample_rate == 32000
    assert config.default_bitrate == 256000


def test_default_bitrate_is_256_kbps():
    assert AppConfig().default_bitrate == 256000


def test_load_config_supplies_bitrate_for_legacy_file(isolated_app_dir):
    get_config_path().write_text(
        json.dumps({"default_format": "mp3", "default_sample_rate": 32000}),
        encoding="utf-8",
    )

    assert load_config().default_bitrate == 256000


@pytest.mark.parametrize("bitrate", [32000, 64000, 128000, 256000])
def test_app_config_accepts_minimax_mp3_bitrates(bitrate):
    assert AppConfig(default_bitrate=bitrate).default_bitrate == bitrate


def test_app_config_rejects_unsupported_bitrate():
    with pytest.raises(ValidationError):
        AppConfig(default_bitrate=192000)


def test_save_and_load_config_round_trip(isolated_app_dir):
    config = AppConfig(
        default_model="speech-2.8-turbo",
        default_format="wav",
        default_sample_rate=16000,
        save_dir="/tmp/out",
    )

    save_config(config)
    loaded = load_config()

    assert loaded == config
    assert get_config_path().exists()


def test_load_config_returns_defaults_on_corrupt_json(isolated_app_dir):
    get_config_path().parent.mkdir(parents=True, exist_ok=True)
    get_config_path().write_text("not valid json", encoding="utf-8")

    config = load_config()

    assert config == AppConfig()


def test_get_app_dir_migrates_legacy_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("VOICEMAX_APP_DIR", raising=False)
    monkeypatch.setattr("app.config.Path.home", lambda: tmp_path)
    legacy = tmp_path / "Library" / "Application Support" / "VoiceMax"
    legacy.mkdir(parents=True)
    (legacy / "config.json").write_text('{"group_id":"old"}', encoding="utf-8")

    result = get_app_dir()

    assert result == tmp_path / "Library" / "Application Support" / "VoiceCanvas"
    assert (result / "config.json").exists()
    assert not legacy.exists()


def test_get_app_dir_prefers_existing_new_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("VOICEMAX_APP_DIR", raising=False)
    monkeypatch.setattr("app.config.Path.home", lambda: tmp_path)
    legacy = tmp_path / "Library" / "Application Support" / "VoiceMax"
    current = tmp_path / "Library" / "Application Support" / "VoiceCanvas"
    legacy.mkdir(parents=True)
    current.mkdir(parents=True)
    (legacy / "legacy.txt").write_text("old", encoding="utf-8")
    (current / "current.txt").write_text("new", encoding="utf-8")

    assert get_app_dir() == current
    assert (current / "current.txt").read_text() == "new"
    assert (legacy / "legacy.txt").read_text() == "old"


def test_get_app_dir_falls_back_when_migration_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("VOICEMAX_APP_DIR", raising=False)
    monkeypatch.setattr("app.config.Path.home", lambda: tmp_path)
    legacy = tmp_path / "Library" / "Application Support" / "VoiceMax"
    legacy.mkdir(parents=True)

    def fail_replace(self, target):
        raise OSError("denied")

    monkeypatch.setattr("app.config.Path.replace", fail_replace)

    assert get_app_dir() == legacy


def test_default_save_dir_uses_voicecanvas(tmp_path, monkeypatch):
    monkeypatch.setattr("app.models.Path.home", lambda: tmp_path)

    assert AppConfig().save_dir == str(tmp_path / "Music" / "VoiceCanvas")
