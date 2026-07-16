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
