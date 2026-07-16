# VoiceMax Maintenance Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 隔离测试中的系统 Keychain、消除文档矛盾、处理项目可控警告，并给出区分代码与环境限制的验证结果。

**Architecture:** 生产代码行为保持不变；系统资源通过 pytest fixture 在测试边界隔离。文档以当前代码与测试为事实源，历史计划保留原始步骤但明确其历史状态。警告只在找到根因且不需要高风险依赖升级时修复。

**Tech Stack:** Python 3.13、pytest 9、FastAPI 0.139、Starlette TestClient、keyring、pydub、imageio-ffmpeg、Markdown。

## Global Constraints

- 仅支持 macOS，应用仍需在启动时绑定 `127.0.0.1` 随机端口。
- API Key 继续存放在 macOS Keychain，生产代码不得静默吞掉 Keychain 错误。
- 不新增产品功能，不升级 FastAPI/Starlette/httpx 核心依赖。
- 不为了沙箱限制修改 `find_free_port()` 的生产实现。
- 每个修复先复现、再最小修改、最后执行定向和回归测试。

---

### Task 1: 隔离 Settings API 测试的真实 Keychain

**Files:**
- Modify: `tests/test_settings_api.py:9-11`

**Interfaces:**
- Consumes: `create_app() -> FastAPI` 和 pytest `monkeypatch` fixture。
- Produces: 默认返回无 API Key、但允许单个测试覆盖的 `client` fixture。

- [x] **Step 1: 复现真实 Keychain 泄漏**

Run: `.venv/bin/pytest tests/test_settings_api.py::test_put_settings_updates_config -q`

Expected: 在无 Keychain 权限环境中 FAIL，调用栈进入 `app.api.settings.get_api_key` 和 macOS keyring。

- [x] **Step 2: 在 fixture 边界添加最小隔离**

将 fixture 改为：

```python
@pytest.fixture
def client(isolated_app_dir, monkeypatch):
    monkeypatch.setattr("app.api.settings.get_api_key", lambda: None)
    return TestClient(create_app())
```

已有需要模拟密钥的测试继续通过自身的 `monkeypatch.setattr` 覆盖默认行为。

- [x] **Step 3: 验证 Settings 测试**

Run: `.venv/bin/pytest tests/test_settings_api.py -q`

Expected: 7 passed，且不出现 Keychain 异常。

- [x] **Step 4: 验证测试未触碰真实 Keychain**

Run: `.venv/bin/pytest tests/test_settings_api.py::test_put_settings_updates_config tests/test_settings_api.py::test_put_api_key_stores_key_and_masks_it -q`

Expected: 2 passed。

---

### Task 2: 把历史 backlog 更新为真实完成状态

**Files:**
- Modify: `docs/superpowers/plans/2026-07-10-voicemax-improvement-backlog.md`

**Interfaces:**
- Consumes: 当前 A1–A10 实现、109 项测试、三份 as-built 文档。
- Produces: 一份明确标记为“历史完成记录”的路线图，以及只包含当前问题的维护清单。

- [x] **Step 1: 更新标题、状态和现状摘要**

在文首加入“状态：Phase 0–4 已完成（2026-07-10）；本文保留为历史记录”，把 99/100 测试和未提交改动等旧描述替换为当前状态。

- [x] **Step 2: 将 A–E 条目分类为已解决、保留取舍和当前债务**

保留原编号以便追溯，但不得继续把 A1–A10、E1、E3、E4描述为未实现。当前债务只保留：Settings fixture 隔离、真实 DOM 交互测试缺口、Starlette/pydub 警告、StaticFiles 注册顺序风险和未归档的部分人工验证。

- [x] **Step 3: 更新优先级和删除过期执行询问**

把 Phase 0–4 标记为历史完成阶段，删除“你想从哪个 Phase 开始”，链接到本计划作为后续维护入口。

- [x] **Step 4: 验证文档没有旧状态断言**

Run: `rg -n "99 项通过|仍标注「待编写|应用图标.*未提交|你想从哪个 Phase|A1.*未写入|A10.*无限流重试" docs/superpowers/plans/2026-07-10-voicemax-improvement-backlog.md`

