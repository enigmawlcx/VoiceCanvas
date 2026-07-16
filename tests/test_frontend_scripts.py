import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "web" / "js"
WEB_DIR = Path(__file__).resolve().parents[1] / "web"


def test_index_uses_voicecanvas_brand():
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")

    assert "<title>声绘魔法</title>" in html
    assert '<span class="brand-name">声绘魔法</span>' in html
    assert 'alt="声绘魔法"' in html
    assert ">VoiceMax<" not in html


def test_api_errors_module_exports_helpers():
    content = (ROOT / "api-errors.js").read_text(encoding="utf-8")
    assert "isMissingApiKeyError" in content
    assert "handleApiError" in content
    assert "尚未配置 API Key" in content
    assert "window.VoiceMaxApiErrors" in content


def test_app_js_has_page_lifecycle_guard():
    content = (ROOT / "app.js").read_text(encoding="utf-8")
    assert "pageGeneration" in content
    assert "__isPageActive" in content
    assert "navigateToSettings" in content
    assert "window.VoiceMaxNavigate" in content


def test_studio_js_has_progress_and_retry_markers():
    content = (ROOT / "pages" / "studio.js").read_text(encoding="utf-8")
    for marker in [
        "已完成",
        "segment-failed",
        "synthesize/concat",
        "vm-sound-effects",
        "studioSaveGeneration",
    ]:
        assert marker in content, marker


def test_studio_js_locks_and_reuses_audio_config_snapshot():
    content = (ROOT / "pages" / "studio.js").read_text(encoding="utf-8")

    for marker in [
        "fetchAudioConfigSnapshot",
        'fetch("/api/settings")',
        "audioConfigSnapshot",
        "audio_config: audioConfigSnapshot",
        "_audioConfigSnapshot",
    ]:
        assert marker in content, marker


def test_studio_js_always_restores_full_synthesis_button():
    content = (ROOT / "pages" / "studio.js").read_text(encoding="utf-8")

    disabled_region = re.search(
        r"fullBtn\.disabled = true;\s*"
        r"resultEl\.className = \"\";\s*"
        r"try \{(?P<body>.*?)\}\s*finally \{\s*"
        r"fullBtn\.disabled = false;\s*\}",
        content,
        re.DOTALL,
    )

    assert disabled_region, "整篇合成按钮的禁用区必须由外层 try/finally 恢复"
    assert "for (let index = 0; index < segments.length; index += 1)" in disabled_region.group("body")
    assert 'fetch("/api/studio/synthesize/concat"' in disabled_region.group("body")


def test_settings_js_has_mp3_bitrate_controls():
    content = (ROOT / "pages" / "settings.js").read_text(encoding="utf-8")

    for marker in [
        "BITRATE_OPTIONS",
        'id="default_bitrate"',
        "仅适用于 MP3",
        "syncBitrateAvailability",
        "settings.default_bitrate",
        'default_format === "mp3"',
    ]:
        assert marker in content, marker
