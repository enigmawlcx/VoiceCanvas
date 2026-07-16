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
_SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[。！？…；\n])(?![。！？…；\n])")
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
