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
