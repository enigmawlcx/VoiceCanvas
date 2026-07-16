import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr("app.config.get_api_key", lambda: "sk-test-key")
    return TestClient(create_app())


def test_get_voices_returns_grouped_lists(client):
    from app.db.voices_repo import insert_voice

    insert_voice(voice_id="local-clone-1", type="cloned", note="备注A")

    with respx.mock:
        respx.post("https://api.minimaxi.com/v1/get_voice").mock(
            return_value=httpx.Response(
                200,
                json={
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                    "system_voice": [{"voice_id": "sys-1", "voice_name": "示例音色"}],
                    "voice_cloning": [{"voice_id": "local-clone-1"}],
                    "voice_generation": [],
                },
            )
        )
        response = client.get("/api/voices")

    assert response.status_code == 200
    body = response.json()
    assert body["system"][0]["voice_id"] == "sys-1"
    assert body["cloned"][0]["voice_id"] == "local-clone-1"
    assert body["cloned"][0]["activated"] is True


def test_get_voices_returns_400_without_api_key(isolated_app_dir, monkeypatch):
    monkeypatch.setattr("app.config.get_api_key", lambda: None)
    client = TestClient(create_app())

    response = client.get("/api/voices")

    assert response.status_code == 400


def test_clone_endpoint_uploads_and_saves_local_record(client):
    with respx.mock:
        respx.post("https://api.minimaxi.com/v1/files/upload").mock(
            return_value=httpx.Response(
                200,
                json={"file": {"file_id": 1}, "base_resp": {"status_code": 0, "status_msg": "success"}},
            )
        )
        respx.post("https://api.minimaxi.com/v1/voice_clone").mock(
            return_value=httpx.Response(
                200,
                json={
                    "demo_audio": "https://example.com/demo.mp3",
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                },
            )
        )
        response = client.post(
            "/api/voices/clone",
            data={"voice_id": "MyVoiceClone1", "note": "客户A"},
            files={"file": ("sample.mp3", b"fake-audio-bytes", "audio/mpeg")},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["voice_id"] == "MyVoiceClone1"
    assert body["demo_audio"] == "https://example.com/demo.mp3"

    from app.db.voices_repo import get_voice

    saved = get_voice("MyVoiceClone1")
    assert saved is not None
    assert saved["note"] == "客户A"


def test_design_endpoint_saves_local_record(client):
    with respx.mock:
        respx.post("https://api.minimaxi.com/v1/voice_design").mock(
            return_value=httpx.Response(
                200,
                json={
                    "voice_id": "ttv-voice-generated",
                    "trial_audio": "deadbeef",
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                },
            )
        )
        response = client.post(
            "/api/voices/design",
            json={"prompt": "沉稳男声", "preview_text": "你好，世界", "note": "旁白"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["voice_id"] == "ttv-voice-generated"
    assert body["trial_audio_hex"] == "deadbeef"

    from app.db.voices_repo import get_voice

    saved = get_voice("ttv-voice-generated")
    assert saved["note"] == "旁白"


def test_patch_note_updates_local_record(client):
    from app.db.voices_repo import insert_voice

    insert_voice(voice_id="voice-x", type="cloned")

    response = client.patch("/api/voices/voice-x", json={"note": "新备注"})

    assert response.status_code == 200
    assert response.json()["note"] == "新备注"


def test_patch_note_returns_404_when_missing(client):
    response = client.patch("/api/voices/missing", json={"note": "x"})

    assert response.status_code == 404


def test_delete_voice_removes_record(client):
    from app.db.voices_repo import insert_voice

    insert_voice(voice_id="voice-y", type="designed")

    response = client.delete("/api/voices/voice-y")

    assert response.status_code == 200
    assert response.json() == {"deleted": True}


def test_delete_voice_returns_404_when_missing(client):
    response = client.delete("/api/voices/missing")

    assert response.status_code == 404
