from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import load_config
from app.db.usage_repo import insert_usage_log

logger = logging.getLogger(__name__)

_RATE_LIMIT_RETRY_DELAYS = (1.0, 2.0)


class MiniMaxError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class MiniMaxAuthError(MiniMaxError):
    pass


class MiniMaxRateLimitError(MiniMaxError):
    pass


class MiniMaxTimeoutError(MiniMaxError):
    pass


def _raise_for_base_resp(base_resp: dict) -> None:
    status_code = base_resp.get("status_code", 0)
    status_msg = base_resp.get("status_msg", "MiniMax 接口错误")

    if status_code == 1004:
        raise MiniMaxAuthError(status_msg, status_code=status_code)
    if status_code == 1002:
        raise MiniMaxRateLimitError(status_msg, status_code=status_code)
    if status_code != 0:
        raise MiniMaxError(status_msg, status_code=status_code)


def _estimate_cost(characters: int | None, tokens: int | None) -> float | None:
    config = load_config()
    cost = 0.0
    has_price = False
    if characters and config.price_per_1k_chars > 0:
        cost += characters / 1000 * config.price_per_1k_chars
        has_price = True
    if tokens and config.price_per_1k_tokens > 0:
        cost += tokens / 1000 * config.price_per_1k_tokens
        has_price = True
    return round(cost, 6) if has_price else None


def _record_usage(
    *,
    feature: str,
    model: str | None,
    voice_id: str | None,
    data: dict | None,
    status: str,
) -> None:
    characters = data.get("usage_characters") if data else None
    tokens = (data.get("usage") or {}).get("total_tokens") if data else None
    try:
        insert_usage_log(
            feature=feature,
            model=model,
            characters=characters,
            tokens=tokens,
            voice_id=voice_id,
            cost_estimate=_estimate_cost(characters, tokens),
            status=status,
        )
    except Exception:
        logger.warning(
            "记账写入失败：feature=%s model=%s status=%s", feature, model, status, exc_info=True
        )


class MiniMaxClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.minimaxi.com",
        group_id: str | None = None,
        timeout: float = 30.0,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._group_id = group_id or None
        self._timeout = timeout

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        feature: str | None = None,
        model: str | None = None,
        voice_id: str | None = None,
    ) -> dict:
        last_rate_limit_error: MiniMaxRateLimitError | None = None
        for attempt in range(len(_RATE_LIMIT_RETRY_DELAYS) + 1):
            try:
                return await self._request_json_once(
                    method,
                    path,
                    json=json,
                    params=params,
                    feature=feature,
                    model=model,
                    voice_id=voice_id,
                )
            except MiniMaxRateLimitError as exc:
                last_rate_limit_error = exc
                if attempt >= len(_RATE_LIMIT_RETRY_DELAYS):
                    if feature is not None:
                        _record_usage(
                            feature=feature, model=model, voice_id=voice_id, data=None, status="failed"
                        )
                    raise
                await asyncio.sleep(_RATE_LIMIT_RETRY_DELAYS[attempt])
        raise last_rate_limit_error  # pragma: no cover

    async def _request_json_once(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        feature: str | None = None,
        model: str | None = None,
        voice_id: str | None = None,
    ) -> dict:
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        request_params = dict(params or {})
        if self._group_id:
            request_params.setdefault("GroupId", self._group_id)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method, url, headers=headers, json=json, params=request_params or None
                )
        except httpx.TimeoutException as exc:
            if feature is not None:
                _record_usage(feature=feature, model=model, voice_id=voice_id, data=None, status="failed")
            raise MiniMaxTimeoutError("请求超时") from exc
        except httpx.RequestError as exc:
            if feature is not None:
                _record_usage(feature=feature, model=model, voice_id=voice_id, data=None, status="failed")
            raise MiniMaxError(f"网络请求失败: {exc}") from exc

        data = response.json()
        try:
            _raise_for_base_resp(data.get("base_resp", {}))
        except MiniMaxError:
            if feature is not None:
                _record_usage(feature=feature, model=model, voice_id=voice_id, data=data, status="failed")
            raise

        if feature is not None:
            _record_usage(feature=feature, model=model, voice_id=voice_id, data=data, status="success")

        return data

    async def upload_file(
        self, *, purpose: str, filename: str, content: bytes, content_type: str = "application/octet-stream"
    ) -> int:
        url = f"{self._base_url}/v1/files/upload"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        params = {"GroupId": self._group_id} if self._group_id else None

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    params=params,
                    data={"purpose": purpose},
                    files={"file": (filename, content, content_type)},
                )
        except httpx.TimeoutException as exc:
            raise MiniMaxTimeoutError("请求超时") from exc
        except httpx.RequestError as exc:
            raise MiniMaxError(f"网络请求失败: {exc}") from exc

        data = response.json()
        _raise_for_base_resp(data.get("base_resp", {}))
        return data["file"]["file_id"]


def build_client() -> MiniMaxClient:
    from app.config import get_api_key, load_config

    api_key = get_api_key()
    if not api_key:
        raise MiniMaxAuthError("尚未配置 API Key，请先在配置页填写")
    config = load_config()
    return MiniMaxClient(api_key=api_key, base_url=config.base_url, group_id=config.group_id or None)
