# VoiceCanvas Test Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Keychain 清除测试准确表达哨兵语义，并锁定 WebView 原生窗口标题“声绘魔法”。

**Architecture:** 仅修改测试，不改变生产代码。Keychain 测试直接检查新 service 中的清除哨兵；WebView 测试调用真实 `app.main.main()`，同时用轻量替身隔离数据库、线程、等待和 GUI 副作用。

**Tech Stack:** Python 3.13、pytest、monkeypatch、pywebview

## Global Constraints

- 不修改生产代码或运行时行为。
- 只修改 `tests/test_keychain.py` 和 `tests/test_main.py`。
- Keychain 仍保留旧 `VoiceMax` 项，新版通过新 service 中的清除哨兵防止旧凭据复活。
- WebView 标题固定为 `声绘魔法`。
- 测试不得启动真实数据库、服务器线程或 WebView 窗口。

---

## File Structure

- `tests/test_keychain.py`：准确描述并断言 Keychain 清除哨兵、幂等清除和旧凭据保留行为。
- `tests/test_main.py`：通过隔离副作用调用真实 `main()`，锁定 WebView 窗口标题和启动编排。

### Task 1: 清理 Keychain 清除测试语义

**Files:**
- Modify: `tests/test_keychain.py`

**Interfaces:**
- Consumes: `delete_api_key() -> None`、`get_api_key() -> str | None`、`KEYRING_CLEARED_SENTINEL`。
- Produces: 准确覆盖“写入哨兵而非物理删除”的测试契约。

- [ ] **Step 1: 导入清除哨兵并重写清除已有值测试**

将导入改为：

```python
from app.config import (
    KEYRING_CLEARED_SENTINEL,
    delete_api_key,
    get_api_key,
    set_api_key,
)
```

将 `test_delete_api_key_removes_value` 替换为：

```python
def test_delete_api_key_marks_value_as_cleared(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(keyring, "get_password", fake.get_password)
    monkeypatch.setattr(keyring, "set_password", fake.set_password)
    set_api_key("sk-test-123")

    delete_api_key()

    assert get_api_key() is None
    assert (
        fake.get_password("VoiceCanvas", "minimax_api_key")
        == KEYRING_CLEARED_SENTINEL
    )
```

- [ ] **Step 2: 重写不存在值的幂等清除测试**

将 `test_delete_api_key_ignores_missing_key` 替换为：

```python
def test_delete_api_key_marks_missing_value_as_cleared(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(keyring, "set_password", fake.set_password)

    delete_api_key()

    assert (
        fake.get_password("VoiceCanvas", "minimax_api_key")
        == KEYRING_CLEARED_SENTINEL
    )
```

- [ ] **Step 3: 清理旧凭据防复活测试的无效 monkeypatch 并强化断言**

从 `test_delete_api_key_does_not_resurrect_legacy_value` 删除：

```python
monkeypatch.setattr(keyring, "delete_password", fake.delete_password)
```

并在 `assert get_api_key() is None` 后增加：

```python
assert (
    fake.get_password("VoiceCanvas", "minimax_api_key")
    == KEYRING_CLEARED_SENTINEL
)
```

- [ ] **Step 4: 运行 Keychain 聚焦测试**

Run: `.venv/bin/python -m pytest tests/test_keychain.py -v`

Expected: `8 passed`。本任务只重构测试语义，不修改生产代码，因此没有生产行为的 RED 阶段；新增哨兵断言必须全部通过。

- [ ] **Step 5: 提交 Keychain 测试清理**

```bash
git add tests/test_keychain.py
git commit -m "test: clarify keychain cleared sentinel behavior"
```

### Task 2: 增加 WebView 窗口标题回归测试

**Files:**
- Modify: `tests/test_main.py`

**Interfaces:**
- Consumes: `app.main.main() -> None`。
- Produces: 对 `webview.create_window("声绘魔法", "http://127.0.0.1:43123")` 和启动编排的自动化契约。

- [ ] **Step 1: 增加测试依赖和 WebView 编排测试**

在文件顶部增加：

```python
import sys
from types import SimpleNamespace

import app.main as main_module
```

在 FastAPI 品牌测试后增加：

```python
def test_main_uses_voicecanvas_window_title(monkeypatch):
    calls = {}
    fake_app = object()

    class FakeThread:
        def __init__(self, target, args, daemon):
            calls["thread"] = (target, args, daemon)

        def start(self):
            calls["thread_started"] = True

    fake_webview = SimpleNamespace(
        create_window=lambda title, url: calls.setdefault("window", (title, url)),
        start=lambda: calls.setdefault("webview_started", True),
    )

    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    monkeypatch.setattr(main_module, "_force_chinese_native_menu", lambda: None)
    monkeypatch.setattr(main_module, "_restore_native_context_menu", lambda: None)
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    monkeypatch.setattr(main_module, "create_app", lambda: fake_app)
    monkeypatch.setattr(main_module, "find_free_port", lambda: 43123)
    monkeypatch.setattr(main_module.threading, "Thread", FakeThread)
    monkeypatch.setattr(main_module.time, "sleep", lambda _: None)

    main_module.main()

    assert calls["window"] == ("声绘魔法", "http://127.0.0.1:43123")
    assert calls["thread"] == (main_module.run_server, (fake_app, 43123), True)
    assert calls["thread_started"] is True
    assert calls["webview_started"] is True
```

- [ ] **Step 2: 验证测试能捕获标题回退**

临时将 `app/main.py` 中 `webview.create_window("声绘魔法", ...)` 的标题改为 `VoiceMax`，运行：

Run: `.venv/bin/python -m pytest tests/test_main.py::test_main_uses_voicecanvas_window_title -v`

Expected: FAIL，实际窗口元组标题为 `VoiceMax`，期望为 `声绘魔法`。

立即还原 `app/main.py` 的临时突变，并确认 `git diff -- app/main.py` 无输出。该突变只用于证明测试有效，不得进入提交。

- [ ] **Step 3: 运行 WebView 聚焦测试并确认通过**

Run: `.venv/bin/python -m pytest tests/test_main.py::test_main_uses_voicecanvas_window_title -v`

Expected: `1 passed`，且不启动真实线程、数据库或窗口。

- [ ] **Step 4: 运行两文件聚焦回归**

Run: `.venv/bin/python -m pytest tests/test_keychain.py tests/test_main.py -v`

Expected: 全部 PASS；除既有 `StarletteDeprecationWarning` 外无新增 warning 或 error。

- [ ] **Step 5: 运行全量回归和差异检查**

Run: `.venv/bin/python -m pytest -v`

Expected: 全部 PASS；除既有 `StarletteDeprecationWarning` 外无新增 warning 或 error。

Run: `git diff --check && git status --short`

Expected: `git diff --check` 无输出；仅 `tests/test_main.py` 尚未提交，`app/main.py` 无差异。

- [ ] **Step 6: 提交并推送 WebView 测试**

```bash
git add tests/test_main.py
git commit -m "test: cover VoiceCanvas webview window title"
git push
```

Expected: 提交推送到 `agent/voicecanvas-rename`，现有 Draft PR #1 自动更新。
