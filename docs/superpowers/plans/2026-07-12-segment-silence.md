# 整篇音频段间固定留白实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在整篇音频本地拼接时，为每两个成功音频段之间额外插入固定 500 毫秒静音。

**Architecture:** 保持逐段调用 MiniMax 和现有 HTTP 接口不变，只扩展后端统一拼接函数 `concat_audio_bytes()`。该函数解码音频块后，在第二个及后续音频块前插入 pydub 静音片段，因此 `/synthesize/concat` 与 `/synthesize/full` 自动获得一致行为。

**Tech Stack:** Python 3、pydub、imageio-ffmpeg、pytest、respx

## Global Constraints

- 每两个成功合成的相邻音频段之间额外插入固定 500 毫秒静音。
- 文件开头和结尾不增加静音；单段音频不增加静音。
- 不检测或裁剪 MiniMax 音频自带的头尾静音。
- 合成失败的音频段不产生占位静音；相邻成功段之间只插入一次静音。
- 不修改 HTTP 接口签名、前端请求结构、配置文件或数据库结构。
- 不增加 MiniMax 请求、输入字符或费用。
- 500 毫秒是固定产品规则，不新增界面开关或配置项。

---

## 文件结构

- 修改 `app/services/synthesize.py`：定义内部常量 `SEGMENT_GAP_MS`，并由 `concat_audio_bytes()` 在相邻音频块之间生成和插入静音。
- 修改 `tests/test_synthesize_service.py`：直接验证单段、两段、三段拼接时长，并验证整篇合成跳过失败段后只按成功段数量插入静音。

无需修改 API 与前端文件：两条整篇导出路径已经统一调用 `concat_audio_bytes()`。

### Task 1: 在统一拼接函数中增加 500 毫秒段间静音

**Files:**
- Modify: `app/services/synthesize.py:28-38,117-137`
- Test: `tests/test_synthesize_service.py:12-15,45-49,113-187`

**Interfaces:**
- Consumes: `concat_audio_bytes(segments_audio: list[bytes], *, format: str, save_dir: str, filename: str | None = None) -> Path`
- Produces: 内部常量 `SEGMENT_GAP_MS: int = 500`；`concat_audio_bytes()` 的公开签名不变，输出音频在 N 个输入块之间包含 N−1 个固定静音片段。

- [ ] **Step 1: 导入拼接函数并添加直接覆盖单段、两段和三段时长的失败测试**

将 `tests/test_synthesize_service.py` 的合成服务导入改为：

```python
from app.services.synthesize import concat_audio_bytes, synthesize_full, synthesize_segment
```

在 `_silent_wav_hex()` 后添加字节辅助函数和参数化测试：

```python
def _silent_wav_bytes(duration_ms: int) -> bytes:
    return bytes.fromhex(_silent_wav_hex(duration_ms))


@pytest.mark.parametrize(
    ("durations_ms", "expected_duration_ms"),
    [
        ([120], 120),
        ([120, 180], 800),
        ([120, 180, 240], 1540),
    ],
)
def test_concat_audio_bytes_adds_500ms_only_between_segments(
    tmp_path, durations_ms, expected_duration_ms
):
    output_path = concat_audio_bytes(
        [_silent_wav_bytes(duration) for duration in durations_ms],
        format="wav",
        save_dir=str(tmp_path),
        filename="combined.wav",
    )

    exported = AudioSegment.from_file(output_path, format="wav")
    assert len(exported) == pytest.approx(expected_duration_ms, abs=5)
```

这些用例分别证明单段没有首尾留白、两段只有一个 500 毫秒间隔、三段只有两个 500 毫秒间隔。

- [ ] **Step 2: 运行直接拼接测试并确认当前实现失败**

Run:

```bash
pytest tests/test_synthesize_service.py::test_concat_audio_bytes_adds_500ms_only_between_segments -v
```

Expected: 参数 `[120]` 通过；参数 `[120, 180]` 和 `[120, 180, 240]` 失败，实际时长分别约为 300 毫秒和 540 毫秒，缺少预期的段间静音。

- [ ] **Step 3: 添加中间失败段的整篇合成测试**

将现有 `test_synthesize_full_continues_when_one_segment_fails` 改为三个输入段，令第二段失败、第一和第三段成功，并精确验证只产生一个间隔：

```python
@pytest.mark.asyncio
@respx.mock
async def test_synthesize_full_adds_one_gap_between_successes_when_middle_segment_fails(
    db, tmp_path
):
    respx.post(f"{BASE_URL}/v1/t2a_v2").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                    "data": {"audio": _silent_wav_hex(150)},
                },
            ),
            httpx.Response(
                200,
                json={
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                    "data": {"audio": ""},
                },
            ),
            httpx.Response(
                200,
                json={
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                    "data": {"audio": _silent_wav_hex(250)},
                },
            ),
        ]
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    output = await synthesize_full(
        client,
        segments=[
            {"text": "第一段", "emotion": "calm"},
            {"text": "第二段", "emotion": "happy"},
            {"text": "第三段", "emotion": "sad"},
        ],
        voice_id="voice-1",
        format="wav",
        save_dir=str(tmp_path),
        filename="partial.wav",
    )

    assert output["completed"] == 2
    assert output["total"] == 3
    assert output["failed"] == [{"index": 1, "error": "合成接口未返回音频数据"}]
    exported = AudioSegment.from_file(output["file_path"], format="wav")
    assert len(exported) == pytest.approx(150 + 500 + 250, abs=5)
```

- [ ] **Step 4: 运行失败段测试并确认当前实现失败**

Run:

```bash
pytest tests/test_synthesize_service.py::test_synthesize_full_adds_one_gap_between_successes_when_middle_segment_fails -v
```

Expected: FAIL，导出时长约为 400 毫秒而非 900 毫秒；失败段索引和成功数量断言通过。

- [ ] **Step 5: 在本地拼接函数中插入固定静音**

在 `app/services/synthesize.py` 的 `DEFAULT_MODEL` 后定义内部常量：

```python
DEFAULT_MODEL = "speech-2.8-hd"
SEGMENT_GAP_MS = 500
```

将 `concat_audio_bytes()` 的拼接循环改为：

```python
    combined: AudioSegment | None = None
    for audio_bytes in segments_audio:
        chunk = _audio_bytes_to_segment(audio_bytes, format=format)
        if combined is None:
            combined = chunk
        else:
            silence = AudioSegment.silent(
                duration=SEGMENT_GAP_MS,
                frame_rate=combined.frame_rate,
            )
            combined = combined + silence + chunk
```

不要更改函数参数或调用方。使用当前已拼接音频的帧率生成静音，pydub 在追加时继续负责声道与采样宽度协调。

- [ ] **Step 6: 运行聚焦测试并确认全部通过**

Run:

```bash
pytest tests/test_synthesize_service.py -v
```

Expected: `tests/test_synthesize_service.py` 全部 PASS；两段原有测试 `test_synthesize_full_concatenates_segments_and_exports_file` 的宽松下界断言也继续通过。

- [ ] **Step 7: 运行完整测试套件并检查代码差异**

Run:

```bash
pytest -q
git diff --check
git diff -- app/services/synthesize.py tests/test_synthesize_service.py
```

Expected: 完整测试套件全部 PASS；`git diff --check` 无输出；差异仅包含固定静音实现和相关测试，不包含 API、前端、配置或数据库改动。

- [ ] **Step 8: 提交功能与测试**

```bash
git add app/services/synthesize.py tests/test_synthesize_service.py
git commit -m "feat: add fixed silence between audio segments"
```
