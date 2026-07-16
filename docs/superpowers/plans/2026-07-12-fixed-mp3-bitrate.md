# MP3 恒定比特率实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让配置页可选择 32/64/128/256 kbps，并确保工作台每个 MP3 分段及拼接成品都使用任务快照锁定的 CBR，默认值为 256 kbps。

**Architecture:** `AppConfig` 保存经过枚举校验的默认码率；工作台在生成动作开始时从设置 API 获取格式、采样率和码率快照，并随分段、重试及拼接请求传递。服务层仅对 MP3 向 MiniMax 发送 `bitrate/force_cbr`，拼接时通过 ffmpeg 的明确 `-b:a` 目标重新编码；WAV/FLAC 完全忽略 MP3 码率语义。

**Tech Stack:** Python 3、FastAPI、Pydantic、httpx、pydub、imageio-ffmpeg、原生 JavaScript、pytest、respx

## Global Constraints

- 优先使用简体中文回答和输出文件。
- `default_bitrate` 使用 bps 存储，仅允许 `32000`、`64000`、`128000`、`256000`，默认 `256000`。
- 旧配置缺少 `default_bitrate` 时直接采用 `256000`，不执行配置文件迁移。
- MP3 始终强制 CBR；不向用户暴露 `force_cbr` 开关。
- WAV/FLAC 保留所选比特率配置，但合成及导出均不应用它。
- 一次工作台生成任务的分段、失败重试和拼接必须使用同一音频配置快照。
- 保持双声道输出和相邻成功分段之间 500ms 静音的现有行为。
- 不增加第三方依赖，不增加 VBR/ABR、自定义任意码率或编码质量档位。

---

## 文件结构

- `app/models.py`：持久化配置模型及码率合法值的单一来源。
- `app/api/studio.py`：音频配置快照请求模型、全局配置回退及 API 到服务层的参数传递。
- `app/services/synthesize.py`：MiniMax payload 和 MP3/WAV/FLAC 拼接导出的编码规则。
- `web/js/pages/settings.js`：比特率选择器、格式联动提示和设置保存。
- `web/js/pages/studio.js`：在生成动作开始时获取并复用音频配置快照。
- `tests/test_config.py`、`tests/test_settings_api.py`：配置默认值、兼容性、枚举校验和 API 往返。
- `tests/test_synthesize_service.py`：MiniMax payload、导出参数、MP3 CBR 与静音回归。
- `tests/test_studio_api.py`：快照优先级、旧调用回退及两条 API 数据流。
- `tests/test_frontend_scripts.py`：配置页联动和工作台快照复用的静态契约。

### Task 1: 配置模型与设置 API

**Files:**
- Modify: `app/models.py`
- Modify: `tests/test_config.py`
- Modify: `tests/test_settings_api.py`

**Interfaces:**
- Consumes: Pydantic `BaseModel` 与现有 `load_config`/`save_config`。
- Produces: `ALLOWED_BITRATES: tuple[int, ...]` 和 `AppConfig.default_bitrate: Literal[32000, 64000, 128000, 256000]`，供设置 API、studio 请求模型和服务层使用。

- [ ] **Step 1: 为默认值、旧配置与非法值编写失败测试**

在 `tests/test_config.py` 增加导入和测试：

```python
import json

import pytest
from pydantic import ValidationError


def test_default_bitrate_is_256_kbps():
    assert AppConfig().default_bitrate == 256000


def test_load_config_supplies_bitrate_for_legacy_file(isolated_app_dir):
    get_config_path().write_text(
        json.dumps({"default_format": "mp3", "default_sample_rate": 32000}),
        encoding="utf-8",
    )

    assert load_config().default_bitrate == 256000


@pytest.mark.parametrize("bitrate", [32000, 64000, 128000, 256000])
def test_app_config_accepts_minimax_mp3_bitrates(bitrate):
    assert AppConfig(default_bitrate=bitrate).default_bitrate == bitrate


def test_app_config_rejects_unsupported_bitrate():
    with pytest.raises(ValidationError):
        AppConfig(default_bitrate=192000)
```

在 `test_load_config_returns_defaults_when_missing` 中增加：

```python
assert config.default_bitrate == 256000
```

在 `tests/test_settings_api.py::test_get_settings_returns_defaults_and_no_api_key` 中增加：

```python
assert body["default_bitrate"] == 256000
```

