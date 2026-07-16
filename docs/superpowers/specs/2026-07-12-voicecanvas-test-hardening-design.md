# VoiceCanvas 测试加固设计

- 日期：2026-07-12
- 状态：待实施
- 范围：Keychain 清除语义测试、WebView 窗口标题回归测试

## 1. 目标

消除 VoiceCanvas 改名整分支审查留下的两项非阻塞测试维护性问题：让 Keychain 清除测试准确表达哨兵语义，并为 macOS WebView 窗口标题增加自动化回归保护。

## 2. 约束

- 不修改生产代码或运行时行为。
- 只修改 `tests/test_keychain.py` 和 `tests/test_main.py`。
- Keychain 仍保留旧 `VoiceMax` 项，新版通过新 service 中的清除哨兵防止旧凭据复活。
- WebView 标题固定为 `声绘魔法`。
- 测试不得启动真实数据库、服务器线程或 WebView 窗口。

## 3. Keychain 测试设计

- 删除清除测试中不再使用的 `delete_password` monkeypatch。
- 将测试名称从物理删除语义改为清除哨兵语义。
- 清除已有新凭据后，直接断言 `VoiceCanvas/minimax_api_key` 保存了 `KEYRING_CLEARED_SENTINEL`，并断言公开读取结果为 `None`。
- 清除不存在的新凭据时，同样断言写入清除哨兵，以证明清除操作是幂等的。
- 旧 `VoiceMax` 凭据存在时，断言旧值保持不变，并断言新版读取为 `None`，证明旧凭据不会复活。

## 4. WebView 标题测试设计

测试直接调用真实 `app.main.main()`，避免为测试引入新的生产辅助函数。通过 monkeypatch 隔离所有外部副作用：

- `_force_chinese_native_menu()`
- `_restore_native_context_menu()`
- `init_db()`
- `create_app()`
- `find_free_port()`
- `threading.Thread`
- `time.sleep()`
- `webview` 模块

测试使用固定端口和假的 WebView 对象，断言：

- `webview.create_window()` 收到标题 `声绘魔法` 和对应本地 URL；
- `webview.start()` 被调用；
- 服务器线程按守护线程方式创建并启动。

## 5. 验证策略

- 先增加 WebView 回归测试，并通过临时改变标题的突变检查证明测试能捕获回退；突变只用于 RED 证据，随后立即还原，不进入提交。
- Keychain 部分属于测试语义重构，不改变生产行为；修改后运行聚焦测试确认哨兵断言与既有迁移行为共同通过。
- 运行 `pytest tests/test_keychain.py tests/test_main.py -v`。
- 运行全量 `pytest -v`。
- 运行 `git diff --check`，确认工作树只包含本设计范围文件。

## 6. 交付

测试改动形成单独提交并推送到现有 Draft PR #1，不修改 PR 的功能范围或生产行为。
