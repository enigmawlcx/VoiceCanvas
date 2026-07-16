import io
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
import respx

from app.db import get_connection
from app.services.minimax_client import MiniMaxClient
from app.services.synthesize import concat_audio_bytes, synthesize_full, synthesize_segment
from pydub import AudioSegment

BASE_URL = "https://fake.minimax.test"


def test_import_synthesize_service_without_pydub_ffmpeg_warning(tmp_path):
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "error",
            "-c",
            (
                "import imageio_ffmpeg\n"
                "import app.services.synthesize as synthesize\n"
                "assert synthesize.AudioSegment.converter "
                "== imageio_ffmpeg.get_ffmpeg_exe()"
            ),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr


def _silent_wav_hex(duration_ms: int) -> str:
    segment = AudioSegment.silent(duration=duration_ms, frame_rate=32000)
    buf = io.BytesIO()
    segment.export(buf, format="wav")
    return buf.getvalue().hex()


def _silent_wav_bytes(duration_ms: int) -> bytes:
    return bytes.fromhex(_silent_wav_hex(duration_ms))


def _silent_mp3_bytes(duration_ms: int) -> bytes:
    buf = io.BytesIO()
    AudioSegment.silent(duration=duration_ms, frame_rate=32000).export(
        buf, format="mp3", bitrate="128k"
    )
    return buf.getvalue()


@pytest.mark.parametrize(
    ("durations_ms", "expected_duration_ms"),
    [
        ([120], 120),
        ([120, 180], 1300),
        ([120, 180, 240], 2540),
    ],
)
def test_concat_audio_bytes_adds_1000ms_only_between_segments(
    tmp_path, durations_ms, expected_duration_ms
):
    output_path = concat_audio_bytes(
        [_silent_wav_bytes(duration) for duration in durations_ms],
        format="wav",
        save_dir=str(tmp_path),
        filename="combined.wav",
    )

    exported = AudioSegment.from_file(output_path, format="wav")
    assert len(exported) == pytest.approx(expected_duration_ms, abs=5)


def test_concat_mp3_exports_with_selected_constant_bitrate(tmp_path, monkeypatch):
    calls = []
    original_export = AudioSegment.export

    def recording_export(self, *args, **kwargs):
        calls.append(kwargs.copy())
        return original_export(self, *args, **kwargs)

    monkeypatch.setattr(AudioSegment, "export", recording_export)
    output_path = concat_audio_bytes(
        [_silent_mp3_bytes(100)],
        format="mp3",
        bitrate=256000,
        save_dir=str(tmp_path),
        filename="combined.mp3",
    )

    assert output_path.exists()
    assert calls[-1]["format"] == "mp3"
    assert calls[-1]["bitrate"] == "256k"