并在 `test_put_settings_updates_config` 的 JSON 中传入 `"default_bitrate": 128000`，随后断言：

```python
assert body["default_bitrate"] == 128000
```

新增非法设置接口测试：

```python
def test_put_settings_rejects_unsupported_bitrate(client):
    payload = client.get("/api/settings").json()
    payload.pop("has_api_key")
    payload.pop("api_key_masked")
    payload["default_bitrate"] = 192000

    response = client.put("/api/settings", json=payload)

    assert response.status_code == 422
```

- [ ] **Step 2: 运行配置测试并确认失败**

Run: `pytest tests/test_config.py tests/test_settings_api.py -q`

Expected: FAIL，错误包含 `AppConfig` 没有 `default_bitrate`，且设置 API 不拒绝 `192000`。

- [ ] **Step 3: 实现枚举校验和 256 kbps 默认值**

修改 `app/models.py`：

```python
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ALLOWED_BITRATES = (32000, 64000, 128000, 256000)
Bitrate = Literal[32000, 64000, 128000, 256000]


class AppConfig(BaseModel):
    default_model: str = "speech-2.8-hd"
    default_format: str = "mp3"
    default_sample_rate: int = 32000
    default_bitrate: Bitrate = 256000
    save_dir: str = Field(default_factory=_default_save_dir)
    base_url: str = "https://api.minimaxi.com"
    group_id: str = ""
    price_per_1k_chars: float = 0
    price_per_1k_tokens: float = 0
```

保留 `_default_save_dir()` 的原有位置和实现；不要为旧 JSON 编写迁移逻辑，Pydantic 缺省值即完成兼容。

- [ ] **Step 4: 运行配置测试并确认通过**

Run: `pytest tests/test_config.py tests/test_settings_api.py -q`

Expected: PASS。

- [ ] **Step 5: 提交配置模型**

```bash
git add app/models.py tests/test_config.py tests/test_settings_api.py
git commit -m "feat: add configurable MP3 bitrate"
```

### Task 2: MiniMax MP3 CBR 与拼接编码

**Files:**
- Modify: `app/services/synthesize.py`
- Modify: `tests/test_synthesize_service.py`

**Interfaces:**
- Consumes: Task 1 的合法 `bitrate: int`。
- Produces: `synthesize_segment(..., bitrate: int = 256000) -> bytes`、`concat_audio_bytes(..., bitrate: int = 256000) -> Path`、`synthesize_full(..., bitrate: int = 256000) -> dict`。

- [ ] **Step 1: 为格式条件 payload 和导出码率编写失败测试**

在 `tests/test_synthesize_service.py` 增加：

```python
@pytest.mark.asyncio
@respx.mock
async def test_synthesize_segment_forces_selected_mp3_cbr(db):
    route = respx.post(f"{BASE_URL}/v1/t2a_v2").mock(
        return_value=httpx.Response(
            200,
            json={"base_resp": {"status_code": 0}, "data": {"audio": "00"}},
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    await synthesize_segment(
        client, text="你好", voice_id="voice-1", format="mp3", bitrate=256000
    )

    audio_setting = json.loads(route.calls.last.request.content)["audio_setting"]
    assert audio_setting["bitrate"] == 256000
    assert audio_setting["force_cbr"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("format", ["wav", "flac"])
@respx.mock
async def test_synthesize_segment_omits_mp3_bitrate_fields_for_lossless_formats(db, format):
    route = respx.post(f"{BASE_URL}/v1/t2a_v2").mock(
        return_value=httpx.Response(
            200,
            json={
                "base_resp": {"status_code": 0},
                "data": {"audio": _silent_wav_hex(100)},
            },
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    await synthesize_segment(
        client, text="你好", voice_id="voice-1", format=format, bitrate=256000
    )

    audio_setting = json.loads(route.calls.last.request.content)["audio_setting"]
    assert "bitrate" not in audio_setting
    assert "force_cbr" not in audio_setting
```

为导出调用增加单元测试，避免仅凭平均码率判断 CBR：

