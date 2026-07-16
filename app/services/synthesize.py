import io
import os
import tempfile
from datetime import datetime
from pathlib import Path

import imageio_ffmpeg

_FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
_original_path = os.environ.get("PATH")
with tempfile.TemporaryDirectory() as _ffmpeg_path:
    Path(_ffmpeg_path, "ffmpeg").symlink_to(_FFMPEG_EXE)
    try:
        os.environ["PATH"] = (
            os.pathsep.join([_ffmpeg_path, _original_path])
            if _original_path is not None
            else _ffmpeg_path
        )
        from pydub import AudioSegment
    finally:
        if _original_path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = _original_path

from app.services.minimax_client import MiniMaxClient

DEFAULT_MODEL = "speech-2.8-hd"
SEGMENT_GAP_MS = 1000

# pydub 依赖外部 ffmpeg/ffprobe 可执行文件，系统上不一定预装。这里显式指向
# imageio-ffmpeg 内置的静态 ffmpeg 二进制，避免依赖用户机器/打包环境的 PATH。
AudioSegment.converter = _FFMPEG_EXE

# pydub 探测媒体信息（mediainfo_json）硬编码只认 PATH 上名为 ffprobe/avprobe 的
# 可执行文件，且不支持像 converter 一样被显式指定路径；imageio-ffmpeg 也不提供
# ffprobe。由于服务端已知每个分段的编码格式，显式传入 codec 可跳过探测步骤，
# 从而彻底不依赖 ffprobe。
_CODEC_BY_FORMAT = {"mp3": "mp3"}


def _resolve_output_path(save_dir: str, filename: str | None, *, format: str) -> Path:
    save_path = Path(save_dir)
    output_name = filename or f"voicemax-{datetime.now().strftime('%Y%m%d-%H%M%S')}.{format}"

    # filename 来自本地 HTTP API。即使服务仅监听回环地址，也不能允许绝对路径或
    # ../ 逃逸用户配置的导出目录；反斜杠同时按路径分隔符处理，避免跨平台绕过。
    if (
        not output_name.strip()
        or output_name in {".", ".."}
        or "/" in output_name
        or "\\" in output_name
        or Path(output_name).name != output_name
    ):
        raise ValueError("文件名不能包含路径")

    return save_path / output_name


def _build_t2a_payload(
    *,
    text: str,
    model: str,
    voice_id: str,
    speed: float,
    vol: float,
    pitch: int,
    emotion: str | None,
    voice_modify: dict | None,
    sample_rate: int,
    format: str,
    bitrate: int,
) -> dict:
    voice_setting: dict = {"voice_id": voice_id, "speed": speed, "vol": vol, "pitch": pitch}
    if emotion:
        voice_setting["emotion"] = emotion

    audio_setting = {
        "sample_rate": sample_rate,
        "format": format,
        "channel": 2,  # MiniMax API：1=单声道，2=双声道，固定启用双声道输出
    }
    if format == "mp3":
        audio_setting.update({"bitrate": bitrate, "force_cbr": True})

    payload: dict = {
        "model": model,
        "text": text,
        "stream": False,
        "voice_setting": voice_setting,
        "audio_setting": audio_setting,
    }
    if voice_modify:
        payload["voice_modify"] = voice_modify
    return payload


async def synthesize_segment(
    client: MiniMaxClient,
    *,
    text: str,
    voice_id: str,
    model: str = DEFAULT_MODEL,
    speed: float = 1.0,
    vol: float = 1.0,
    pitch: int = 0,
    emotion: str | None = None,
    voice_modify: dict | None = None,
    sample_rate: int = 32000,
    format: str = "mp3",
    bitrate: int = 256000,
) -> bytes:
    payload = _build_t2a_payload(
        text=text,
        model=model,
        voice_id=voice_id,
        speed=speed,
        vol=vol,
        pitch=pitch,
        emotion=emotion,
        voice_modify=voice_modify,
        sample_rate=sample_rate,
        format=format,
        bitrate=bitrate,
    )
    result = await client.request_json(
        "POST", "/v1/t2a_v2", json=payload, feature="synthesize", model=model, voice_id=voice_id
    )

    audio_hex = (result.get("data") or {}).get("audio", "")
    if not audio_hex:
        raise ValueError("合成接口未返回音频数据")
    return bytes.fromhex(audio_hex)


def _audio_bytes_to_segment(audio_bytes: bytes, *, format: str) -> AudioSegment:
    return AudioSegment.from_file(
        io.BytesIO(audio_bytes), format=format, codec=_CODEC_BY_FORMAT.get(format)
    )


def concat_audio_bytes(
    segments_audio: list[bytes],
    *,
    format: str,
    save_dir: str,
    filename: str | None = None,
    bitrate: int = 256000,
) -> Path:
    if not segments_audio:
        raise ValueError("没有可拼接的音频")

    combined: AudioSegment | None = None
    for audio_bytes in segments_audio:
        chunk = _audio_bytes_to_segment(audio_bytes, format=format)
        if combined is None:
            combined = chunk
        else:
            silence = AudioSegment.silent(
                duration=SEGMENT_GAP_MS,
                frame_rate=combined.frame_rate,
            )
            combined = combined + silence + chunk

    output_path = _resolve_output_path(save_dir, filename, format=format)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_kwargs: dict = {"format": format}
    if format == "mp3":
        export_kwargs["bitrate"] = f"{bitrate // 1000}k"
    try:
        combined.export(output_path, **export_kwargs)
    except Exception as exc:
        raise ValueError("音频导出失败") from exc
    return output_path


async def synthesize_full(
    client: MiniMaxClient,
    *,
    segments: list[dict],
    voice_id: str,
    model: str = DEFAULT_MODEL,
    speed: float = 1.0,
    vol: float = 1.0,
    pitch: int = 0,
    voice_modify: dict | None = None,
    sample_rate: int = 32000,
    format: str = "mp3",
    bitrate: int = 256000,
    save_dir: str,
    filename: str | None = None,
) -> dict:
    if not segments:
        raise ValueError("没有可合成的分段")

    successful_audio: list[bytes] = []
    failed: list[dict] = []
    for index, segment in enumerate(segments):
        try:
            audio_bytes = await synthesize_segment(
                client,
                text=segment["text"],
                voice_id=voice_id,
                model=model,
                speed=speed,
                vol=vol,
                pitch=pitch,
                emotion=segment.get("emotion"),
                voice_modify=voice_modify,
                sample_rate=sample_rate,
                format=format,
                bitrate=bitrate,
            )
        except Exception as exc:
            failed.append({"index": index, "error": str(exc)})
            continue
        successful_audio.append(audio_bytes)

    if not successful_audio:
        raise ValueError("所有分段合成均失败")

    output_path = concat_audio_bytes(
        successful_audio,
        format=format,
        save_dir=save_dir,
        filename=filename,
        bitrate=bitrate,
    )
    return {
        "file_path": output_path,
        "total": len(segments),
        "completed": len(successful_audio),
        "failed": failed,
    }
