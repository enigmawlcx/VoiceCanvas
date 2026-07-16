# 工作台（Studio）重构 Implementation Plan

> **状态说明（2026-07-10）：** 本计划已完成。正文中未勾选的逐步步骤保留为原始 TDD 执行模板，不表示当前仍未实施；完成状态以文末“完成标准”和提交历史为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把工作台从"原文/标注两栏文本框"重构为"单一大文本框 + 右侧情绪/语气词按钮面板"，润色改为只加标注不改原文（结构化输出+校验重试+规则兜底），新增自动保存草稿、清空工作台、标签常量接口，并把语音合成改为双声道输出。

**Architecture:** 后端新增 `app/services/tags.py` 作为情绪/语气词的唯一数据源，供 `annotate.py`（解析校验）、`polish.py`（提示词与合法性校验）、新接口 `GET /api/studio/tags`（前端按钮渲染）三处复用；`polish.py` 改为要求 LLM 返回结构化 JSON，本地校验"拼接后与原文一致"，不一致则追加纠错消息重试一次，仍失败则走本地规则兜底分段。前端 `studio.js` 用模块级变量保存草稿 id 与最新文本内容，实现"切页不丢、10 秒自动保存、应用重启后从后端恢复"。`projects` 表结构不变，工作台的"当前草稿"就是某一行 `source_text`/`annotated_text` 同时写入相同内容。

**Tech Stack:** 沿用现有栈（FastAPI、Pydantic 2、SQLite、httpx、pydub），无新增依赖；`polish.py` 重写仅使用标准库 `json`/`re`；测试沿用 pytest + pytest-asyncio + respx；前端为原生 JS + `fetch` + `localStorage`，无新增前端依赖。

---

## 前置说明

- 本次改动是同一子系统（工作台页面）内紧密耦合的一组变更（标签数据源 → 润色算法 → 接口 → 前端整页重写），不拆分为多个计划。
- 前端 JS/CSS 无自动化测试基建（现状如此，符合设计文档"测试计划"一节），对应任务用"写代码 → 静态内容断言脚本 → （可选）手动验证 → 提交"代替 TDD 红绿循环；最后一个任务是覆盖全部交互点的手动验证清单。
- 后端任务遵循严格 TDD：先写失败测试，再实现。

## File Structure

- Create: `app/services/tags.py` — 9 个情绪 + 19 个语气词的唯一数据源（`EMOTIONS`、`INTERJECTIONS`、`VALID_EMOTIONS`）
- Modify: `app/services/annotate.py` — `VALID_EMOTIONS` 改为从 `tags.py` 导入
- Modify: `app/services/synthesize.py` — `_build_t2a_payload` 的 `channel` 从 1 改为 2
- Modify: `app/services/polish.py` — 重写为"结构化 JSON 输出 + 校验 + 重试 + 规则兜底"
- Modify: `app/api/studio.py` — 新增 `GET /api/studio/tags`；`PolishResponse` 新增可选 `notice` 字段
- Modify: `web/css/style.css` — 移除旧的三栏样式，新增工作台方案 B（单文本框 + 右侧按钮面板）样式
- Modify: `web/js/pages/studio.js` — 整页重写：单文本框、标签按钮渲染与插入、自动保存、草稿恢复、清空工作台、音色分组重排
- Create: `tests/test_tags_service.py`
- Modify: `tests/test_annotate.py` — 无需改动内容，仅用于回归验证（`VALID_EMOTIONS` 取值不变）
- Modify: `tests/test_synthesize_service.py` — 新增断言 `channel == 2` 的用例
- Modify: `tests/test_polish_service.py` — 重写为新算法的 4 个场景
- Modify: `tests/test_studio_api.py` — 更新 `/polish` 用例为结构化 mock，新增 `/tags` 用例与兜底 `notice` 用例

---

### Task 1: 标签常量模块 `app/services/tags.py`

**Files:**
- Create: `app/services/tags.py`
- Test: `tests/test_tags_service.py`

- [ ] **Step 1: 写失败的测试**

```python
from app.services.tags import EMOTIONS, INTERJECTIONS, VALID_EMOTIONS


def test_emotions_contains_nine_fixed_values_with_chinese_labels():
    assert len(EMOTIONS) == 9
    assert {"id": "happy", "label": "开心"} in EMOTIONS
    assert {"id": "whisper", "label": "耳语"} in EMOTIONS


def test_interjections_contains_nineteen_fixed_values_with_chinese_labels():
    assert len(INTERJECTIONS) == 19
    assert {"id": "laughs", "label": "笑声"} in INTERJECTIONS
    assert {"id": "sneezes", "label": "喷嚏"} in INTERJECTIONS


def test_valid_emotions_matches_emotion_ids():
    assert VALID_EMOTIONS == {item["id"] for item in EMOTIONS}
```

保存为 `tests/test_tags_service.py`。

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_tags_service.py -v`
Expected: FAIL，报 `ModuleNotFoundError: No module named 'app.services.tags'`

- [ ] **Step 3: 实现 `tags.py`**

```python
EMOTIONS: list[dict[str, str]] = [
    {"id": "happy", "label": "开心"},
    {"id": "sad", "label": "悲伤"},
    {"id": "angry", "label": "生气"},
    {"id": "fearful", "label": "害怕"},
    {"id": "disgusted", "label": "厌恶"},
    {"id": "surprised", "label": "惊讶"},
    {"id": "calm", "label": "平静"},
    {"id": "fluent", "label": "流畅"},
    {"id": "whisper", "label": "耳语"},
]

