from app.services.annotate import parse_annotated_text


def test_parses_multiple_segments_with_emotion_tags():
    text = "[calm] 大家好，欢迎回来。(emm) 今天聊个有意思的话题。\n[happy] 没想到吧！(laughs) 这真的太棒了。"

    segments = parse_annotated_text(text)

    assert segments == [
        {"text": "大家好，欢迎回来。(emm) 今天聊个有意思的话题。", "emotion": "calm"},
        {"text": "没想到吧！(laughs) 这真的太棒了。", "emotion": "happy"},
    ]


def test_skips_blank_lines():
    text = "[calm] 第一段\n\n\n[sad] 第二段"

    segments = parse_annotated_text(text)

    assert len(segments) == 2


def test_line_without_emotion_tag_has_none_emotion():
    text = "没有标签的普通文本"

    segments = parse_annotated_text(text)

    assert segments == [{"text": "没有标签的普通文本", "emotion": None}]


def test_unrecognized_bracket_tag_is_kept_as_plain_text():
    text = "[note] 这不是合法情绪标签"

    segments = parse_annotated_text(text)

    assert segments == [{"text": "[note] 这不是合法情绪标签", "emotion": None}]


def test_emotion_tag_is_case_insensitive():
    text = "[HAPPY] 大写标签"

    segments = parse_annotated_text(text)

    assert segments == [{"text": "大写标签", "emotion": "happy"}]


def test_skips_segment_that_becomes_empty_after_stripping_tag():
    text = "[calm]   \n[sad] 有效内容"

    segments = parse_annotated_text(text)

    assert segments == [{"text": "有效内容", "emotion": "sad"}]


def test_empty_input_returns_empty_list():
    assert parse_annotated_text("") == []
    assert parse_annotated_text("   \n  \n") == []
