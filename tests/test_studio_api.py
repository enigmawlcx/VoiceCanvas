import io
import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pydub import AudioSegment

from app.main import create_app


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr("app.config.get_api_key", lambda: "sk-test-key")
    return TestClient(create_app())


def _silent_wav_hex(duration_ms: int = 100) -> str:
    segment = AudioSegment.silent(duration=duration_ms, frame_rate=32000)
    buf = io.BytesIO()
    segment.export(buf, format="wav")
    return buf.getvalue().hex()


def test_polish_endpoint_returns_annotated_text_and_segments(client):
    content = json.dumps({"segments": [{"text": "你好世界", "emotion": "calm"}]}, ensure_ascii=False)
    with respx.mock:
        respx.post("https://api.minimaxi.com/v1/text/chatcompletion_v2").mock(
            return_value=httpx.Response(
                200,
                json={
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                    "choices": [{"message": {"role": "assistant", "content": content}}],
                },
            )
        )
        response = client.post("/api/studio/polish", json={"source_text": "你好世界"})

    assert response.status_code == 200
    body = response.json()
    assert body["annotated_text"] == "[calm] 你好世界"
    assert body["segments"] == [{"text": "你好世界", "emotion": "calm"}]
    assert body["notice"] is None


def test_polish_endpoint_includes_notice_when_llm_cannot_preserve_source_text(client):
    with respx.mock:
        respx.post("https://api.minimaxi.com/v1/text/chatcompletion_v2").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "base_resp": {"status_code": 0, "status_msg": "success"},
                        "choices": [{"message": {"role": "assistant", "content": "不是JSON"}}],
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "base_resp": {"status_code": 0, "status_msg": "success"},
                        "choices": [{"message": {"role": "assistant", "content": "还是不是JSON"}}],
                    },
                ),
            ]
        )
        response = client.post("/api/studio/polish", json={"source_text": "你好，世界。"})

    assert response.status_code == 200
    body = response.json()
    assert body["notice"] == "AI 未能在保留原文前提下完成标注，已自动按标点分段，可手动点击情绪/语气词按钮补充"
    assert body["segments"] == [{"text": "你好，世界。", "emotion": None}]


def test_get_tags_endpoint_returns_fixed_emotion_and_interjection_lists(client):
    response = client.get("/api/studio/tags")

    assert response.status_code == 200
    body = response.json()
    assert len(body["emotions"]) == 9
    assert len(body["interjections"]) == 19
    assert {"id": "happy", "label": "开心"} in body["emotions"]
    assert {"id": "laughs", "label": "笑声"} in body["interjections"]


def test_polish_endpoint_returns_400_without_api_key(isolated_app_dir, monkeypatch):
    monkeypatch.setattr("app.config.get_api_key", lambda: None)
    client = TestClient(create_app())

    response = client.post("/api/studio/polish", json={"source_text": "x"})

    assert response.status_code == 400


def test_annotate_parse_endpoint_does_not_call_minimax(client):
    response = client.post(
        "/api/studio/annotate/parse", json={"annotated_text": "[happy] 分段一\n[sad] 分段二"}
    )

    assert response.status_code == 200
    assert response.json() == [
        {"text": "分段一", "emotion": "happy"},
        {"text": "分段二", "emotion": "sad"},
    ]


def test_synthesize_segment_endpoint_returns_audio_hex(client, monkeypatch):
    from app.config import save_config
    from app.models import AppConfig

    save_config(AppConfig(default_format="wav"))
    audio_hex = _silent_wav_hex()

    with respx.mock:
        respx.post("https://api.minimaxi.com/v1/t2a_v2").mock(
            return_value=httpx.Response(
                200,
                json={"base_resp": {"status_code": 0, "status_msg": "success"}, "data": {"audio": audio_hex}},
            )
        )
        response = client.post(
            "/api/studio/synthesize/segment",
            json={"text": "你好", "voice_id": "voice-1", "emotion": "calm"},
        )

    assert response.status_code == 200
    assert response.json()["audio_hex"] == audio_hex