INTERJECTIONS: list[dict[str, str]] = [
    {"id": "laughs", "label": "笑声"},
    {"id": "chuckle", "label": "轻笑"},
    {"id": "coughs", "label": "咳嗽"},
    {"id": "clear-throat", "label": "清嗓子"},
    {"id": "groans", "label": "呻吟"},
    {"id": "breath", "label": "换气"},
    {"id": "pant", "label": "喘气"},
    {"id": "inhale", "label": "吸气"},
    {"id": "exhale", "label": "呼气"},
    {"id": "gasps", "label": "倒吸气"},
    {"id": "sniffs", "label": "吸鼻子"},
    {"id": "sighs", "label": "叹气"},
    {"id": "snorts", "label": "喷鼻息"},
    {"id": "burps", "label": "打嗝"},
    {"id": "lip-smacking", "label": "咂嘴"},
    {"id": "humming", "label": "哼唱"},
    {"id": "hissing", "label": "嘶嘶声"},
    {"id": "emm", "label": "嗯"},
    {"id": "sneezes", "label": "喷嚏"},
]

VALID_EMOTIONS = {item["id"] for item in EMOTIONS}
```

保存为 `app/services/tags.py`。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_tags_service.py -v`
Expected: 3 项全部 PASS

- [ ] **Step 5: 提交**

```bash
git add app/services/tags.py tests/test_tags_service.py
git commit -m "feat: 新增情绪/语气词标签常量模块"
```

---

### Task 2: `annotate.py` 复用标签常量模块

**Files:**
- Modify: `app/services/annotate.py:1-13`

- [ ] **Step 1: 替换硬编码的 `VALID_EMOTIONS`**

将：

```python
import re

VALID_EMOTIONS = {
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgusted",
    "surprised",
    "calm",
    "fluent",
    "whisper",
}
```

替换为：

```python
import re

from app.services.tags import VALID_EMOTIONS
```

`app/services/annotate.py` 其余代码（`_LEADING_TAG_PATTERN`、`parse_annotated_text`）不变。

- [ ] **Step 2: 运行现有测试确认无回归**

Run: `pytest tests/test_annotate.py -v`
Expected: 全部 PASS（情绪取值未变，行为不变）

- [ ] **Step 3: 提交**

```bash
git add app/services/annotate.py
git commit -m "refactor: annotate.py 复用 tags.py 的情绪常量，避免重复维护"
```

---

### Task 3: 语音合成启用双声道输出

**Files:**
- Modify: `app/services/synthesize.py:45-51`
- Test: `tests/test_synthesize_service.py`

- [ ] **Step 1: 写失败的测试**

在 `tests/test_synthesize_service.py` 顶部导入区加入 `import json`，并新增以下测试函数（放在 `test_synthesize_segment_returns_decoded_audio_and_records_usage` 之后）：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_synthesize_service.py::test_synthesize_segment_requests_dual_channel_audio -v`
Expected: FAIL，`assert 1 == 2`

- [ ] **Step 3: 修改 `_build_t2a_payload`**

将 `app/services/synthesize.py` 中：

```python
        "audio_setting": {
            "sample_rate": sample_rate,
            "bitrate": 128000,
            "format": format,
            "channel": 1,
        },
