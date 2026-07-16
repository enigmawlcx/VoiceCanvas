import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(isolated_app_dir, monkeypatch):
    monkeypatch.setattr("app.api.settings.get_api_key", lambda: None)
    return TestClient(create_app())


def test_get_settings_returns_defaults_and_no_api_key(client, monkeypatch):
    monkeypatch.setattr("app.api.settings.get_api_key", lambda: None)
    response = client.get("/api/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["default_model"] == "speech-2.8-hd"
    assert body["default_bitrate"] == 256000
    assert body["base_url"] == "https://api.minimaxi.com"
    assert body["has_api_key"] is False
    assert body["api_key_masked"] is None


def test_put_settings_updates_config(client):
    response = client.put(
        "/api/settings",
        json={
            "default_model": "speech-2.8-turbo",
            "default_format": "wav",
            "default_sample_rate": 16000,
            "default_bitrate": 128000,
            "save_dir": "/tmp/voicemax-out",
            "base_url": "https://api.minimaxi.com",
            "group_id": "group-abc",
        },
    )

    assert response.status_code == 200

    followup = client.get("/api/settings")
    body = followup.json()
    assert body["default_model"] == "speech-2.8-turbo"
    assert body["default_bitrate"] == 128000
    assert body["group_id"] == "group-abc"


def test_put_settings_rejects_unsupported_bitrate(client):
    payload = client.get("/api/settings").json()
    payload.pop("has_api_key")
    payload.pop("api_key_masked")
    payload["default_bitrate"] = 192000

    response = client.put("/api/settings", json=payload)

    assert response.status_code == 422


def test_put_api_key_stores_key_and_masks_it(client, monkeypatch):
    store: dict[str, str] = {}
    monkeypatch.setattr("app.api.settings.set_api_key", lambda key: store.setdefault("key", key))
    monkeypatch.setattr("app.api.settings.get_api_key", lambda: store.get("key"))

    response = client.put("/api/settings/api-key", json={"api_key": "sk-1234567890abcd"})

    assert response.status_code == 200
    body = response.json()
    assert body["has_api_key"] is True
    assert body["api_key_masked"].endswith("abcd")
    assert "1234567890" not in body["api_key_masked"]


def test_delete_api_key_clears_it(client, monkeypatch):
    store: dict[str, str] = {"key": "sk-existing"}
    monkeypatch.setattr("app.api.settings.delete_api_key", lambda: store.pop("key", None))
    monkeypatch.setattr("app.api.settings.get_api_key", lambda: store.get("key"))

    response = client.delete("/api/settings/api-key")

    assert response.status_code == 200
    assert response.json()["has_api_key"] is False


def test_test_connection_returns_ok_when_key_valid(client, monkeypatch):
    monkeypatch.setattr("app.api.settings.get_api_key", lambda: "sk-valid")

    with respx.mock:
        respx.post("https://api.minimaxi.com/v1/get_voice").mock(
            return_value=httpx.Response(
                200, json={"base_resp": {"status_code": 0, "status_msg": "success"}, "system_voice": []}
            )
        )
        response = client.post("/api/settings/test-connection")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "连接成功"}


def test_test_connection_returns_error_when_no_key_configured(client, monkeypatch):
    monkeypatch.setattr("app.api.settings.get_api_key", lambda: None)

    response = client.post("/api/settings/test-connection")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "未配置" in body["message"]


def test_test_connection_returns_auth_error_message(client, monkeypatch):
    monkeypatch.setattr("app.api.settings.get_api_key", lambda: "sk-bad")

    with respx.mock:
        respx.post("https://api.minimaxi.com/v1/get_voice").mock(
            return_value=httpx.Response(
                200, json={"base_resp": {"status_code": 1004, "status_msg": "鉴权失败"}}
            )
        )
        response = client.post("/api/settings/test-connection")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "鉴权失败" in body["message"]
