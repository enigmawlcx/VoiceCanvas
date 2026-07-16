import re

from app.services.tags import VALID_EMOTIONS

_LEADING_TAG_PATTERN = re.compile(r"^\[(?P<tag>[a-zA-Z]+)\]\s*(?P<rest>.*)$")


def parse_annotated_text(annotated_text: str) -> list[dict]:
    """将标注文本解析为分段列表 [{text, emotion}]。

    格式约定：每个非空行是一个分段；行首 `[emotion]` 标签（须为合法情绪值）
    会被提取为该段的 emotion 并从文本中移除，未识别的方括号内容按普通文本处理。
    """
    segments: list[dict] = []
    for raw_line in annotated_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        emotion = None
        text = line
        match = _LEADING_TAG_PATTERN.match(line)
        if match and match.group("tag").lower() in VALID_EMOTIONS:
            emotion = match.group("tag").lower()
            text = match.group("rest").strip()

        if not text:
            continue

        segments.append({"text": text, "emotion": emotion})

    return segments