```python
def _silent_mp3_bytes(duration_ms: int) -> bytes:
    buf = io.BytesIO()
    AudioSegment.silent(duration=duration_ms, frame_rate=32000).export(
        buf, format="mp3", bitrate="128k"
    )
    return buf.getvalue()


def test_concat_mp3_exports_with_selected_constant_bitrate(tmp_path, monkeypatch):
    calls = []
    original_export = AudioSegment.export

    def recording_export(self, *args, **kwargs):
        calls.append(kwargs.copy())
        return original_export(self, *args, **kwargs)

    monkeypatch.setattr(AudioSegment, "export", recording_export)
    output_path = concat_audio_bytes(
        [_silent_mp3_bytes(100)],
        format="mp3",
        bitrate=256000,
        save_dir=str(tmp_path),
        filename="combined.mp3",
    )

    assert output_path.exists()
    assert calls[-1]["format"] == "mp3"
    assert calls[-1]["bitrate"] == "256k"
```

在现有 `test_concat_audio_bytes_adds_500ms_only_between_segments` 中保留 WAV 时长断言，确保无损格式不受影响。

- [ ] **Step 2: 运行服务层新增测试并确认失败**

Run: `pytest tests/test_synthesize_service.py -q`

Expected: FAIL，错误包含 `unexpected keyword argument 'bitrate'`，或 MP3 payload 缺少 `force_cbr`。

- [ ] **Step 3: 实现格式条件 payload 与明确 MP3 导出码率**

在 `app/services/synthesize.py` 中：

1. 给 `_build_t2a_payload`、`synthesize_segment`、`concat_audio_bytes`、`synthesize_full` 增加 `bitrate: int = 256000`（内部 helper 可不设默认）。
2. 将 `audio_setting` 先构造为公共字段，再仅对 MP3增加码率字段：

```python
audio_setting = {
    "sample_rate": sample_rate,
    "format": format,
    "channel": 2,
}
if format == "mp3":
    audio_setting.update({"bitrate": bitrate, "force_cbr": True})

payload: dict = {
    "model": model,
    "text": text,
    "stream": False,
    "voice_setting": voice_setting,
    "audio_setting": audio_setting,
}
```

3. `synthesize_full` 调用每个 `synthesize_segment` 以及最终 `concat_audio_bytes` 时都传 `bitrate=bitrate`。
4. 拼接导出仅对 MP3设置 `bitrate`：

```python
export_kwargs: dict = {"format": format}
if format == "mp3":
    export_kwargs["bitrate"] = f"{bitrate // 1000}k"
try:
    combined.export(output_path, **export_kwargs)
except Exception as exc:
    raise ValueError("音频导出失败") from exc
```

`pydub` 的 `bitrate` 会映射为 ffmpeg `-b:a`；不传 `-q:a` 等 VBR 质量参数，使 libmp3lame 使用指定 CBR。WAV/FLAC 的 `export_kwargs` 不得出现 `bitrate`。

- [ ] **Step 4: 运行服务层测试并确认通过**

Run: `pytest tests/test_synthesize_service.py -q`

Expected: PASS，现有 500ms 静音、双声道和失败分段测试也保持通过。

- [ ] **Step 5: 提交服务层编码规则**

```bash
git add app/services/synthesize.py tests/test_synthesize_service.py
git commit -m "feat: force CBR for MP3 synthesis and export"
```

### Task 3: Studio API 音频配置快照

**Files:**
- Modify: `app/api/studio.py`
- Modify: `tests/test_studio_api.py`

**Interfaces:**
- Consumes: Task 1 的 `Bitrate`，Task 2 的 `bitrate` 服务参数。
- Produces: `AudioConfigPayload` 请求对象；`SegmentSynthesizeRequest.audio_config`、`FullSynthesizeRequest.audio_config`、`ConcatSynthesizeRequest.audio_config`；`_resolve_audio_config(payload, config) -> tuple[str, int, int]`。

- [ ] **Step 1: 编写快照覆盖全局配置及非法快照测试**

在 `tests/test_studio_api.py` 增加：

```python
def test_segment_endpoint_uses_request_audio_snapshot(client):
    from app.config import save_config
    from app.models import AppConfig

    save_config(AppConfig(default_format="wav", default_sample_rate=16000, default_bitrate=32000))
    with respx.mock:
        route = respx.post("https://api.minimaxi.com/v1/t2a_v2").mock(
            return_value=httpx.Response(
                200,
                json={"base_resp": {"status_code": 0}, "data": {"audio": "00"}},
            )
        )
        response = client.post(
            "/api/studio/synthesize/segment",
            json={
                "text": "你好",
                "voice_id": "voice-1",
                "audio_config": {
                    "format": "mp3",
                    "sample_rate": 32000,
                    "bitrate": 256000,
                },
            },
        )

    assert response.status_code == 200
    setting = json.loads(route.calls.last.request.content)["audio_setting"]
    assert setting["format"] == "mp3"
    assert setting["sample_rate"] == 32000
    assert setting["bitrate"] == 256000
    assert setting["force_cbr"] is True


def test_segment_endpoint_rejects_invalid_audio_snapshot(client):
    response = client.post(
        "/api/studio/synthesize/segment",
        json={
            "text": "你好",
            "voice_id": "voice-1",
            "audio_config": {
                "format": "mp3",
                "sample_rate": 32000,
                "bitrate": 192000,
            },
        },
    )

    assert response.status_code == 422
```

