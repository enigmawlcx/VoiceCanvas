from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.db.voices_repo import delete_voice, get_voice, insert_voice, list_voices, update_note
from app.services.minimax_client import MiniMaxAuthError, MiniMaxError, build_client
from app.services.voices import clone_voice, design_voice, fetch_remote_voices

router = APIRouter(prefix="/api/voices", tags=["voices"])


class DesignRequest(BaseModel):
    prompt: str
    preview_text: str
    voice_id: str | None = None
    note: str | None = None


class NoteUpdateRequest(BaseModel):
    note: str


def _raise_http_error(exc: MiniMaxError) -> None:
    status_code = 400 if isinstance(exc, MiniMaxAuthError) else 502
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("")
async def get_voices() -> dict:
    try:
        client = build_client()
        remote = await fetch_remote_voices(client)
    except MiniMaxError as exc:
        _raise_http_error(exc)

    remote_cloned_ids = {item["voice_id"] for item in remote.get("voice_cloning", [])}
    remote_designed_ids = {item["voice_id"] for item in remote.get("voice_generation", [])}

    cloned = [
        {**voice, "activated": voice["voice_id"] in remote_cloned_ids}
        for voice in list_voices(type="cloned")
    ]
    designed = [
        {**voice, "activated": voice["voice_id"] in remote_designed_ids}
        for voice in list_voices(type="designed")
    ]

    return {
        "system": remote.get("system_voice", []),
        "cloned": cloned,
        "designed": designed,
    }


@router.post("/clone", status_code=201)
async def clone(
    voice_id: str = Form(...),
    note: str | None = Form(None),
    preview_text: str | None = Form(None),
    clone_prompt: str | None = Form(None),
    model: str | None = Form(None),
    file: UploadFile = File(...),
) -> dict:
    content = await file.read()
    try:
        client = build_client()
        result = await clone_voice(
            client,
            file_bytes=content,
            filename=file.filename or "clone.mp3",
            voice_id=voice_id,
            preview_text=preview_text,
            model=model,
            clone_prompt=clone_prompt,
        )
    except MiniMaxError as exc:
        _raise_http_error(exc)

    insert_voice(voice_id=voice_id, type="cloned", note=note, sample_path=result.get("demo_audio") or None)
    return {"voice_id": voice_id, "demo_audio": result.get("demo_audio") or None}


@router.post("/design", status_code=201)
async def design(payload: DesignRequest) -> dict:
    try:
        client = build_client()
        result = await design_voice(
            client, prompt=payload.prompt, preview_text=payload.preview_text, voice_id=payload.voice_id
        )
    except MiniMaxError as exc:
        _raise_http_error(exc)

    generated_voice_id = result.get("voice_id", payload.voice_id)
    insert_voice(voice_id=generated_voice_id, type="designed", note=payload.note)
    return {"voice_id": generated_voice_id, "trial_audio_hex": result.get("trial_audio")}


@router.patch("/{voice_id}")
def patch_note(voice_id: str, payload: NoteUpdateRequest) -> dict:
    if not get_voice(voice_id):
        raise HTTPException(status_code=404, detail="音色不存在")
    update_note(voice_id, payload.note)
    return get_voice(voice_id)


@router.delete("/{voice_id}")
def remove_voice(voice_id: str) -> dict:
    if not delete_voice(voice_id):
        raise HTTPException(status_code=404, detail="音色不存在")
    return {"deleted": True}