```

改为：

```python
        "audio_setting": {
            "sample_rate": sample_rate,
            "bitrate": 128000,
            "format": format,
            "channel": 2,  # MiniMax API：1=单声道，2=双声道，固定启用双声道输出
        },
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_synthesize_service.py -v`
Expected: 全部 PASS（含新增用例）

- [ ] **Step 5: 提交**

```bash
git add app/services/synthesize.py tests/test_synthesize_service.py
git commit -m "feat: 语音合成启用双声道输出"
```

---

### Task 4: `polish.py` 改为结构化输出 + 校验 + 重试 + 规则兜底

**Files:**
- Modify: `app/services/polish.py`（整体重写）
- Modify: `tests/test_polish_service.py`（整体重写）

- [ ] **Step 1: 写失败的测试（整体替换 `tests/test_polish_service.py`）**

```python
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
async def test_polish_text_raises_when_no_choices_returned(db):
    respx.post(f"{BASE_URL}/v1/text/chatcompletion_v2").mock(
        return_value=httpx.Response(
            200, json={"base_resp": {"status_code": 0, "status_msg": "success"}, "choices": []}
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    with pytest.raises(ValueError):
        await polish_text(client, source_text="你好")
```

保存为 `tests/test_polish_service.py`（覆盖原文件）。

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_polish_service.py -v`
Expected: FAIL（`polish_text` 尚未支持新签名/返回值，`ImportError: cannot import name 'FALLBACK_NOTICE'` 等）

- [ ] **Step 3: 重写 `app/services/polish.py`**

```python
import json
import re

from app.services.minimax_client import MiniMaxClient
from app.services.tags import EMOTIONS, INTERJECTIONS

DEFAULT_POLISH_MODEL = "abab6.5s-chat"

FALLBACK_NOTICE = "AI 未能在保留原文前提下完成标注，已自动按标点分段，可手动点击情绪/语气词按钮补充"

_EMOTION_IDS = [item["id"] for item in EMOTIONS]
_INTERJECTION_IDS = [item["id"] for item in INTERJECTIONS]

_INTERJECTION_TAG_PATTERN = re.compile(
    r"\((?:" + "|".join(re.escape(tag_id) for tag_id in _INTERJECTION_IDS) + r")\)"
)
_WHITESPACE_PATTERN = re.compile(r"\s+")
_SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[。！？…；\n])")
_BLANK_LINE_PATTERN = re.compile(r"\n\s*\n")

SYSTEM_PROMPT = (
    "你是一名专业的中文有声书文本标注助手。请阅读原文，只做以下操作："
    "按语义分段、为每段标注情绪、在合适位置插入语气词标签；"
    "不允许增删改原文任何文字、标点或替换用词，也不允许复述或改写原文。\n\n"
    "请只返回如下 JSON 格式，不要输出任何解释、前后缀或 Markdown 代码块标记：\n"
    '{"segments": [{"text": "……", "emotion": "happy"}, {"text": "……", "emotion": ""}]}\n\n'
    "约束：\n"
    "1. 所有 segments 的 text 字段依次拼接后，必须与原文完全一致（可忽略两端空白），"
    "只能在其中插入语气词标签；\n"
    f"2. emotion 取值仅限：{'/'.join(_EMOTION_IDS)}，不标注则为空字符串 \"\"；\n"
    f"3. 语气词标签取值仅限：{'/'.join(_INTERJECTION_IDS)}，格式为英文小括号包裹，如 (laughs)。"
)

RETRY_MESSAGE = (
    "上次结果修改了原文文字，请重新处理，必须逐字保留原文所有文字与标点，"
    "只能分段、标注情绪、插入语气词标签"
)


def _normalize(text: str) -> str:
    return _WHITESPACE_PATTERN.sub("", text)


def _strip_interjection_tags(text: str) -> str:
    return _INTERJECTION_TAG_PATTERN.sub("", text)


def _parse_llm_segments(content: str) -> list[dict] | None:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None

    raw_segments = data.get("segments") if isinstance(data, dict) else None
    if not isinstance(raw_segments, list) or not raw_segments:
        return None

    segments: list[dict] = []
    for item in raw_segments:
        if not isinstance(item, dict):
            return None
        text = item.get("text")
        if not isinstance(text, str):
            return None
        emotion = item.get("emotion") or None
        if emotion is not None and emotion not in _EMOTION_IDS:
            return None
        segments.append({"text": text, "emotion": emotion})
    return segments


def _validate_segments(segments: list[dict], source_text: str) -> bool:
    joined = "".join(segment["text"] for segment in segments)
    joined = _strip_interjection_tags(joined)
    return _normalize(joined) == _normalize(source_text)


def _fallback_segments(source_text: str) -> list[dict]:
    segments: list[dict] = []
    for block in _BLANK_LINE_PATTERN.split(source_text):
        for part in _SENTENCE_BOUNDARY_PATTERN.split(block):
            text = part.strip()
            if text:
                segments.append({"text": text, "emotion": None})
    return segments


def _build_annotated_text(segments: list[dict]) -> str:
    lines = []
    for segment in segments:
        if segment.get("emotion"):
            lines.append(f"[{segment['emotion']}] {segment['text']}")
        else:
            lines.append(segment["text"])
    return "\n".join(lines)


async def _request_polish_completion(client: MiniMaxClient, *, model: str, messages: list[dict]) -> str:
    result = await client.request_json(
        "POST",
        "/v1/text/chatcompletion_v2",
        json={"model": model, "messages": messages},
        feature="polish",
        model=model,
    )
    choices = result.get("choices") or []
    if not choices:
        raise ValueError("润色接口未返回有效结果")
    return choices[0]["message"]["content"].strip()


async def polish_text(
    client: MiniMaxClient, *, source_text: str, model: str = DEFAULT_POLISH_MODEL
) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": source_text},
    ]

    for attempt in range(2):
        content = await _request_polish_completion(client, model=model, messages=messages)
        segments = _parse_llm_segments(content)
        if segments is not None and _validate_segments(segments, source_text):
            return {
                "annotated_text": _build_annotated_text(segments),
                "segments": segments,
                "notice": None,
            }
        if attempt == 0:
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": RETRY_MESSAGE})

    fallback = _fallback_segments(source_text)
    return {
        "annotated_text": _build_annotated_text(fallback),
        "segments": fallback,
        "notice": FALLBACK_NOTICE,
    }
```

保存为 `app/services/polish.py`（覆盖原文件）。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_polish_service.py -v`
Expected: 全部 PASS（4 项）

- [ ] **Step 5: 提交**

```bash
git add app/services/polish.py tests/test_polish_service.py
git commit -m "feat: 润色改为结构化输出+校验重试+规则兜底，保证不改动原文"
```

---

### Task 5: `app/api/studio.py` 新增标签接口 + 润色响应 `notice` 字段

**Files:**
- Modify: `app/api/studio.py`
- Modify: `tests/test_studio_api.py`

- [ ] **Step 1: 写失败/更新的测试**

在 `tests/test_studio_api.py` 顶部加入 `import json`，并将 `test_polish_endpoint_returns_annotated_text_and_segments` 替换为：

```python
def test_polish_endpoint_returns_annotated_text_and_segments(client):
    content = json.dumps({"segments": [{"text": "你好世界", "emotion": "calm"}]}, ensure_ascii=False)
    with respx.mock:
        respx.post("https://api.minimaxi.com/v1/text/chatcompletion_v2").mock(
            return_value=httpx.Response(
                200,
                json={
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                    "choices": [{"message": {"role": "assistant", "content": content}}],
                },
            )
        )
        response = client.post("/api/studio/polish", json={"source_text": "你好世界"})

    assert response.status_code == 200
    body = response.json()
    assert body["annotated_text"] == "[calm] 你好世界"
    assert body["segments"] == [{"text": "你好世界", "emotion": "calm"}]
    assert body["notice"] is None
```

并在其后新增两个测试函数：

```python
def test_polish_endpoint_includes_notice_when_llm_cannot_preserve_source_text(client):
    with respx.mock:
        respx.post("https://api.minimaxi.com/v1/text/chatcompletion_v2").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "base_resp": {"status_code": 0, "status_msg": "success"},
                        "choices": [{"message": {"role": "assistant", "content": "不是JSON"}}],
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "base_resp": {"status_code": 0, "status_msg": "success"},
                        "choices": [{"message": {"role": "assistant", "content": "还是不是JSON"}}],
                    },
                ),
            ]
        )
        response = client.post("/api/studio/polish", json={"source_text": "你好，世界。"})

    assert response.status_code == 200
    body = response.json()
    assert body["notice"] == "AI 未能在保留原文前提下完成标注，已自动按标点分段，可手动点击情绪/语气词按钮补充"
    assert body["segments"] == [{"text": "你好，世界。", "emotion": None}]


