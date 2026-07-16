from fastapi import APIRouter
from pydantic import BaseModel

from app.config import delete_api_key, get_api_key, load_config, save_config, set_api_key
from app.models import AppConfig
from app.services.minimax_client import MiniMaxClient, MiniMaxError

router = APIRouter(prefix="/api/settings", tags=["settings"])


def mask_api_key(api_key: str) -> str:
    if len(api_key) <= 4:
        return "*" * len(api_key)
    return f"{'*' * (len(api_key) - 4)}{api_key[-4:]}"


class ApiKeyPayload(BaseModel):
    api_key: str


class SettingsResponse(AppConfig):
    has_api_key: bool
    api_key_masked: str | None = None


class ApiKeyResponse(BaseModel):
    has_api_key: bool
    api_key_masked: str | None = None


class TestConnectionResponse(BaseModel):
    ok: bool
    message: str


def _settings_response() -> SettingsResponse:
    config = load_config()
    api_key = get_api_key()
    return SettingsResponse(
        **config.model_dump(),
        has_api_key=api_key is not None,
        api_key_masked=mask_api_key(api_key) if api_key else None,
    )


@router.get("", response_model=SettingsResponse)
def get_settings() -> SettingsResponse:
    return _settings_response()


@router.put("", response_model=SettingsResponse)
def update_settings(config: AppConfig) -> SettingsResponse:
    save_config(config)
    return _settings_response()


@router.put("/api-key", response_model=ApiKeyResponse)
def update_api_key(payload: ApiKeyPayload) -> ApiKeyResponse:
    set_api_key(payload.api_key)
    return ApiKeyResponse(has_api_key=True, api_key_masked=mask_api_key(payload.api_key))


@router.delete("/api-key", response_model=ApiKeyResponse)
def remove_api_key() -> ApiKeyResponse:
    delete_api_key()
    return ApiKeyResponse(has_api_key=False, api_key_masked=None)


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection() -> TestConnectionResponse:
    api_key = get_api_key()
    if not api_key:
        return TestConnectionResponse(ok=False, message="尚未配置 API Key，请先填写并保存")

    config = load_config()
    client = MiniMaxClient(api_key=api_key, base_url=config.base_url, group_id=config.group_id or None)
    try:
        await client.request_json("POST", "/v1/get_voice", json={"voice_type": "system"})
    except MiniMaxError as exc:
        return TestConnectionResponse(ok=False, message=str(exc))

    return TestConnectionResponse(ok=True, message="连接成功")