为 concat 添加传参测试，使用 monkeypatch 捕获服务调用而不依赖 MP3 fixture：

```python
def test_concat_endpoint_passes_audio_snapshot(client, tmp_path, monkeypatch):
    captured = {}

    def fake_concat(audio_list, **kwargs):
        captured.update(kwargs)
        return tmp_path / "final.mp3"

    monkeypatch.setattr("app.api.studio.concat_audio_bytes", fake_concat)
    response = client.post(
        "/api/studio/synthesize/concat",
        json={
            "audio_hex_list": ["00"],
            "audio_config": {
                "format": "mp3",
                "sample_rate": 32000,
                "bitrate": 128000,
            },
        },
    )

    assert response.status_code == 200
    assert captured["format"] == "mp3"
    assert captured["bitrate"] == 128000
```

为后端整篇合成路径增加同样的捕获测试：

```python
def test_full_endpoint_passes_audio_snapshot(client, tmp_path, monkeypatch):
    captured = {}

    async def fake_full(client, **kwargs):
        captured.update(kwargs)
        return {
            "file_path": tmp_path / "final.mp3",
            "total": 1,
            "completed": 1,
            "failed": [],
        }

    monkeypatch.setattr("app.api.studio.synthesize_full", fake_full)
    response = client.post(
        "/api/studio/synthesize/full",
        json={
            "segments": [{"text": "第一段"}],
            "voice_id": "voice-1",
            "audio_config": {
                "format": "mp3",
                "sample_rate": 44100,
                "bitrate": 64000,
            },
        },
    )

    assert response.status_code == 200
    assert captured["format"] == "mp3"
    assert captured["sample_rate"] == 44100
    assert captured["bitrate"] == 64000
```

现有不带 `audio_config` 的 segment/full 测试必须保留，以证明旧调用仍回退到全局设置。

- [ ] **Step 2: 运行 API 测试并确认失败**

Run: `pytest tests/test_studio_api.py -q`

Expected: FAIL；请求快照被忽略，且 `192000` 没有产生 422。

- [ ] **Step 3: 实现请求模型、回退解析和参数传递**

修改 `app/api/studio.py` 的导入：

```python
from typing import Literal

from app.models import AppConfig, Bitrate
```

增加模型与 helper：

```python
AudioFormat = Literal["mp3", "wav", "flac"]
SampleRate = Literal[8000, 16000, 22050, 24000, 32000, 44100]


class AudioConfigPayload(BaseModel):
    format: AudioFormat
    sample_rate: SampleRate
    bitrate: Bitrate


def _resolve_audio_config(
    payload: AudioConfigPayload | None, config: AppConfig
) -> tuple[str, int, int]:
    if payload is not None:
        return payload.format, payload.sample_rate, payload.bitrate
    return config.default_format, config.default_sample_rate, config.default_bitrate
```

给三个请求模型增加：

```python
audio_config: AudioConfigPayload | None = None
```

每个 endpoint 加载全局 `config` 后只调用一次 `_resolve_audio_config`：

```python
format, sample_rate, bitrate = _resolve_audio_config(payload.audio_config, config)
```

随后向 `synthesize_segment`、`synthesize_full` 或 `concat_audio_bytes` 显式传递：

```python
format=format,
sample_rate=sample_rate,  # concat_audio_bytes 不需要该参数
bitrate=bitrate,
```

`concat` 继续使用全局 `save_dir`，因为任务快照只锁定音频编码参数，不允许客户端覆盖文件系统路径。

- [ ] **Step 4: 运行 API 与服务测试**

Run: `pytest tests/test_studio_api.py tests/test_synthesize_service.py -q`

Expected: PASS。

- [ ] **Step 5: 提交 API 快照支持**