def test_get_tags_endpoint_returns_fixed_emotion_and_interjection_lists(client):
    response = client.get("/api/studio/tags")

    assert response.status_code == 200
    body = response.json()
    assert len(body["emotions"]) == 9
    assert len(body["interjections"]) == 19
    assert {"id": "happy", "label": "开心"} in body["emotions"]
    assert {"id": "laughs", "label": "笑声"} in body["interjections"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_studio_api.py -v`
Expected: `test_polish_endpoint_returns_annotated_text_and_segments` 的 `notice` 断言失败（字段不存在），`test_get_tags_endpoint_returns_fixed_emotion_and_interjection_lists` 报 404

- [ ] **Step 3: 修改 `app/api/studio.py`**

将顶部导入：

```python
from app.services.annotate import parse_annotated_text
from app.services.minimax_client import MiniMaxAuthError, MiniMaxError, build_client
from app.services.polish import polish_text
from app.services.synthesize import synthesize_full, synthesize_segment
```

改为：

```python
from app.services.annotate import parse_annotated_text
from app.services.minimax_client import MiniMaxAuthError, MiniMaxError, build_client
from app.services.polish import polish_text
from app.services.synthesize import synthesize_full, synthesize_segment
from app.services.tags import EMOTIONS, INTERJECTIONS
```

将：

```python
class PolishResponse(BaseModel):
    annotated_text: str
    segments: list[dict]
```

改为：

```python
class PolishResponse(BaseModel):
    annotated_text: str
    segments: list[dict]
    notice: str | None = None


class TagsResponse(BaseModel):
    emotions: list[dict]
    interjections: list[dict]
```

将：

```python
@router.post("/polish", response_model=PolishResponse)
async def polish(payload: PolishRequest) -> PolishResponse:
    try:
        client = build_client()
        annotated_text = await polish_text(client, source_text=payload.source_text)
    except MiniMaxError as exc:
        _raise_http_error(exc)

    return PolishResponse(annotated_text=annotated_text, segments=parse_annotated_text(annotated_text))
```

改为：

```python
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
```

（`parse_annotated_text` 仍被 `/annotate/parse` 端点使用，保留其导入。）

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_studio_api.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 运行完整测试套件确认无回归**

Run: `pytest -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add app/api/studio.py tests/test_studio_api.py
git commit -m "feat: 新增 /api/studio/tags 接口，润色响应新增 notice 字段"
```

---

### Task 6: 工作台方案 B 布局样式

**Files:**
- Modify: `web/css/style.css`

- [ ] **Step 1: 移除旧的三栏布局样式**

删除 `web/css/style.css` 中的：

```css
.studio-columns {
  display: flex;
  gap: 16px;
  align-items: stretch;
}

.studio-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
```

- [ ] **Step 2: 新增方案 B 布局样式**

在删除处（或文件末尾 `#pagination-row` 规则之后）新增：

```css
.studio-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.studio-main {
  display: flex;
  gap: 16px;
  align-items: stretch;
  margin-bottom: 16px;
}

.studio-editor-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.studio-big-textarea {
  min-height: 480px;
}

.studio-tag-panel {
  width: 260px;
  flex-shrink: 0;
  max-height: 560px;
  overflow-y: auto;
}

.tag-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-bottom: 16px;
}

.tag-btn {
  padding: 10px 6px;
  border-radius: 8px;
  border: 1px solid #d2d2d7;
  background: #f5f5f7;
  color: #1d1d1f;
  font-size: 13px;
  cursor: pointer;
  text-align: center;
}

.tag-btn:hover {
  background: #e5e5ea;
}

.tag-btn-emotion {
  border-color: #0071e3;
  color: #0071e3;
}
```

- [ ] **Step 3: 静态内容校验**

Run:
```bash
python3 -c "
css = open('web/css/style.css').read()
assert '.studio-columns' not in css
assert '.studio-toolbar' in css
assert '.studio-tag-panel' in css
assert '.tag-grid' in css
print('css ok')
"
```
Expected: 打印 `css ok`

- [ ] **Step 4: 提交**

```bash
git add web/css/style.css
git commit -m "feat: 新增工作台方案 B 布局样式"
```

---

### Task 7: 工作台前端整页重写

**Files:**
- Modify: `web/js/pages/studio.js`（整体重写）

- [ ] **Step 1: 整体替换 `web/js/pages/studio.js`**

```javascript
const STUDIO_DRAFT_ID_KEY = "voicemax.studio.draftId";
const STUDIO_AUTOSAVE_DELAY_MS = 10000;

let studioDraftId = null;
let studioMemoryText = null;
let studioAutosaveTimer = null;
let studioDirty = false;

function studioHexToBlobUrl(hex, mimeType = "audio/mpeg") {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  return URL.createObjectURL(new Blob([bytes], { type: mimeType }));
}

function studioEscapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

async function fetchVoiceGroups() {
  const response = await fetch("/api/voices");
  if (!response.ok) return { system: [], cloned: [], designed: [] };
  return response.json();
}

function buildVoiceOptionsHtml(voiceData) {
  const groups = [
    { label: "我的克隆音色", items: voiceData.cloned || [], nameKey: "voice_id" },
    { label: "我的设计音色", items: voiceData.designed || [], nameKey: "voice_id" },
    { label: "系统音色", items: voiceData.system || [], nameKey: "voice_name" },
  ];
  const groupsHtml = groups
    .filter((g) => g.items.length)
    .map(
      (g) => `<optgroup label="${g.label}">${g.items
        .map(
          (item) =>
            `<option value="${studioEscapeHtml(item.voice_id)}">${studioEscapeHtml(
              item[g.nameKey] || item.voice_id
            )}</option>`
        )
        .join("")}</optgroup>`
    )
    .join("");
  if (!groupsHtml) return '<option value="">暂无可用音色，请先在音色库添加</option>';
  return `<option value="">请选择音色</option>${groupsHtml}`;
}

async function fetchStudioTags() {
  const response = await fetch("/api/studio/tags");
  if (!response.ok) return { emotions: [], interjections: [] };
  return response.json();
}

function buildTagButtonsHtml(tags, className) {
  return tags
    .map(
      (tag) =>
        `<button type="button" class="${className}" data-id="${studioEscapeHtml(tag.id)}">${studioEscapeHtml(
          tag.label
        )}</button>`
    )
    .join("");
}

function insertEmotionTag(textarea, emotionId, validEmotionIds) {
  const value = textarea.value;
  const cursor = textarea.selectionStart;
  const lineStart = value.lastIndexOf("\n", cursor - 1) + 1;
  const nextBreak = value.indexOf("\n", cursor);
  const lineEnd = nextBreak === -1 ? value.length : nextBreak;
  const line = value.slice(lineStart, lineEnd);

  const match = line.match(/^\[([a-zA-Z-]+)\]\s*/);
  const hasValidTag = Boolean(match && validEmotionIds.includes(match[1].toLowerCase()));
  const rest = hasValidTag ? line.slice(match[0].length) : line;
  const newLine = `[${emotionId}] ${rest}`;

  textarea.value = value.slice(0, lineStart) + newLine + value.slice(lineEnd);

  const cursorOffsetInLine = cursor - lineStart;
  const oldPrefixLength = hasValidTag ? match[0].length : 0;
  const newPrefixLength = `[${emotionId}] `.length;
  const newCursorOffset = Math.max(0, cursorOffsetInLine - oldPrefixLength) + newPrefixLength;
  const newCursor = lineStart + newCursorOffset;

  textarea.selectionStart = textarea.selectionEnd = newCursor;
  textarea.focus();
  textarea.dispatchEvent(new Event("input"));
}

function insertInterjectionTag(textarea, tagId) {
  const value = textarea.value;
  const cursor = textarea.selectionStart;
  const before = value.slice(0, cursor);
  const after = value.slice(cursor);
  const needSpaceBefore = before.length > 0 && !/\s$/.test(before);
  const needSpaceAfter = after.length > 0 && !/^\s/.test(after);
  const insertion = `${needSpaceBefore ? " " : ""}(${tagId})${needSpaceAfter ? " " : ""}`;

  textarea.value = before + insertion + after;
  const newCursor = cursor + insertion.length;
  textarea.selectionStart = textarea.selectionEnd = newCursor;
  textarea.focus();
  textarea.dispatchEvent(new Event("input"));
}

async function restoreStudioContent() {
  if (studioMemoryText !== null) {
    return { text: studioMemoryText, draftId: studioDraftId };
  }
  const storedId = localStorage.getItem(STUDIO_DRAFT_ID_KEY);
  if (!storedId) {
    return { text: "", draftId: null };
  }
  const response = await fetch(`/api/studio/projects/${storedId}`);
  if (!response.ok) {
    localStorage.removeItem(STUDIO_DRAFT_ID_KEY);
    return { text: "", draftId: null };
  }
  const project = await response.json();
  return { text: project.annotated_text || project.source_text || "", draftId: project.id };
}

async function saveStudioDraft(text) {
  if (studioDraftId) {
    await fetch(`/api/studio/projects/${studioDraftId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_text: text, annotated_text: text }),
    });
    return;
  }
  const response = await fetch("/api/studio/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: text.trim().slice(0, 20) || "未命名项目",
      source_text: text,
      annotated_text: text,
    }),
  });
  if (response.ok) {
    const project = await response.json();
    studioDraftId = project.id;
    localStorage.setItem(STUDIO_DRAFT_ID_KEY, String(project.id));
  }
}