def test_segment_endpoint_uses_request_audio_snapshot(client):
    from app.config import save_config
    from app.models import AppConfig

    save_config(AppConfig(default_format="wav", default_sample_rate=16000, default_bitrate=32000))
    with respx.mock:
        route = respx.post("https://api.minimaxi.com/v1/t2a_v2").mock(
            return_value=httpx.Response(
                200,
                json={"base_resp": {"status_code": 0}, "data": {"audio": "00"}},
            )
        )
        response = client.post(
            "/api/studio/synthesize/segment",
            json={
                "text": "你好",
                "voice_id": "voice-1",
                "audio_config": {
                    "format": "mp3",
                    "sample_rate": 32000,
                    "bitrate": 256000,
                },
            },
        )

    assert response.status_code == 200
    setting = json.loads(route.calls.last.request.content)["audio_setting"]
    assert setting["format"] == "mp3"
    assert setting["sample_rate"] == 32000
    assert setting["bitrate"] == 256000
    assert setting["force_cbr"] is True


def test_segment_endpoint_rejects_invalid_audio_snapshot(client):
    response = client.post(
        "/api/studio/synthesize/segment",
        json={
            "text": "你好",
            "voice_id": "voice-1",
            "audio_config": {
                "format": "mp3",
                "sample_rate": 32000,
                "bitrate": 192000,
            },
        },
    )

    assert response.status_code == 422


def test_synthesize_full_endpoint_exports_file(client, tmp_path):
    from app.config import save_config
    from app.models import AppConfig

    save_config(AppConfig(default_format="wav", save_dir=str(tmp_path)))

    with respx.mock:
        respx.post("https://api.minimaxi.com/v1/t2a_v2").mock(
            return_value=httpx.Response(
                200,
                json={
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                    "data": {"audio": _silent_wav_hex()},
                },
            )
        )
        response = client.post(
            "/api/studio/synthesize/full",
            json={
                "segments": [{"text": "第一段", "emotion": "calm"}, {"text": "第二段"}],
                "voice_id": "voice-1",
                "filename": "final.wav",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["file_path"].endswith("final.wav")
    assert body["total"] == 2
    assert body["completed"] == 2
    assert body["failed"] == []
    from pathlib import Path

    assert Path(body["file_path"]).exists()


def test_concat_endpoint_passes_audio_snapshot(client, tmp_path, monkeypatch):
    captured = {}

    def fake_concat(audio_list, **kwargs):
        captured.update(kwargs)
        return tmp_path / "final.mp3"

    monkeypatch.setattr("app.api.studio.concat_audio_bytes", fake_concat)
    response = client.post(
        "/api/studio/synthesize/concat",
        json={
            "audio_hex_list": ["00"],
            "audio_config": {
                "format": "mp3",
                "sample_rate": 32000,
                "bitrate": 128000,
            },
        },
    )

    assert response.status_code == 200
    assert captured["format"] == "mp3"
    assert captured["bitrate"] == 128000


def test_full_endpoint_passes_audio_snapshot(client, tmp_path, monkeypatch):
    captured = {}

    async def fake_full(client, **kwargs):
        captured.update(kwargs)
        return {
            "file_path": tmp_path / "final.mp3",
            "total": 1,
            "completed": 1,
            "failed": [],
        }

    monkeypatch.setattr("app.api.studio.synthesize_full", fake_full)
    response = client.post(
        "/api/studio/synthesize/full",
        json={
            "segments": [{"text": "第一段"}],
            "voice_id": "voice-1",
            "audio_config": {
                "format": "mp3",
                "sample_rate": 44100,
                "bitrate": 64000,
            },
        },
    )

    assert response.status_code == 200
    assert captured["format"] == "mp3"
    assert captured["sample_rate"] == 44100
    assert captured["bitrate"] == 64000


def test_project_crud_flow(client):
    create_response = client.post(
        "/api/studio/projects", json={"title": "我的项目", "source_text": "原文内容"}
    )
    assert create_response.status_code == 201
    project = create_response.json()
    project_id = project["id"]

    list_response = client.get("/api/studio/projects")
    assert any(p["id"] == project_id for p in list_response.json())

    get_response = client.get(f"/api/studio/projects/{project_id}")
    assert get_response.json()["title"] == "我的项目"

    update_response = client.put(
        f"/api/studio/projects/{project_id}", json={"annotated_text": "[calm] 标注后文本"}
    )
    assert update_response.json()["annotated_text"] == "[calm] 标注后文本"

    delete_response = client.delete(f"/api/studio/projects/{project_id}")
    assert delete_response.status_code == 200

    missing_response = client.get(f"/api/studio/projects/{project_id}")
    assert missing_response.status_code == 404


def test_get_project_returns_404_when_missing(client):
    response = client.get("/api/studio/projects/999999")

    assert response.status_code == 404