```bash
git add app/api/studio.py tests/test_studio_api.py
git commit -m "feat: accept studio audio configuration snapshots"
```

### Task 4: 配置页比特率交互

**Files:**
- Modify: `web/js/pages/settings.js`
- Modify: `tests/test_frontend_scripts.py`

**Interfaces:**
- Consumes: 设置 API 返回的 `default_format` 和 `default_bitrate`。
- Produces: 保存设置时的 `default_bitrate: number`，以及 `syncBitrateAvailability()` 格式联动行为。

- [ ] **Step 1: 编写前端契约失败测试**

在 `tests/test_frontend_scripts.py` 增加：

```python
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
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_frontend_scripts.py::test_settings_js_has_mp3_bitrate_controls -q`

Expected: FAIL，缺少 `BITRATE_OPTIONS`。

- [ ] **Step 3: 实现选择器、提示与格式联动**

在 `web/js/pages/settings.js` 顶部增加：

```javascript
const BITRATE_OPTIONS = [32000, 64000, 128000, 256000];
```

在默认采样率字段之后渲染：

```javascript
<div class="field-row">
  <label>默认比特率</label>
  <select id="default_bitrate">
    ${BITRATE_OPTIONS.map(
      (value) =>
        `<option value="${value}" ${value === settings.default_bitrate ? "selected" : ""}>${value / 1000} kbps</option>`
    ).join("")}
  </select>
  <span id="bitrate-format-hint" class="hint">仅适用于 MP3</span>
</div>
```

在模板写入后、保存监听器注册前增加：

```javascript
const formatSelect = container.querySelector("#default_format");
const bitrateSelect = container.querySelector("#default_bitrate");
const bitrateHint = container.querySelector("#bitrate-format-hint");

function syncBitrateAvailability() {
  const default_format = formatSelect.value;
  const isMp3 = default_format === "mp3";
  bitrateSelect.disabled = !isMp3;
  bitrateHint.style.display = isMp3 ? "none" : "inline";
}

formatSelect.addEventListener("change", syncBitrateAvailability);
syncBitrateAvailability();
```

保存 payload 增加：

```javascript
default_bitrate: Number(container.querySelector("#default_bitrate").value),
```

禁用 select 不影响通过 DOM 读取其当前值，因此 WAV/FLAC 保存时会保留上次选择。

- [ ] **Step 4: 运行前端契约和设置 API 测试**

Run: `pytest tests/test_frontend_scripts.py tests/test_settings_api.py -q`

Expected: PASS。

- [ ] **Step 5: 提交配置页交互**

```bash
git add web/js/pages/settings.js tests/test_frontend_scripts.py
git commit -m "feat: add MP3 bitrate setting control"
```

### Task 5: 工作台任务级快照复用

**Files:**
- Modify: `web/js/pages/studio.js`
- Modify: `tests/test_frontend_scripts.py`

**Interfaces:**
- Consumes: Task 3 的请求字段 `audio_config` 和 `GET /api/settings`。
- Produces: `fetchAudioConfigSnapshot() -> Promise<{format: string, sample_rate: number, bitrate: number}>`；批量生成循环、失败重试和拼接共享同一个对象。

- [ ] **Step 1: 编写快照获取和复用的前端契约失败测试**

在 `tests/test_frontend_scripts.py` 增加：

```python
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
```

- [ ] **Step 2: 运行契约测试并确认失败**

Run: `pytest tests/test_frontend_scripts.py::test_studio_js_locks_and_reuses_audio_config_snapshot -q`

Expected: FAIL，缺少 `fetchAudioConfigSnapshot`。

- [ ] **Step 3: 实现快照 helper 和单次试听快照**

在 `web/js/pages/studio.js` 的页面函数作用域增加：

```javascript
async function fetchAudioConfigSnapshot() {
  const response = await fetch("/api/settings");
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || "读取音频配置失败");
  return {
    format: body.default_format,
    sample_rate: body.default_sample_rate,
    bitrate: body.default_bitrate,
  };
}
```

扩展 `renderSegments`，允许保存批量任务快照：

```javascript
function renderSegments(segments, failures = {}, audioConfigSnapshot = null) {
  // 保留现有渲染逻辑
  els.segmentList._audioConfigSnapshot = audioConfigSnapshot;
}
```

`synthesizeOneSegment` 在请求前使用已有批量快照，否则为本次手动试听读取一次：