async function loadStudioPage(container) {
  container.innerHTML = `
    <div class="page studio-page">
      <h1>工作台</h1>

      <div class="studio-toolbar">
        <button id="polish-btn">润色</button>
        <button id="parse-btn" class="secondary">解析分段</button>
        <button id="save-project-btn" class="secondary">保存草稿</button>
        <button id="clear-workspace-btn" class="secondary">清空工作台</button>
        <span id="polish-result"></span>
      </div>

      <div class="studio-main">
        <section class="card studio-editor-col">
          <textarea id="studio-text" class="editor-textarea studio-big-textarea" placeholder="粘贴或输入原文..." autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"></textarea>
        </section>

        <aside class="card studio-tag-panel">
          <h2>情绪</h2>
          <div id="emotion-buttons" class="tag-grid"></div>
          <h2>语气词</h2>
          <div id="interjection-buttons" class="tag-grid"></div>
        </aside>
      </div>

      <section class="card">
        <h2>合成设置</h2>
        <div class="field-row">
          <label>音色</label>
          <select id="voice-select"><option>加载中...</option></select>
        </div>
        <div class="field-row">
          <label>语速 <span id="speed-value">1.0</span></label>
          <input type="range" id="speed" min="0.5" max="2" step="0.05" value="1" />
        </div>
        <div class="field-row">
          <label>音量 <span id="vol-value">1.0</span></label>
          <input type="range" id="vol" min="0.1" max="10" step="0.1" value="1" />
        </div>
        <div class="field-row">
          <label>Pitch <span id="pitch-value">0</span></label>
          <input type="range" id="pitch" min="-12" max="12" step="1" value="0" />
        </div>
        <h2>音效器（可选）</h2>
        <div class="field-row">
          <label>音高 <span id="vm-pitch-value">0</span></label>
          <input type="range" id="vm-pitch" min="-100" max="100" step="1" value="0" />
        </div>
        <div class="field-row">
          <label>强度 <span id="vm-intensity-value">0</span></label>
          <input type="range" id="vm-intensity" min="-100" max="100" step="1" value="0" />
        </div>
        <div class="field-row">
          <label>音色 <span id="vm-timbre-value">0</span></label>
          <input type="range" id="vm-timbre" min="-100" max="100" step="1" value="0" />
        </div>
      </section>

      <section class="card">
        <div class="field-row">
          <h2 style="flex:1;">分段列表</h2>
          <button id="synthesize-full-btn">整篇合成并导出</button>
          <span id="synthesize-full-result"></span>
        </div>
        <div id="segment-list"><p class="hint">点击"解析分段"后，分段将显示在此处</p></div>
      </section>
    </div>
  `;

  const els = {
    text: container.querySelector("#studio-text"),
    voiceSelect: container.querySelector("#voice-select"),
    speed: container.querySelector("#speed"),
    vol: container.querySelector("#vol"),
    pitch: container.querySelector("#pitch"),
    vmPitch: container.querySelector("#vm-pitch"),
    vmIntensity: container.querySelector("#vm-intensity"),
    vmTimbre: container.querySelector("#vm-timbre"),
    segmentList: container.querySelector("#segment-list"),
    emotionButtons: container.querySelector("#emotion-buttons"),
    interjectionButtons: container.querySelector("#interjection-buttons"),
    polishResult: container.querySelector("#polish-result"),
  };

  const SLIDER_BINDINGS = [
    ["speed", "speed-value"],
    ["vol", "vol-value"],
    ["pitch", "pitch-value"],
    ["vm-pitch", "vm-pitch-value"],
    ["vm-intensity", "vm-intensity-value"],
    ["vm-timbre", "vm-timbre-value"],
  ];

  SLIDER_BINDINGS.forEach(([inputId, labelId]) => {
    const input = container.querySelector(`#${inputId}`);
    const label = container.querySelector(`#${labelId}`);
    input.addEventListener("input", () => (label.textContent = input.value));
  });

  function resetSlidersToDefault() {
    els.speed.value = "1";
    els.vol.value = "1";
    els.pitch.value = "0";
    els.vmPitch.value = "0";
    els.vmIntensity.value = "0";
    els.vmTimbre.value = "0";
    SLIDER_BINDINGS.forEach(([inputId, labelId]) => {
      container.querySelector(`#${labelId}`).textContent = container.querySelector(`#${inputId}`).value;
    });
  }

  const voiceData = await fetchVoiceGroups();
  els.voiceSelect.innerHTML = buildVoiceOptionsHtml(voiceData);

  const tags = await fetchStudioTags();
  const validEmotionIds = tags.emotions.map((tag) => tag.id);
  els.emotionButtons.innerHTML = buildTagButtonsHtml(tags.emotions, "tag-btn tag-btn-emotion");
  els.interjectionButtons.innerHTML = buildTagButtonsHtml(tags.interjections, "tag-btn tag-btn-interjection");

  els.emotionButtons.querySelectorAll(".tag-btn-emotion").forEach((btn) => {
    btn.addEventListener("click", () => insertEmotionTag(els.text, btn.dataset.id, validEmotionIds));
  });
  els.interjectionButtons.querySelectorAll(".tag-btn-interjection").forEach((btn) => {
    btn.addEventListener("click", () => insertInterjectionTag(els.text, btn.dataset.id));
  });

  const restored = await restoreStudioContent();
  studioDraftId = restored.draftId;
  studioMemoryText = restored.text;
  els.text.value = restored.text;

  function scheduleAutosave() {
    studioDirty = true;
    clearTimeout(studioAutosaveTimer);
    studioAutosaveTimer = setTimeout(async () => {
      if (!studioDirty) return;
      await saveStudioDraft(studioMemoryText);
      studioDirty = false;
    }, STUDIO_AUTOSAVE_DELAY_MS);
  }

  els.text.addEventListener("input", () => {
    studioMemoryText = els.text.value;
    scheduleAutosave();
  });

  function currentSynthesisParams() {
    const vmPitch = Number(els.vmPitch.value);
    const vmIntensity = Number(els.vmIntensity.value);
    const vmTimbre = Number(els.vmTimbre.value);
    const voiceModify =
      vmPitch || vmIntensity || vmTimbre ? { pitch: vmPitch, intensity: vmIntensity, timbre: vmTimbre } : null;
    return {
      voice_id: els.voiceSelect.value,
      speed: Number(els.speed.value),
      vol: Number(els.vol.value),
      pitch: Number(els.pitch.value),
      voice_modify: voiceModify,
    };
  }

  function renderSegments(segments) {
    if (!segments.length) {
      els.segmentList.innerHTML = '<p class="hint">没有解析到分段</p>';
      els.segmentList._segments = [];
      return;
    }
    els.segmentList.innerHTML = `<div class="segment-list">${segments
      .map(
        (seg, index) => `
        <div class="segment-item" data-index="${index}">
          <span class="segment-emotion">${seg.emotion ? `[${studioEscapeHtml(seg.emotion)}]` : ""}</span>
          <span class="segment-text">${studioEscapeHtml(seg.text)}</span>
          <button class="segment-play secondary">试听</button>
          <audio class="segment-audio" controls style="display:none;"></audio>
        </div>`
      )
      .join("")}</div>`;

    els.segmentList.querySelectorAll(".segment-play").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const item = btn.closest(".segment-item");
        const index = Number(item.dataset.index);
        const segment = segments[index];
        const params = currentSynthesisParams();
        if (!params.voice_id) {
          alert("请先选择音色");
          return;
        }
        btn.textContent = "合成中...";
        btn.disabled = true;
        try {
          const response = await fetch("/api/studio/synthesize/segment", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              text: segment.text,
              emotion: segment.emotion,
              ...params,
            }),
          });
          const body = await response.json();
          if (!response.ok) throw new Error(body.detail || "合成失败");
          const audioEl = item.querySelector(".segment-audio");
          audioEl.src = studioHexToBlobUrl(body.audio_hex);
          audioEl.style.display = "block";
          audioEl.play();
        } catch (error) {
          alert(error.message);
        } finally {
          btn.textContent = "试听";
          btn.disabled = false;
        }
      });
    });

    els.segmentList._segments = segments;
  }

  async function parseAnnotatedText() {
    const response = await fetch("/api/studio/annotate/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ annotated_text: els.text.value }),
    });
    const segments = await response.json();
    renderSegments(segments);
    return segments;
  }

  container.querySelector("#parse-btn").addEventListener("click", parseAnnotatedText);

  container.querySelector("#polish-btn").addEventListener("click", async () => {
    if (!els.text.value.trim()) return;
    els.polishResult.textContent = "润色中...";
    els.polishResult.className = "";
    try {
      const response = await fetch("/api/studio/polish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_text: els.text.value }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "润色失败");
      els.text.value = body.annotated_text;
      studioMemoryText = body.annotated_text;
      scheduleAutosave();
      if (body.notice) {
        els.polishResult.textContent = body.notice;
        els.polishResult.className = "error";
      } else {
        els.polishResult.textContent = "润色完成";
        els.polishResult.className = "ok";
      }
    } catch (error) {
      els.polishResult.textContent = error.message;
      els.polishResult.className = "error";
    }
  });

  container.querySelector("#save-project-btn").addEventListener("click", async () => {
    clearTimeout(studioAutosaveTimer);
    await saveStudioDraft(els.text.value);
    studioDirty = false;
    els.polishResult.textContent = "草稿已保存";
    els.polishResult.className = "ok";
  });

  container.querySelector("#clear-workspace-btn").addEventListener("click", async () => {
    clearTimeout(studioAutosaveTimer);
    if (studioDraftId) {
      await fetch(`/api/studio/projects/${studioDraftId}`, { method: "DELETE" });
    }
    studioDraftId = null;
    studioMemoryText = "";
    studioDirty = false;
    localStorage.removeItem(STUDIO_DRAFT_ID_KEY);

    els.text.value = "";
    resetSlidersToDefault();
    els.voiceSelect.value = "";
    els.segmentList.innerHTML = '<p class="hint">点击"解析分段"后，分段将显示在此处</p>';
    els.segmentList._segments = undefined;
    els.polishResult.textContent = "";
    els.polishResult.className = "";
  });

  container.querySelector("#synthesize-full-btn").addEventListener("click", async () => {
    const resultEl = container.querySelector("#synthesize-full-result");
    const segments = els.segmentList._segments || (await parseAnnotatedText());
    if (!segments.length) {
      resultEl.textContent = "没有可合成的分段";
      resultEl.className = "error";
      return;
    }
    const params = currentSynthesisParams();
    if (!params.voice_id) {
      resultEl.textContent = "请先选择音色";
      resultEl.className = "error";
      return;
    }
    resultEl.textContent = "合成中，请稍候...";
    resultEl.className = "";
    try {
      const response = await fetch("/api/studio/synthesize/full", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ segments, ...params }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "合成失败");
      resultEl.textContent = `已导出：${body.file_path}`;
      resultEl.className = "ok";
    } catch (error) {
      resultEl.textContent = error.message;
      resultEl.className = "error";
    }
  });
}

