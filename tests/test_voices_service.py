import httpx
import pytest
import respx

from app.db import get_connection
from app.services.minimax_client import MiniMaxClient
from app.services.voices import clone_voice, design_voice, fetch_remote_voices

BASE_URL = "https://fake.minimax.test"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_remote_voices_returns_grouped_payload(db):
    respx.post(f"{BASE_URL}/v1/get_voice").mock(
        return_value=httpx.Response(
            200,
            json={
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "system_voice": [{"voice_id": "sys-1", "voice_name": "示例"}],
                "voice_cloning": [],
                "voice_generation": [],
            },
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    result = await fetch_remote_voices(client)

    assert result["system_voice"][0]["voice_id"] == "sys-1"


@pytest.mark.asyncio
@respx.mock
async def test_clone_voice_uploads_then_clones_without_preview(db):
    respx.post(f"{BASE_URL}/v1/files/upload").mock(
        return_value=httpx.Response(
            200,
            json={"file": {"file_id": 111}, "base_resp": {"status_code": 0, "status_msg": "success"}},
        )
    )
    clone_route = respx.post(f"{BASE_URL}/v1/voice_clone").mock(
        return_value=httpx.Response(
            200, json={"demo_audio": "", "base_resp": {"status_code": 0, "status_msg": "success"}}
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    result = await clone_voice(
        client, file_bytes=b"audio-bytes", filename="a.mp3", voice_id="MyVoice001"
    )

    sent_body = clone_route.calls.last.request.content
    assert b'"file_id":111' in sent_body
    assert b'"text"' not in sent_body
    assert result["demo_audio"] == ""

    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM usage_log WHERE feature='clone'").fetchone()["c"]
    assert count == 1


@pytest.mark.asyncio
@respx.mock
async def test_clone_voice_records_characters_from_extra_info_when_preview_given(db):
    respx.post(f"{BASE_URL}/v1/files/upload").mock(
        return_value=httpx.Response(
            200,
            json={"file": {"file_id": 111}, "base_resp": {"status_code": 0, "status_msg": "success"}},
        )
    )
    respx.post(f"{BASE_URL}/v1/voice_clone").mock(
        return_value=httpx.Response(
            200,
            json={
                "demo_audio": "https://example.com/demo.mp3",
                "extra_info": {"usage_characters": 18},
                "base_resp": {"status_code": 0, "status_msg": "success"},
            },
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    await clone_voice(
        client,
        file_bytes=b"audio-bytes",
        filename="a.mp3",
        voice_id="MyVoice001",
        preview_text="你好，世界",
    )

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM usage_log WHERE feature='clone'").fetchone()
    assert row["characters"] == 18
    assert row["voice_id"] == "MyVoice001"


@pytest.mark.asyncio
@respx.mock
async def test_clone_voice_sends_clone_prompt_when_given(db):
    respx.post(f"{BASE_URL}/v1/files/upload").mock(
        return_value=httpx.Response(
            200,
            json={"file": {"file_id": 111}, "base_resp": {"status_code": 0, "status_msg": "success"}},
        )
    )
    clone_route = respx.post(f"{BASE_URL}/v1/voice_clone").mock(
        return_value=httpx.Response(
            200, json={"demo_audio": "", "base_resp": {"status_code": 0, "status_msg": "success"}}
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    await clone_voice(
        client,
        file_bytes=b"audio-bytes",
        filename="a.mp3",
        voice_id="MyVoice001",
        clone_prompt="请模仿稳重的播音风格",
    )

    sent_body = clone_route.calls.last.request.content.decode()
    assert "clone_prompt" in sent_body
    assert "请模仿稳重的播音风格" in sent_body


@pytest.mark.asyncio
@respx.mock
async def test_design_voice_records_estimated_characters(db):
    respx.post(f"{BASE_URL}/v1/voice_design").mock(
        return_value=httpx.Response(
            200,
            json={
                "voice_id": "ttv-voice-xyz",
                "trial_audio": "deadbeef",
                "base_resp": {"status_code": 0, "status_msg": "success"},
            },
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    result = await design_voice(client, prompt="活力四射的男声", preview_text="大家好")

    assert result["voice_id"] == "ttv-voice-xyz"
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM usage_log WHERE feature='design'").fetchone()
    assert row["characters"] == len("大家好")
    assert row["voice_id"] == "ttv-voice-xyz"