Expected: 无匹配。

---

### Task 3: 对齐主设计正文、README 与 Studio 测试说明

**Files:**
- Modify: `docs/superpowers/specs/2026-07-08-voice-max-design.md`
- Modify: `docs/superpowers/specs/2026-07-08-studio-redesign-design.md:237-249`
- Modify: `docs/superpowers/plans/2026-07-08-voice-max-foundation.md`
- Modify: `docs/superpowers/plans/2026-07-08-studio-redesign.md`
- Modify: `README.md:5-22`

**Interfaces:**
- Consumes: textarea + 分段预览、SVG 折线图、imageio-ffmpeg、现有静态脚本测试。
- Produces: 直接反映 as-built 状态的用户说明和设计正文。

- [x] **Step 1: 更新主设计规范性正文**

将架构图、工作台、报表、依赖和项目树中的 CodeMirror/ECharts/system ffmpeg/vendor 描述替换为实际实现；附录改为历史设计决策，不再承担纠正文义的职责。

- [x] **Step 2: 更新 README 功能摘要**

补充整篇合成失败段重试、音效器、clone prompt、按周趋势和费用估算；保留“无需系统 ffmpeg”的准确说明。

- [x] **Step 3: 澄清前端测试覆盖边界**

Studio spec 写明当前已有 `tests/test_frontend_scripts.py` 静态标记检查，但没有浏览器 DOM/交互自动化；不得笼统写成“前端零测试”。

- [x] **Step 4: 标记历史实施计划**

在两份旧计划标题后加入状态说明：计划已完成，未勾选的逐步步骤是原始 TDD 执行模板，完成状态以末尾“完成标准”和提交历史为准。

- [x] **Step 5: 验证当前文档描述**

Run: `rg -n "CodeMirror|ECharts|brew install ffmpeg|web/vendor|前端逻辑.*暂无自动化测试基建" README.md docs/superpowers/specs/2026-07-08-voice-max-design.md docs/superpowers/specs/2026-07-08-studio-redesign-design.md`

Expected: 仅历史决策说明中允许出现 CodeMirror/ECharts；其余过期描述无匹配。

---

### Task 4: 消除 pydub 导入期警告并记录上游兼容性债务

**Files:**
- Modify: `app/services/synthesize.py:1-14`
- Test: `tests/test_synthesize_service.py`
- Modify: `docs/superpowers/plans/2026-07-11-maintenance-cleanup.md`

**Interfaces:**
- Consumes: `imageio_ffmpeg.get_ffmpeg_exe() -> str`。
- Produces: 导入 `app.services.synthesize` 时不触发 pydub 的“找不到 ffmpeg”警告，`AudioSegment.converter` 仍指向内置二进制。

- [x] **Step 1: 编写导入期警告回归测试**

新增一个 subprocess 测试，以干净 Python 进程执行：

```python
result = subprocess.run(
    [sys.executable, "-W", "error", "-c", "import app.services.synthesize"],
    cwd=Path(__file__).resolve().parents[1],
    capture_output=True,
    text=True,
)
assert result.returncode == 0, result.stderr
```

- [x] **Step 2: 验证测试因当前 pydub 警告失败**

Run: `.venv/bin/pytest tests/test_synthesize_service.py -q`

Expected: 新测试 FAIL，stderr 包含 `Couldn't find ffmpeg or avconv`。

- [x] **Step 3: 在导入 pydub 前提供 ffmpeg 路径**

先取得 `imageio_ffmpeg.get_ffmpeg_exe()`，临时把其目录前置到 `PATH` 后再导入 pydub；导入完成后恢复原 PATH，并继续显式设置 `AudioSegment.converter`。使用 `try/finally`，避免模块导入永久修改进程环境。

- [x] **Step 4: 验证合成服务测试和警告**

Run: `.venv/bin/pytest tests/test_synthesize_service.py -q`

Expected: 全部通过，且无 pydub warning。

- [x] **Step 5: 记录 Starlette 警告决策**

