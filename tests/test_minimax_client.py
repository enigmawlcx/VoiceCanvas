import httpx
import pytest
import respx

from app.db import get_connection
from app.services.minimax_client import (
    MiniMaxAuthError,
    MiniMaxClient,
    MiniMaxError,
    MiniMaxRateLimitError,
    MiniMaxTimeoutError,
    build_client,
)

BASE_URL = "https://fake.minimax.test"


@pytest.mark.asyncio
@respx.mock
async def test_request_json_returns_data_on_success(db):
    respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(
            200, json={"base_resp": {"status_code": 0, "status_msg": "success"}, "data": "ok"}
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    result = await client.request_json("POST", "/v1/fake", json={"a": 1})

    assert result["data"] == "ok"


@pytest.mark.asyncio
@respx.mock
async def test_request_json_records_usage_when_feature_given(db):
    respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(
            200,
            json={"base_resp": {"status_code": 0, "status_msg": "success"}, "usage_characters": 42},
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    await client.request_json("POST", "/v1/fake", json={"a": 1}, feature="synthesize", model="speech-2.8-hd")

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM usage_log ORDER BY id DESC LIMIT 1").fetchone()

    assert row["feature"] == "synthesize"
    assert row["model"] == "speech-2.8-hd"
    assert row["characters"] == 42
    assert row["status"] == "success"


@pytest.mark.asyncio
@respx.mock
async def test_request_json_records_cost_estimate_when_prices_configured(db, monkeypatch):
    from app.config import save_config
    from app.models import AppConfig

    save_config(AppConfig(price_per_1k_chars=1.5, price_per_1k_tokens=2.0))
    respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(
            200,
            json={
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "usage_characters": 1000,
                "usage": {"total_tokens": 2000},
            },
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    await client.request_json("POST", "/v1/fake", feature="synthesize", model="speech-2.8-hd")

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM usage_log ORDER BY id DESC LIMIT 1").fetchone()

    assert row["cost_estimate"] == pytest.approx(5.5)


@pytest.mark.asyncio
@respx.mock
async def test_request_json_does_not_record_usage_without_feature(db):
    respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(
            200,
            json={"base_resp": {"status_code": 0, "status_msg": "success"}, "usage_characters": 42},
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    await client.request_json("POST", "/v1/fake", json={"a": 1})

    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM usage_log").fetchone()["c"]

    assert count == 0


@pytest.mark.asyncio
@respx.mock
async def test_request_json_raises_auth_error_on_1004(db):
    respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(200, json={"base_resp": {"status_code": 1004, "status_msg": "鉴权失败"}})
    )
    client = MiniMaxClient(api_key="bad-key", base_url=BASE_URL)

    with pytest.raises(MiniMaxAuthError):
        await client.request_json("POST", "/v1/fake", feature="synthesize", model="speech-2.8-hd")

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM usage_log ORDER BY id DESC LIMIT 1").fetchone()

    assert row["feature"] == "synthesize"
    assert row["status"] == "failed"


@pytest.mark.asyncio
@respx.mock
async def test_request_json_raises_rate_limit_error_on_1002(db, monkeypatch):
    monkeypatch.setattr("app.services.minimax_client._RATE_LIMIT_RETRY_DELAYS", (0, 0))
    route = respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(200, json={"base_resp": {"status_code": 1002, "status_msg": "触发限流"}})
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    with pytest.raises(MiniMaxRateLimitError):
        await client.request_json("POST", "/v1/fake", feature="polish", model="abab-chat")

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM usage_log ORDER BY id DESC LIMIT 1").fetchone()

    assert row["feature"] == "polish"
    assert row["status"] == "failed"
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_request_json_retries_rate_limit_then_succeeds(db, monkeypatch):
    monkeypatch.setattr("app.services.minimax_client._RATE_LIMIT_RETRY_DELAYS", (0, 0))
    route = respx.post(f"{BASE_URL}/v1/fake").mock(
        side_effect=[
            httpx.Response(200, json={"base_resp": {"status_code": 1002, "status_msg": "触发限流"}}),
            httpx.Response(200, json={"base_resp": {"status_code": 1002, "status_msg": "触发限流"}}),
            httpx.Response(
                200,
                json={"base_resp": {"status_code": 0, "status_msg": "success"}, "data": "ok"},
            ),
        ]
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    result = await client.request_json("POST", "/v1/fake")

    assert result["data"] == "ok"
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_request_json_raises_timeout_error(db):
    respx.post(f"{BASE_URL}/v1/fake").mock(side_effect=httpx.TimeoutException("timeout"))
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    with pytest.raises(MiniMaxTimeoutError):
        await client.request_json("POST", "/v1/fake")


@pytest.mark.asyncio
@respx.mock
async def test_request_json_records_tokens_from_usage_field(db):
    respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(
            200,
            json={
                "base_resp": {"status_code": 0, "status_msg": "success"},
                "usage": {"total_tokens": 88},
            },
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    await client.request_json("POST", "/v1/fake", feature="polish", model="abab-chat")

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM usage_log ORDER BY id DESC LIMIT 1").fetchone()

    assert row["tokens"] == 88


@pytest.mark.asyncio
@respx.mock
async def test_request_json_raises_generic_error_with_status_code(db):
    respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(200, json={"base_resp": {"status_code": 2013, "status_msg": "参数错误"}})
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    with pytest.raises(MiniMaxError) as exc_info:
        await client.request_json("POST", "/v1/fake")

    assert exc_info.value.status_code == 2013


@pytest.mark.asyncio
@respx.mock
async def test_request_json_wraps_connection_error(db):
    respx.post(f"{BASE_URL}/v1/fake").mock(side_effect=httpx.ConnectError("connection refused"))
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    with pytest.raises(MiniMaxError):
        await client.request_json("POST", "/v1/fake")


@pytest.mark.asyncio
@respx.mock
async def test_request_json_appends_group_id_when_configured(db):
    route = respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(
            200, json={"base_resp": {"status_code": 0, "status_msg": "success"}, "data": "ok"}
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL, group_id="group-123")

    await client.request_json("POST", "/v1/fake")

    assert route.calls.last.request.url.params["GroupId"] == "group-123"


@pytest.mark.asyncio
@respx.mock
async def test_request_json_omits_group_id_when_not_configured(db):
    route = respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(
            200, json={"base_resp": {"status_code": 0, "status_msg": "success"}, "data": "ok"}
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    await client.request_json("POST", "/v1/fake")

    assert "GroupId" not in route.calls.last.request.url.params


@pytest.mark.asyncio
@respx.mock
async def test_upload_file_returns_file_id(db):
    respx.post(f"{BASE_URL}/v1/files/upload").mock(
        return_value=httpx.Response(
            200,
            json={
                "file": {"file_id": 123456, "bytes": 10, "filename": "a.mp3", "purpose": "voice_clone"},
                "base_resp": {"status_code": 0, "status_msg": "success"},
            },
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    file_id = await client.upload_file(purpose="voice_clone", filename="a.mp3", content=b"fake-audio")

    assert file_id == 123456


@pytest.mark.asyncio
@respx.mock
async def test_upload_file_raises_auth_error_on_1004(db):
    respx.post(f"{BASE_URL}/v1/files/upload").mock(
        return_value=httpx.Response(200, json={"base_resp": {"status_code": 1004, "status_msg": "鉴权失败"}})
    )
    client = MiniMaxClient(api_key="bad-key", base_url=BASE_URL)

    with pytest.raises(MiniMaxAuthError):
        await client.upload_file(purpose="voice_clone", filename="a.mp3", content=b"fake-audio")


def test_build_client_raises_when_no_api_key(isolated_app_dir, monkeypatch):
    monkeypatch.setattr("app.config.get_api_key", lambda: None)

    with pytest.raises(MiniMaxAuthError):
        build_client()


def test_build_client_uses_saved_config(isolated_app_dir, monkeypatch):
    from app.config import save_config
    from app.models import AppConfig

    monkeypatch.setattr("app.config.get_api_key", lambda: "sk-test")
    save_config(AppConfig(base_url="https://custom.minimax.example", group_id="group-9"))

    client = build_client()

    assert client._base_url == "https://custom.minimax.example"
    assert client._group_id == "group-9"


@pytest.mark.asyncio
@respx.mock
async def test_request_json_returns_data_even_if_usage_log_insert_fails(db, monkeypatch):
    respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(
            200, json={"base_resp": {"status_code": 0, "status_msg": "success"}, "data": "ok"}
        )
    )

    def broken_insert(**kwargs):
        raise RuntimeError("db is locked")

    monkeypatch.setattr("app.services.minimax_client.insert_usage_log", broken_insert)
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    result = await client.request_json("POST", "/v1/fake", feature="synthesize")

    assert result["data"] == "ok"
