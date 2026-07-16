from app.db.usage_repo import insert_usage_log
from app.services.minimax_client import MiniMaxClient

DEFAULT_PREVIEW_MODEL = "speech-2.8-hd"


async def fetch_remote_voices(client: MiniMaxClient) -> dict:
    return await client.request_json("POST", "/v1/get_voice", json={"voice_type": "all"})


async def clone_voice(
    client: MiniMaxClient,
    *,
    file_bytes: bytes,
    filename: str,
    voice_id: str,
    preview_text: str | None = None,
    model: str | None = None,
    clone_prompt: str | None = None,
) -> dict:
    file_id = await client.upload_file(purpose="voice_clone", filename=filename, content=file_bytes)

    payload: dict = {"file_id": file_id, "voice_id": voice_id}
    preview_model = model or DEFAULT_PREVIEW_MODEL
    if preview_text:
        payload["text"] = preview_text
        payload["model"] = preview_model
    if clone_prompt:
        payload["clone_prompt"] = {"prompt_text": clone_prompt}

    # 克隆响应的计费字段嵌套在 extra_info.usage_characters 而非顶层 usage_characters，
    # 因此不复用 request_json 的自动记账（feature=None），改为在此手动记账。
    result = await client.request_json("POST", "/v1/voice_clone", json=payload)

    characters = None
    if preview_text:
        characters = (result.get("extra_info") or {}).get("usage_characters")
    insert_usage_log(
        feature="clone",
        model=preview_model if preview_text else None,
        characters=characters,
        voice_id=voice_id,
        status="success",
    )
    return result


async def design_voice(
    client: MiniMaxClient,
    *,
    prompt: str,
    preview_text: str,
    voice_id: str | None = None,
) -> dict:
    payload: dict = {"prompt": prompt, "preview_text": preview_text}
    if voice_id:
        payload["voice_id"] = voice_id

    # T2VResp 未提供顶层 usage_characters 字段，按预览文本长度本地估算计费字符数。
    result = await client.request_json("POST", "/v1/voice_design", json=payload)

    insert_usage_log(
        feature="design",
        characters=len(preview_text),
        voice_id=result.get("voice_id", voice_id),
        status="success",
    )
    return result