```javascript
const audioConfigSnapshot =
  els.segmentList._audioConfigSnapshot || (await fetchAudioConfigSnapshot());
```

请求 body 增加：

```javascript
audio_config: audioConfigSnapshot,
```

失败后重新调用 `renderSegments` 时必须传回同一个快照：

```javascript
renderSegments(segments, failures, audioConfigSnapshot);
```

- [ ] **Step 4: 实现批量循环、失败重试和拼接共享快照**

在整篇按钮处理器验证音色后、循环开始前只读取一次：

```javascript
let audioConfigSnapshot;
try {
  audioConfigSnapshot = await fetchAudioConfigSnapshot();
} catch (error) {
  resultEl.textContent = error.message;
  resultEl.className = "error";
  return;
}
```

循环内每个 segment body 和最终 concat body 分别增加同一个对象：

```javascript
audio_config: audioConfigSnapshot,
```

批量完成后必须保留快照供失败按钮重试：

```javascript
renderSegments(segments, failures, audioConfigSnapshot);
```

清空工作台和重新解析分段会通过现有重新渲染流程清除 `_audioConfigSnapshot`；不要把它放入模块级持久化状态，应用重启后不恢复旧任务编码配置。

- [ ] **Step 5: 运行前端与 API 测试**

Run: `pytest tests/test_frontend_scripts.py tests/test_studio_api.py -q`

Expected: PASS。

- [ ] **Step 6: 提交工作台快照**

```bash
git add web/js/pages/studio.js tests/test_frontend_scripts.py
git commit -m "feat: lock audio settings per studio generation"
```

### Task 6: 集成验证与文档收尾

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-07-10-settings-as-built.md`

**Interfaces:**
- Consumes: Tasks 1–5 的完整行为。
- Produces: 用户可见能力说明和全套验证证据。

- [ ] **Step 1: 更新用户文档**

在 `README.md` 的工作台或配置能力描述中加入：

```markdown
- **音频编码**：MP3 支持 32/64/128/256 kbps，分段与拼接成品统一使用恒定比特率（CBR）；WAV/FLAC 不应用比特率设置。
```

在 `docs/superpowers/specs/2026-07-10-settings-as-built.md` 的实现摘要补充：

```markdown
- MP3 默认比特率可配置为 32/64/128/256 kbps，默认 256 kbps；WAV/FLAC 下禁用该选项但保留所选值。
```

- [ ] **Step 2: 运行完整测试套件**

Run: `pytest -q`

Expected: 全部 PASS、无 error；允许当前测试基础设施中已知的 `StarletteDeprecationWarning`，不得出现其他 warning。

- [ ] **Step 3: 执行 MP3 实际编码验收**

使用测试中已经过验证的 `concat_audio_bytes` 生成至少两个 1 秒音频分段的 256 kbps MP3，并用 bundled ffmpeg 检查文件：

```bash
python -c 'from pydub import AudioSegment; from app.services.synthesize import concat_audio_bytes; import io, tempfile; bufs=[io.BytesIO() for _ in range(2)]; [AudioSegment.silent(duration=1000, frame_rate=32000).set_channels(2).export(buf, format="mp3", bitrate="128k") for buf in bufs]; p=concat_audio_bytes([buf.getvalue() for buf in bufs], format="mp3", bitrate=256000, save_dir=tempfile.gettempdir(), filename="voicecanvas-cbr-check.mp3"); print(p)'
```

随后运行（将路径替换为上一命令输出）：

```bash
"$(python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')" -hide_banner -i /tmp/voicecanvas-cbr-check.mp3 -f null -
```

Expected: 输入信息显示 MP3、32000 Hz、stereo、约 `256 kb/s`；总时长约 2.5 秒。CBR 的强保证来自 MiniMax `force_cbr: true` 和本地 ffmpeg `-b:a 256k` 的测试契约，探测输出用于验证实际成品未偏离目标码率。

- [ ] **Step 4: 检查变更范围与工作树**

Run: `git diff --check && git status --short`

Expected: `git diff --check` 无输出；仅出现本计划范围内尚未提交的 README/竣工文档。

- [ ] **Step 5: 提交文档与最终验证记录**

```bash
git add README.md docs/superpowers/specs/2026-07-10-settings-as-built.md
git commit -m "docs: document fixed MP3 bitrate support"
```

- [ ] **Step 6: 确认最终状态**

Run: `git status --short`

Expected: 无输出，工作树干净。
