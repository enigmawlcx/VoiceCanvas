# 整篇音频段间留白调整为一秒实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将整篇音频相邻成功段之间的额外固定静音从 500 毫秒调整为 1000 毫秒。

**Architecture:** 保持现有本地拼接架构与函数签名不变，只调整内部常量 `SEGMENT_GAP_MS`。同步修改直接拼接和失败段集成测试，使一秒规则由真实导出音频时长约束。

**Tech Stack:** Python 3、pydub、pytest、respx

## Global Constraints

- 每两个成功合成的相邻音频段之间额外插入固定 1000 毫秒静音。
- 文件开头和结尾不增加静音；单段音频不增加静音。
- 合成失败段不产生占位静音。
- 不检测或裁剪 MiniMax 音频自身的头尾静音。
- 不修改 HTTP 接口、前端请求、配置模型、数据库或 MiniMax 请求。
- 不新增设置控件或可配置项。
- 本计划不重新构建应用安装包。

---

## 文件结构

- 修改 `app/services/synthesize.py`：将固定段间留白常量从 500 改为 1000。
- 修改 `tests/test_synthesize_service.py`：更新测试名称与单段、两段、三段、中间失败段的期望时长。

### Task 1: 将固定段间留白调整为 1000 毫秒

**Files:**
- Modify: `app/services/synthesize.py:28-30`
- Test: `tests/test_synthesize_service.py:64-83,253-299`

**Interfaces:**
- Consumes: 现有内部常量 `SEGMENT_GAP_MS: int` 与 `concat_audio_bytes(...) -> Path`
- Produces: `SEGMENT_GAP_MS = 1000`；公开函数签名和返回类型不变。

- [ ] **Step 1: 先更新直接拼接测试以表达一秒规则**

将参数化数据与测试名称改为：

```python
@pytest.mark.parametrize(
    ("durations_ms", "expected_duration_ms"),
    [
        ([120], 120),
        ([120, 180], 1300),
        ([120, 180, 240], 2540),
    ],
)
def test_concat_audio_bytes_adds_1000ms_only_between_segments(
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

- [ ] **Step 2: 更新中间失败段测试的一秒期望**

保持现有三次 MiniMax 模拟响应、失败索引和成功数量断言不变，只将最终时长断言改为：

```python
    exported = AudioSegment.from_file(output["file_path"], format="wav")
    assert len(exported) == pytest.approx(150 + 1000 + 250, abs=5)
```

- [ ] **Step 3: 运行聚焦测试并确认当前实现失败**

Run:

```bash
.venv/bin/pytest \
  tests/test_synthesize_service.py::test_concat_audio_bytes_adds_1000ms_only_between_segments \
  tests/test_synthesize_service.py::test_synthesize_full_adds_one_gap_between_successes_when_middle_segment_fails \
  -v
```

Expected: 单段参数通过；两段、三段和中间失败段失败。当前实际时长分别约为 800、1540、900 毫秒，低于一秒规则对应的 1300、2540、1400 毫秒。

- [ ] **Step 4: 将固定留白常量改为 1000 毫秒**

在 `app/services/synthesize.py` 中修改：

```python
DEFAULT_MODEL = "speech-2.8-hd"
SEGMENT_GAP_MS = 1000
```

不要修改 `concat_audio_bytes()` 的循环、参数或调用方。

- [ ] **Step 5: 运行聚焦测试并确认通过**

Run:

```bash
.venv/bin/pytest \
  tests/test_synthesize_service.py::test_concat_audio_bytes_adds_1000ms_only_between_segments \
  tests/test_synthesize_service.py::test_synthesize_full_adds_one_gap_between_successes_when_middle_segment_fails \
  -v
```

Expected: 4 个测试参数全部 PASS。

- [ ] **Step 6: 运行服务测试与完整测试套件**

Run:

```bash
.venv/bin/pytest tests/test_synthesize_service.py -v
.venv/bin/pytest -q
git diff --check
```

Expected: 服务测试全部 PASS；完整测试套件全部 PASS；`git diff --check` 无输出。若完整测试在受限沙箱内仅因 `test_find_free_port_returns_valid_port` 无法绑定本机临时端口而失败，应在获准的非沙箱环境原样重跑完整测试，不能将沙箱失败计为通过。

- [ ] **Step 7: 检查范围并提交**

Run:

```bash
git diff -- app/services/synthesize.py tests/test_synthesize_service.py
```

Expected: 差异仅包含 `SEGMENT_GAP_MS`、测试名称及对应时长期望。

```bash
git add app/services/synthesize.py tests/test_synthesize_service.py
git commit -m "feat: extend segment silence to one second"
```