@pytest.mark.parametrize(
    "filename",
    ["../outside.wav", "/tmp/outside.wav", "nested/outside.wav", r"..\outside.wav", ".."],
)
def test_concat_audio_bytes_rejects_filename_paths(tmp_path, filename):
    with pytest.raises(ValueError, match="文件名不能包含路径"):
        concat_audio_bytes(
            [_silent_wav_bytes(100)],
            format="wav",
            save_dir=str(tmp_path),
            filename=filename,
        )

    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_segment_returns_decoded_audio_and_records_usage(db):
    audio_hex = _silent_wav_hex(200)
    respx.post(f"{BASE_URL}/v1/t2a_v2").mock(
        return_value=httpx.Response(
            200,
            json={
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "data": {"audio": audio_hex},
                "usage_characters": 6,
            },
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    audio_bytes = await synthesize_segment(
        client, text="你好世界", voice_id="voice-1", format="wav"
    )

    assert audio_bytes == bytes.fromhex(audio_hex)
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM usage_log WHERE feature='synthesize'").fetchone()
    assert row["characters"] == 6
    assert row["voice_id"] == "voice-1"


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_segment_requests_dual_channel_audio(db):
    route = respx.post(f"{BASE_URL}/v1/t2a_v2").mock(
        return_value=httpx.Response(
            200,
            json={
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "data": {"audio": _silent_wav_hex(100)},
            },
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    await synthesize_segment(client, text="你好", voice_id="voice-1", format="wav")

    sent_payload = json.loads(route.calls.last.request.content)
    assert sent_payload["audio_setting"]["channel"] == 2


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_segment_forces_selected_mp3_cbr(db):
    route = respx.post(f"{BASE_URL}/v1/t2a_v2").mock(
        return_value=httpx.Response(
            200,
            json={"base_resp": {"status_code": 0}, "data": {"audio": "00"}},
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    await synthesize_segment(
        client, text="你好", voice_id="voice-1", format="mp3", bitrate=256000
    )

    audio_setting = json.loads(route.calls.last.request.content)["audio_setting"]
    assert audio_setting["bitrate"] == 256000
    assert audio_setting["force_cbr"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("format", ["wav", "flac"])
@respx.mock
async def test_synthesize_segment_omits_mp3_bitrate_fields_for_lossless_formats(db, format):
    route = respx.post(f"{BASE_URL}/v1/t2a_v2").mock(
        return_value=httpx.Response(
            200,
            json={
                "base_resp": {"status_code": 0},
                "data": {"audio": _silent_wav_hex(100)},
            },
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    await synthesize_segment(
        client, text="你好", voice_id="voice-1", format=format, bitrate=256000
    )

    audio_setting = json.loads(route.calls.last.request.content)["audio_setting"]
    assert "bitrate" not in audio_setting
    assert "force_cbr" not in audio_setting


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_segment_raises_when_no_audio_returned(db):
    respx.post(f"{BASE_URL}/v1/t2a_v2").mock(
        return_value=httpx.Response(
            200, json={"base_resp": {"status_code": 0, "status_msg": "success"}, "data": {"audio": ""}}
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    with pytest.raises(ValueError):
        await synthesize_segment(client, text="你好", voice_id="voice-1", format="wav")


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_full_concatenates_segments_and_exports_file(db, tmp_path):
    respx.post(f"{BASE_URL}/v1/t2a_v2").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                    "data": {"audio": _silent_wav_hex(150)},
                },
            ),
            httpx.Response(
                200,
                json={
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                    "data": {"audio": _silent_wav_hex(250)},
                },
            ),
        ]
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    output = await synthesize_full(
        client,
        segments=[{"text": "第一段", "emotion": "calm"}, {"text": "第二段", "emotion": "happy"}],
        voice_id="voice-1",
        format="wav",
        save_dir=str(tmp_path),
        filename="output.wav",
    )

    assert output["completed"] == 2
    assert output["total"] == 2
    assert output["failed"] == []
    assert output["file_path"].exists()
    exported = AudioSegment.from_file(output["file_path"], format="wav")
    assert len(exported) >= 150 + 250 - 5  # 允许极小的编码误差


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_full_adds_one_gap_between_successes_when_middle_segment_fails(
    db, tmp_path
):
    respx.post(f"{BASE_URL}/v1/t2a_v2").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                    "data": {"audio": _silent_wav_hex(150)},
                },
            ),
            httpx.Response(
                200,
                json={"base_resp": {"status_code": 0, "status_msg": "success"}, "data": {"audio": ""}},
            ),
            httpx.Response(
                200,
                json={
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                    "data": {"audio": _silent_wav_hex(250)},
                },
            ),
        ]
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    output = await synthesize_full(
        client,
        segments=[
            {"text": "第一段", "emotion": "calm"},
            {"text": "第二段", "emotion": "happy"},
            {"text": "第三段", "emotion": "sad"},
        ],
        voice_id="voice-1",
        format="wav",
        save_dir=str(tmp_path),
        filename="partial.wav",
    )

    assert output["completed"] == 2
    assert output["total"] == 3
    assert output["failed"] == [{"index": 1, "error": "合成接口未返回音频数据"}]
    exported = AudioSegment.from_file(output["file_path"], format="wav")
    assert len(exported) == pytest.approx(150 + 1000 + 250, abs=5)


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_segment_includes_sound_effects_in_voice_modify(db):
    route = respx.post(f"{BASE_URL}/v1/t2a_v2").mock(
        return_value=httpx.Response(
            200,
            json={
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "data": {"audio": _silent_wav_hex(100)},
            },
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    await synthesize_segment(
        client,
        text="你好",
        voice_id="voice-1",
        format="wav",
        voice_modify={"pitch": 0, "intensity": 0, "timbre": 0, "sound_effects": "spacious_echo"},
    )

    sent_payload = json.loads(route.calls.last.request.content)
    assert sent_payload["voice_modify"]["sound_effects"] == "spacious_echo"


@pytest.mark.asyncio
async def test_synthesize_full_raises_when_no_segments(db, tmp_path):
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    with pytest.raises(ValueError):
        await synthesize_full(client, segments=[], voice_id="voice-1", save_dir=str(tmp_path))