在本计划执行记录中注明：警告来自 FastAPI 0.139 暂时仍导出基于旧 httpx 的 `TestClient`，本轮不升级核心依赖；后续在 FastAPI 官方支持的迁移路径稳定后单独处理。

---

### Task 5: 完整验证与计划收尾

**Files:**
- Modify: `docs/superpowers/plans/2026-07-11-maintenance-cleanup.md`

**Interfaces:**
- Consumes: Tasks 1–4 的修改。
- Produces: 可审计的最终验证记录。

- [x] **Step 1: 运行不依赖 socket bind 的回归测试**

Run: `.venv/bin/pytest -q --ignore=tests/test_main.py && .venv/bin/pytest tests/test_main.py -q -k "not find_free_port"`

Expected: 所有执行项通过；仅保留已记录的 Starlette 上游弃用警告。

- [x] **Step 2: 尝试完整测试**

Run: `.venv/bin/pytest -q`

Expected outside restricted sandbox: 110 passed。若沙箱禁止 socket bind，Expected in sandbox: 仅 `test_find_free_port_returns_valid_port` 因 `PermissionError` 失败，其余通过。

- [x] **Step 3: 检查文档与工作树**

Run: `git diff --check && git status --short && ! rg -n "[T]BD|[T]ODO|[待]补充" docs/superpowers/specs/2026-07-11-maintenance-cleanup-design.md docs/superpowers/plans/2026-07-11-maintenance-cleanup.md`

Expected: 整条命令退出码 0；`git diff --check` 成功，`git status --short`
以只读方式显示当前工作树状态，且无占位符匹配。

- [x] **Step 4: 写入执行记录并勾选完成项**

在本计划末尾记录日期、定向测试数量、完整测试结果、环境受限项和仍保留的 Starlette 警告。只勾选有命令输出证据的步骤。

- [x] **Step 5: 提交**

```bash
git add README.md app/services/synthesize.py tests/test_settings_api.py tests/test_synthesize_service.py docs/superpowers
git commit -m "fix: resolve maintenance cleanup backlog"
```

---

## 执行记录

- Tasks 1–4 的勾选依据分别来自 `.superpowers/sdd/task-1-report.md`
  至 `task-4-report.md` 的已运行命令：Task 1 记录 Keychain 失败复现、
  7 项 Settings 测试及 2 项关键隔离测试通过；Task 2 的指定旧断言
  `rg` 无匹配；Task 3 的指定文档 `rg` 仅命中历史决策，且
  前端标记测试 3 passed；Task 4 记录目标警告 RED 失败与修复后
  8 passed、无 pydub warning。这些勾选不表示本次文档归档重跑了
  历史 RED 步骤。
- 2026-07-11 Task 4：已通过子进程回归测试确认导入 `app.services.synthesize`
  不再触发 pydub 的 ffmpeg 探测警告，并保留 `AudioSegment.converter` 指向
  imageio-ffmpeg 内置二进制。
- Starlette 警告决策：警告来自 FastAPI 0.139 暂时仍导出基于旧 httpx 的
  `TestClient`；本轮不升级核心依赖，后续在 FastAPI 官方支持的迁移路径稳定后
  单独处理。
- 2026-07-11 Task 5：worktree 未包含 `.venv`，因此全部 pytest 命令使用
  `<项目根目录>/.venv/bin/pytest`。不依赖 socket bind 的
  回归测试分别为 107 passed，以及 2 passed、1 deselected，共执行 109 项；
  两组命令均为退出码 0。
- 完整测试在受限沙箱内为 109 passed、1 failed，唯一失败是
  `test_find_free_port_returns_valid_port` 在绑定 `127.0.0.1` 随机端口时收到
  `PermissionError: [Errno 1] Operation not permitted`；未修改 `find_free_port()`。
  在非沙箱环境复核为 110 passed，退出码 0。
- 工作树检查使用只读的 `git status --short`；`git diff --check` 成功，
  并使用反向判定的 `[T]BD|[T]ODO|[待]补充` 扫描设计与计划文档。
  无占位符匹配时整条命令退出码 0。
- 每次 pytest 运行均仅出现 1 条 `StarletteDeprecationWarning`，无其他
  警告类型。
