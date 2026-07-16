import json

import httpx
import pytest
import respx

from app.db import get_connection
from app.services.minimax_client import MiniMaxClient
from app.services.polish import FALLBACK_NOTICE, RETRY_MESSAGE, polish_text

BASE_URL = "https://fake.minimax.test"
SOURCE_TEXT = "你好，世界。今天天气不错。"

VALID_CONTENT = json.dumps(
    {
        "segments": [
            {"text": "你好，世界。", "emotion": "happy"},
            {"text": "今天天气不错。(laughs)", "emotion": ""},
        ]
    },
    ensure_ascii=False,
)

# 把原文的句号改成感叹号，拼接后与原文不一致，应判定校验失败
INVALID_CONTENT = json.dumps(
    {"segments": [{"text": "你好，世界！今天天气不错。", "emotion": "happy"}]},
    ensure_ascii=False,
)


def _success_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "base_resp": {"status_code": 0, "status_msg": "success"},
            "choices": [{"message": {"role": "assistant", "content": content}}],
        },
    )


@pytest.mark.asyncio
@respx.mock
async def test_polish_text_succeeds_on_first_attempt_when_output_matches_source(db):
    respx.post(f"{BASE_URL}/v1/text/chatcompletion_v2").mock(return_value=_success_response(VALID_CONTENT))
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    result = await polish_text(client, source_text=SOURCE_TEXT)

    assert result["notice"] is None
    assert result["segments"] == [
        {"text": "你好，世界。", "emotion": "happy"},
        {"text": "今天天气不错。(laughs)", "emotion": None},
    ]
    assert result["annotated_text"] == "[happy] 你好，世界。\n今天天气不错。(laughs)"
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM usage_log WHERE feature='polish'").fetchall()
    assert len(rows) == 1


@pytest.mark.asyncio
@respx.mock
async def test_polish_text_retries_with_correction_message_and_succeeds(db):
    route = respx.post(f"{BASE_URL}/v1/text/chatcompletion_v2").mock(
        side_effect=[_success_response(INVALID_CONTENT), _success_response(VALID_CONTENT)]
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    result = await polish_text(client, source_text=SOURCE_TEXT)

    assert result["notice"] is None
    assert route.call_count == 2
    second_request_body = json.loads(route.calls[1].request.content)
    assert second_request_body["messages"][-1]["content"] == RETRY_MESSAGE


@pytest.mark.asyncio
@respx.mock
async def test_polish_text_falls_back_to_rule_based_segments_after_two_failures(db):
    route = respx.post(f"{BASE_URL}/v1/text/chatcompletion_v2").mock(
        side_effect=[_success_response("不是合法JSON"), _success_response(INVALID_CONTENT)]
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    result = await polish_text(client, source_text=SOURCE_TEXT)

    assert route.call_count == 2
    assert result["notice"] == FALLBACK_NOTICE
    assert result["segments"] == [
        {"text": "你好，世界。", "emotion": None},
        {"text": "今天天气不错。", "emotion": None},
    ]
    assert result["annotated_text"] == "你好，世界。\n今天天气不错。"


@pytest.mark.asyncio
@respx.mock
async def test_polish_text_fallback_merges_consecutive_punctuation_into_one_segment(db):
    respx.post(f"{BASE_URL}/v1/text/chatcompletion_v2").mock(
        side_effect=[_success_response("不是JSON"), _success_response("还不是JSON")]
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    result = await polish_text(client, source_text="你好！！？？世界")

    assert result["segments"] == [{"text": "你好！！？？", "emotion": None}, {"text": "世界", "emotion": None}]


@pytest.mark.asyncio
@respx.mock
async def test_polish_text_raises_when_no_choices_returned(db):
    respx.post(f"{BASE_URL}/v1/text/chatcompletion_v2").mock(
        return_value=httpx.Response(
            200, json={"base_resp": {"status_code": 0, "status_msg": "success"}, "choices": []}
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    with pytest.raises(ValueError):
        await polish_text(client, source_text="你好")