window.VoiceMaxPages = window.VoiceMaxPages || {};
window.VoiceMaxPages.studio = loadStudioPage;
```

保存为 `web/js/pages/studio.js`（覆盖原文件）。

- [ ] **Step 2: 静态内容校验**

Run:
```bash
python3 -c "
js = open('web/js/pages/studio.js').read()
for marker in [
    'STUDIO_DRAFT_ID_KEY',
    'studioMemoryText',
    'insertEmotionTag',
    'insertInterjectionTag',
    'restoreStudioContent',
    'saveStudioDraft',
    'clear-workspace-btn',
    '我的克隆音色',
    '我的设计音色',
    '系统音色',
]:
    assert marker in js, f'missing {marker}'
assert js.index('我的克隆音色') < js.index('我的设计音色') < js.index('系统音色')
print('studio.js ok')
"
```
Expected: 打印 `studio.js ok`

- [ ] **Step 3: 运行后端测试确认无回归（静态文件改动不影响后端，但确保仓库整体可测）**

Run: `pytest -v`
Expected: 全部 PASS

- [ ] **Step 4: 提交**

```bash
git add web/js/pages/studio.js
git commit -m "feat: 工作台重构为单文本框+情绪语气词按钮面板，支持自动保存与清空"
```

---

### Task 8: 端到端人工验证

**Files:**
- 无代码改动，仅验证 Task 1-7 的整体效果

- [ ] **Step 1: 启动应用**

Run: `python3 -m app.main`
Expected: 弹出 VoiceMax 窗口，左侧导航可见"工作台"

- [ ] **Step 2: 验证初始空状态与按钮面板**

点击"工作台"导航项。

Expected:
- 文本框为空，右侧显示"情绪"9 个按钮、"语气词"19 个按钮（可滚动）
- 合成设置区所有滑块为默认值（语速 1.0、音量 1.0、Pitch 0、音效器三项 0）
- 音色下拉默认显示"请选择音色"，分组顺序为：我的克隆音色 → 我的设计音色 → 系统音色
- 分段列表显示提示文案"点击"解析分段"后，分段将显示在此处"

- [ ] **Step 3: 验证情绪/语气词按钮插入逻辑**

在文本框输入一行文字，光标停在行中间，点击任意情绪按钮。

Expected: 该按钮对应的 `[emotion]` 标签出现在行首，光标位置相对原内容保持不变；再点击另一个情绪按钮，行首标签被替换而不是重复插入。

将光标移到文字中间，点击任意语气词按钮。

Expected: `(标签)` 插入到光标处，若左右是非空白字符会自动补空格，不会与文字粘连。

- [ ] **Step 4: 验证润色（需已配置有效 API Key）**

输入一段中文文本，点击"润色"。

Expected: 文本框内容被替换为带 `[emotion]`/语气词标签的版本，原文文字与标点未被增删改；若触发规则兜底，`#polish-result` 区域会显示警示提示文案。

