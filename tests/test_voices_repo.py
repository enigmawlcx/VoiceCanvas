from app.db.voices_repo import delete_voice, get_voice, insert_voice, list_voices, update_note


def test_insert_and_list_voices(db):
    insert_voice(voice_id="voice-1", type="cloned", note="测试克隆")

    voices = list_voices()

    assert len(voices) == 1
    assert voices[0]["voice_id"] == "voice-1"
    assert voices[0]["note"] == "测试克隆"


def test_list_voices_filters_by_type(db):
    insert_voice(voice_id="voice-1", type="cloned")
    insert_voice(voice_id="voice-2", type="designed")

    cloned = list_voices(type="cloned")

    assert [v["voice_id"] for v in cloned] == ["voice-1"]


def test_get_voice_returns_none_when_missing(db):
    assert get_voice("missing") is None


def test_update_note_changes_value(db):
    insert_voice(voice_id="voice-1", type="cloned")

    updated = update_note("voice-1", "新备注")

    assert updated is True
    assert get_voice("voice-1")["note"] == "新备注"


def test_update_note_returns_false_when_missing(db):
    assert update_note("missing", "备注") is False


def test_delete_voice_removes_row(db):
    insert_voice(voice_id="voice-1", type="cloned")

    deleted = delete_voice("voice-1")

    assert deleted is True
    assert get_voice("voice-1") is None


def test_delete_voice_returns_false_when_missing(db):
    assert delete_voice("missing") is False
