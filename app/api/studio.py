from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import load_config
from app.db.projects_repo import (
    delete_project,
    get_project,
    insert_project,
    list_projects,
    update_project,
)
from app.models import AppConfig, Bitrate
from app.services.annotate import parse_annotated_text
from app.services.minimax_client import MiniMaxAuthError, MiniMaxError, build_client
from app.services.polish import polish_text
from app.services.synthesize import concat_audio_bytes, synthesize_full, synthesize_segment
from app.services.tags import EMOTIONS, INTERJECTIONS

router = APIRouter(prefix="/api/studio", tags=["studio"])


def _raise_http_error(exc: MiniMaxError) -> None:
    status_code = 400 if isinstance(exc, MiniMaxAuthError) else 502
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc


class PolishRequest(BaseModel):
    source_text: str


class PolishResponse(BaseModel):
    annotated_text: str
    segments: list[dict]
    notice: str | None = None


class TagsResponse(BaseModel):
    emotions: list[dict]
    interjections: list[dict]


class AnnotateParseRequest(BaseModel):
    annotated_text: str


class VoiceModifyPayload(BaseModel):
    pitch: int = 0
    intensity: int = 0
    timbre: int = 0
    sound_effects: str | None = None


AudioFormat = Literal["mp3", "wav", "flac"]
SampleRate = Literal[8000, 16000, 22050, 24000, 32000, 44100]


class AudioConfigPayload(BaseModel):
    format: AudioFormat
    sample_rate: SampleRate
    bitrate: Bitrate


def _resolve_audio_config(
    payload: AudioConfigPayload | None, config: AppConfig
) -> tuple[str, int, int]:
    if payload is not None:
        return payload.format, payload.sample_rate, payload.bitrate
    return config.default_format, config.default_sample_rate, config.default_bitrate


class SegmentPayload(BaseModel):
    text: str
    emotion: str | None = None


class SegmentSynthesizeRequest(BaseModel):
    text: str
    emotion: str | None = None
    voice_id: str
    model: str | None = None
    speed: float = 1.0
    vol: float = 1.0
    pitch: int = 0
    voice_modify: VoiceModifyPayload | None = None
    audio_config: AudioConfigPayload | None = None


class SegmentSynthesizeResponse(BaseModel):
    audio_hex: str


class FullSynthesizeRequest(BaseModel):
    segments: list[SegmentPayload]
    voice_id: str
    model: str | None = None
    speed: float = 1.0
    vol: float = 1.0
    pitch: int = 0
    voice_modify: VoiceModifyPayload | None = None
    filename: str | None = None
    audio_config: AudioConfigPayload | None = None


class FailedSegmentInfo(BaseModel):
    index: int
    error: str


class FullSynthesizeResponse(BaseModel):
    file_path: str
    total: int
    completed: int
    failed: list[FailedSegmentInfo]


class ConcatSynthesizeRequest(BaseModel):
    audio_hex_list: list[str]
    filename: str | None = None
    audio_config: AudioConfigPayload | None = None


class ConcatSynthesizeResponse(BaseModel):
    file_path: str


class ProjectPayload(BaseModel):
    title: str | None = None
    source_text: str | None = None
    annotated_text: str | None = None


@router.get("/tags", response_model=TagsResponse)
def get_tags() -> TagsResponse:
    return TagsResponse(emotions=EMOTIONS, interjections=INTERJECTIONS)


@router.post("/polish", response_model=PolishResponse)
async def polish(payload: PolishRequest) -> PolishResponse:
    try:
        client = build_client()
        result = await polish_text(client, source_text=payload.source_text)
    except MiniMaxError as exc:
        _raise_http_error(exc)

    return PolishResponse(**result)


@router.post("/annotate/parse")
def annotate_parse(payload: AnnotateParseRequest) -> list[dict]:
    return parse_annotated_text(payload.annotated_text)


@router.post("/synthesize/segment", response_model=SegmentSynthesizeResponse)
async def synthesize_one_segment(payload: SegmentSynthesizeRequest) -> SegmentSynthesizeResponse:
    config = load_config()
    format, sample_rate, bitrate = _resolve_audio_config(payload.audio_config, config)
    try:
        client = build_client()
        audio_bytes = await synthesize_segment(
            client,
            text=payload.text,
            voice_id=payload.voice_id,
            model=payload.model or config.default_model,
            speed=payload.speed,
            vol=payload.vol,
            pitch=payload.pitch,
            emotion=payload.emotion,
            voice_modify=payload.voice_modify.model_dump() if payload.voice_modify else None,
            sample_rate=sample_rate,
            format=format,
            bitrate=bitrate,
        )
    except MiniMaxError as exc:
        _raise_http_error(exc)

    return SegmentSynthesizeResponse(audio_hex=audio_bytes.hex())


@router.post("/synthesize/full", response_model=FullSynthesizeResponse)
async def synthesize_all(payload: FullSynthesizeRequest) -> FullSynthesizeResponse:
    config = load_config()
    format, sample_rate, bitrate = _resolve_audio_config(payload.audio_config, config)
    try:
        client = build_client()
        result = await synthesize_full(
            client,
            segments=[segment.model_dump() for segment in payload.segments],
            voice_id=payload.voice_id,
            model=payload.model or config.default_model,
            speed=payload.speed,
            vol=payload.vol,
            pitch=payload.pitch,
            voice_modify=payload.voice_modify.model_dump() if payload.voice_modify else None,
            sample_rate=sample_rate,
            format=format,
            bitrate=bitrate,
            save_dir=config.save_dir,
            filename=payload.filename,
        )
    except MiniMaxError as exc:
        _raise_http_error(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FullSynthesizeResponse(
        file_path=str(result["file_path"]),
        total=result["total"],
        completed=result["completed"],
        failed=result["failed"],
    )


@router.post("/synthesize/concat", response_model=ConcatSynthesizeResponse)
async def synthesize_concat(payload: ConcatSynthesizeRequest) -> ConcatSynthesizeResponse:
    config = load_config()
    format, _, bitrate = _resolve_audio_config(payload.audio_config, config)
    if not payload.audio_hex_list:
        raise HTTPException(status_code=400, detail="没有可拼接的音频")
    try:
        audio_list = [bytes.fromhex(hex_str) for hex_str in payload.audio_hex_list]
        output_path = concat_audio_bytes(
            audio_list,
            format=format,
            bitrate=bitrate,
            save_dir=config.save_dir,
            filename=payload.filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ConcatSynthesizeResponse(file_path=str(output_path))


@router.get("/projects")
def get_projects() -> list[dict]:
    return list_projects()


@router.post("/projects", status_code=201)
def create_project(payload: ProjectPayload) -> dict:
    project_id = insert_project(
        title=payload.title or "未命名项目",
        source_text=payload.source_text or "",
        annotated_text=payload.annotated_text,
    )
    return get_project(project_id)


@router.get("/projects/{project_id}")
def get_project_detail(project_id: int) -> dict:
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.put("/projects/{project_id}")
def update_project_detail(project_id: int, payload: ProjectPayload) -> dict:
    updated = update_project(
        project_id,
        title=payload.title,
        source_text=payload.source_text,
        annotated_text=payload.annotated_text,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="项目不存在")
    return get_project(project_id)


@router.delete("/projects/{project_id}")
def delete_project_detail(project_id: int) -> dict:
    if not delete_project(project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"deleted": True}