- [ ] **Step 5: 验证解析分段与合成**

点击"解析分段"，检查分段列表按行正确切分；选择一个音色后点击某分段"试听"，确认能听到双声道音频（可用耳机/系统音量均衡器确认左右声道均有声音，或用音频工具查看导出文件声道数）。

- [ ] **Step 6: 验证自动保存与跨页保留**

输入内容后等待 10 秒不做操作，观察网络请求（或 `~/Library/Application Support/VoiceMax/voicemax.db` 中 `projects` 表）确认已写入草稿；切换到"音色库"页面再切回"工作台"，确认文本框内容保持不变（应从内存瞬时恢复，无明显加载延迟）。

- [ ] **Step 7: 验证应用重启后的恢复**

完全退出应用（关闭窗口进程）后重新执行 `python3 -m app.main`，进入工作台。

Expected: 文本框自动加载上次保存的草稿内容（通过 `localStorage` 中的草稿 id 从后端拉取）。

- [ ] **Step 8: 验证清空工作台**

点击"清空工作台"。

Expected: 文本框清空，所有滑块恢复默认值，音色下拉恢复"请选择音色"，分段列表恢复初始提示；重启应用后进入工作台仍为空（草稿记录已被删除）。

- [ ] **Step 9: 记录验证结果**

如全部通过，本计划完成；如发现问题，返回对应 Task 修复后重新执行本任务的相关步骤。

**人工验证记录（2026-07-10）：** 开发阶段曾对 Step 1–3、5–8 进行人工验证；本次归档没有重新复测 Step 4（润色，需有效 API Key）及 Step 6–7（自动保存/重启恢复，需完整应用会话）。功能代码与自动化测试已合入，但不以开发阶段结论冒充本次 Step 6–7 的完整应用会话复测。

---

## 完成标准

- [x] `pytest -v` 全部通过（含 Task 1、3、4、5 新增/修改的测试用例）
- [x] `GET /api/studio/tags` 返回固定的 9 情绪 + 19 语气词
- [x] `POST /api/studio/polish` 不会增删改原文文字，兜底场景下返回 `notice`
- [x] 语音合成请求 payload 中 `audio_setting.channel == 2`
- [x] 工作台页面为单文本框 + 右侧按钮面板布局，支持自动保存、跨页/重启保留内容、清空工作台
- [x] 音色下拉分组顺序为：我的克隆音色 → 我的设计音色 → 系统音色
