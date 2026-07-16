# VoiceCanvas Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将应用从 VoiceMax 无损更名为“声绘魔法 / VoiceCanvas”，并让旧数据目录和旧 Keychain 凭据平滑迁移。

**Architecture:** 将品牌常量直接更新在用户可见界面和打包配置中；将有状态兼容逻辑集中放在 `app/config.py`，通过明确的目录选择函数和新旧 Keychain 双读策略隔离迁移风险。先以单元测试锁定迁移行为，再更新无状态品牌文案与构建资源，最后运行全量测试和品牌残留扫描。

**Tech Stack:** Python 3.13、FastAPI、Pydantic、keyring、pytest、原生 HTML、PyInstaller、Bash

## Global Constraints

- 中文界面主品牌固定为 `声绘魔法`。
- 英文品牌名固定为 `VoiceCanvas`，中间不加空格。
- macOS 应用包固定为 `声绘魔法.app`，内部可执行文件固定为 `VoiceCanvas`。
- 新数据目录为 `~/Library/Application Support/VoiceCanvas/`；显式 `VOICEMAX_APP_DIR` 覆盖优先级最高。
- 新旧数据目录同时存在时优先新目录，不自动合并或覆盖。
- 数据目录迁移失败时继续使用旧目录。
- 新 Keychain service 为 `VoiceCanvas`；旧 service `VoiceMax` 只用于回退读取和迁移，不主动删除。
- 已保存的输出目录不改写；仅将新配置默认值改为 `~/Music/VoiceCanvas`。
- 不修改数据库结构、业务 API、UI 布局或内部 JavaScript 命名空间。
- 不改工作区目录名，不批量修改历史设计文档。

---

## File Structure

- `app/config.py`：唯一负责应用数据目录选择、旧目录迁移和 Keychain 凭据兼容。
- `app/models.py`：只负责全新配置的默认输出目录。
- `tests/test_config.py`：覆盖目录选择、迁移、冲突和失败回退。
- `tests/test_keychain.py`：覆盖新凭据优先、旧凭据迁移和写入失败回退。
- `tests/test_main.py`：锁定 FastAPI 用户可见标题。
- `tests/test_frontend_scripts.py`：锁定静态页面品牌文案，同时允许内部 `VoiceMax*` 命名空间保留。
- `app/main.py`、`web/index.html`：更新运行时用户可见品牌。
- `VoiceCanvas.spec`、`scripts/build_app.sh`、`scripts/generate_app_icon.sh`、`assets/VoiceCanvas.icns`：定义发行产物和图标文件命名。
- `README.md`：记录新品牌、产物路径、默认路径及旧版本迁移行为。

### Task 1: 数据目录和默认输出目录迁移

**Files:**
- Modify: `app/config.py`
- Modify: `app/models.py`
- Modify: `tests/test_config.py`

**Interfaces:**
- Consumes: 环境变量 `VOICEMAX_APP_DIR`、`Path.home()`、旧目录 `VoiceMax`。
- Produces: `_default_app_dir() -> Path`、`_legacy_app_dir() -> Path`、`get_app_dir() -> Path`；`AppConfig.save_dir` 的新安装默认值。

- [ ] **Step 1: 写目录迁移失败测试**

在 `tests/test_config.py` 增加 `tmp_path` + `monkeypatch` 测试。测试中删除 `VOICEMAX_APP_DIR`，将 `app.config.Path.home` 替换为 `lambda: tmp_path`，并覆盖以下精确场景：

```python
def test_get_app_dir_migrates_legacy_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("VOICEMAX_APP_DIR", raising=False)
    monkeypatch.setattr("app.config.Path.home", lambda: tmp_path)
    legacy = tmp_path / "Library" / "Application Support" / "VoiceMax"
    legacy.mkdir(parents=True)
    (legacy / "config.json").write_text('{"group_id":"old"}', encoding="utf-8")

    result = get_app_dir()

    assert result == tmp_path / "Library" / "Application Support" / "VoiceCanvas"
    assert (result / "config.json").exists()
    assert not legacy.exists()


def test_get_app_dir_prefers_existing_new_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("VOICEMAX_APP_DIR", raising=False)
    monkeypatch.setattr("app.config.Path.home", lambda: tmp_path)
    legacy = tmp_path / "Library" / "Application Support" / "VoiceMax"
    current = tmp_path / "Library" / "Application Support" / "VoiceCanvas"
    legacy.mkdir(parents=True)
    current.mkdir(parents=True)
    (legacy / "legacy.txt").write_text("old", encoding="utf-8")
    (current / "current.txt").write_text("new", encoding="utf-8")

    assert get_app_dir() == current
    assert (current / "current.txt").read_text() == "new"
    assert (legacy / "legacy.txt").read_text() == "old"


def test_get_app_dir_falls_back_when_migration_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("VOICEMAX_APP_DIR", raising=False)
    monkeypatch.setattr("app.config.Path.home", lambda: tmp_path)
    legacy = tmp_path / "Library" / "Application Support" / "VoiceMax"
    legacy.mkdir(parents=True)

    def fail_replace(self, target):
        raise OSError("denied")

    monkeypatch.setattr("app.config.Path.replace", fail_replace)

    assert get_app_dir() == legacy


def test_default_save_dir_uses_voicecanvas(tmp_path, monkeypatch):
    monkeypatch.setattr("app.models.Path.home", lambda: tmp_path)

    assert AppConfig().save_dir == str(tmp_path / "Music" / "VoiceCanvas")
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_config.py -v`

Expected: 新增测试因仍返回 `VoiceMax` 路径或没有迁移逻辑而 FAIL；既有显式覆盖目录测试继续 PASS。

- [ ] **Step 3: 实现最小目录选择和迁移逻辑**

在 `app/config.py` 中引入日志并将 `get_app_dir()` 改为：

```python
import logging

logger = logging.getLogger(__name__)


def _default_app_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "VoiceCanvas"


def _legacy_app_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "VoiceMax"


def get_app_dir() -> Path:
    override = os.environ.get("VOICEMAX_APP_DIR")
    if override:
        base = Path(override)
        base.mkdir(parents=True, exist_ok=True)
        return base

    current = _default_app_dir()
    legacy = _legacy_app_dir()
    if current.exists():
        return current
    if legacy.exists():
        try:
            return legacy.replace(current)
        except OSError:
            logger.exception("无法将 VoiceMax 数据目录迁移到 VoiceCanvas，继续使用旧目录")
            return legacy
    current.mkdir(parents=True, exist_ok=True)
    return current
```

在 `app/models.py` 中将 `_default_save_dir()` 的末级目录从 `VoiceMax` 改为 `VoiceCanvas`。不要在 `load_config()` 中重写已有 `save_dir`。

- [ ] **Step 4: 运行目录测试并确认通过**

Run: `pytest tests/test_config.py -v`

Expected: 全部 PASS，日志测试场景允许输出一次预期的迁移异常日志。

- [ ] **Step 5: 提交目录迁移**

```bash
git add app/config.py app/models.py tests/test_config.py
git commit -m "feat: migrate VoiceCanvas application data"
```

### Task 2: Keychain 凭据无损迁移

**Files:**
- Modify: `app/config.py`
- Modify: `tests/test_keychain.py`

**Interfaces:**
- Consumes: keyring 的 `get_password(service, username)`、`set_password(service, username, value)`。
- Produces: `KEYRING_SERVICE = "VoiceCanvas"`、`LEGACY_KEYRING_SERVICE = "VoiceMax"`、`KEYRING_CLEARED_SENTINEL`；保持 `get_api_key() -> str | None`、`set_api_key(str) -> None`、`delete_api_key() -> None` 的公开签名不变。

- [ ] **Step 1: 写 Keychain 迁移失败测试**

扩展 `FakeKeyring`，允许指定新 service 写入失败，并增加：

```python
def test_get_api_key_prefers_voicecanvas_value(monkeypatch):
    fake = FakeKeyring()
    fake.set_password("VoiceMax", "minimax_api_key", "old")
    fake.set_password("VoiceCanvas", "minimax_api_key", "new")
    monkeypatch.setattr(keyring, "get_password", fake.get_password)
    monkeypatch.setattr(keyring, "set_password", fake.set_password)

    assert get_api_key() == "new"


def test_get_api_key_migrates_legacy_value(monkeypatch):
    fake = FakeKeyring()
    fake.set_password("VoiceMax", "minimax_api_key", "old")
    monkeypatch.setattr(keyring, "get_password", fake.get_password)
    monkeypatch.setattr(keyring, "set_password", fake.set_password)

    assert get_api_key() == "old"
    assert fake.get_password("VoiceCanvas", "minimax_api_key") == "old"
    assert fake.get_password("VoiceMax", "minimax_api_key") == "old"


def test_get_api_key_uses_legacy_value_when_copy_fails(monkeypatch):
    fake = FakeKeyring()
    fake.set_password("VoiceMax", "minimax_api_key", "old")
    monkeypatch.setattr(keyring, "get_password", fake.get_password)

    def fail_set(service, username, password):
        raise keyring.errors.KeyringError("denied")

    monkeypatch.setattr(keyring, "set_password", fail_set)

    assert get_api_key() == "old"


def test_delete_api_key_does_not_resurrect_legacy_value(monkeypatch):
    fake = FakeKeyring()
    fake.set_password("VoiceMax", "minimax_api_key", "old")
    monkeypatch.setattr(keyring, "get_password", fake.get_password)
    monkeypatch.setattr(keyring, "set_password", fake.set_password)
    monkeypatch.setattr(keyring, "delete_password", fake.delete_password)

    delete_api_key()

    assert get_api_key() is None
    assert fake.get_password("VoiceMax", "minimax_api_key") == "old"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_keychain.py -v`

Expected: 新 service 优先和旧值复制测试 FAIL，因为代码仍只访问 `VoiceMax`。

- [ ] **Step 3: 实现双读与保守迁移**

在 `app/config.py` 中实现：

```python
KEYRING_SERVICE = "VoiceCanvas"
LEGACY_KEYRING_SERVICE = "VoiceMax"
KEYRING_USERNAME = "minimax_api_key"
KEYRING_CLEARED_SENTINEL = "__VOICECANVAS_CLEARED__"


def get_api_key() -> str | None:
    current = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    if current == KEYRING_CLEARED_SENTINEL:
        return None
    if current is not None:
        return current
    legacy = keyring.get_password(LEGACY_KEYRING_SERVICE, KEYRING_USERNAME)
    if legacy is None:
        return None
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, legacy)
    except keyring.errors.KeyringError:
        logger.exception("无法将 VoiceMax API Key 迁移到 VoiceCanvas，继续使用旧凭据")
    return legacy
```

`set_api_key()` 只写新 service。`delete_api_key()` 不删除旧 service，而是在新 service 写入 `KEYRING_CLEARED_SENTINEL`；这样既满足“保留旧项以便版本回退”，也防止用户清除 Key 后旧值在新版中重新出现。哨兵值必须只由配置层解释，`get_api_key()` 对外仍返回 `None`。

- [ ] **Step 4: 运行 Keychain 测试并确认通过**

Run: `pytest tests/test_keychain.py -v`

Expected: 全部 PASS。

- [ ] **Step 5: 提交凭据迁移**

```bash
git add app/config.py tests/test_keychain.py
git commit -m "feat: migrate VoiceCanvas keychain credentials"
```

### Task 3: 运行时品牌文案

**Files:**
- Modify: `tests/test_main.py`
- Modify: `tests/test_frontend_scripts.py`
- Modify: `app/main.py`
- Modify: `web/index.html`

**Interfaces:**
- Consumes: `create_app()`、静态 `web/index.html`。
- Produces: FastAPI 标题 `声绘魔法 / VoiceCanvas`、窗口标题和侧栏主品牌 `声绘魔法`。

- [ ] **Step 1: 写用户可见品牌失败测试**

在 `tests/test_main.py` 增加：

```python
def test_fastapi_uses_voicecanvas_brand():
    assert create_app().title == "声绘魔法 / VoiceCanvas"
```

在 `tests/test_frontend_scripts.py` 增加：

```python
def test_index_uses_voicecanvas_brand():
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")

    assert "<title>声绘魔法</title>" in html
    assert '<span class="brand-name">声绘魔法</span>' in html
    assert 'alt="声绘魔法"' in html
    assert ">VoiceMax<" not in html
```

如果该测试文件还没有 `WEB_DIR`，在文件顶部定义：

```python
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
```

- [ ] **Step 2: 运行品牌测试并确认失败**

Run: `pytest tests/test_main.py tests/test_frontend_scripts.py -v`

Expected: 新增断言因当前标题仍为 `VoiceMax` 而 FAIL。

- [ ] **Step 3: 更新运行时品牌**

- `app/main.py`：`FastAPI(title="声绘魔法 / VoiceCanvas")`；`webview.create_window("声绘魔法", ...)`；中文注释中的产品名改为“声绘魔法”。
- `web/index.html`：`<title>`、Logo `alt`、`.brand-name` 均改为“声绘魔法”。
- 保留 `window.VoiceMaxPages`、`window.VoiceMaxNavigate`、`window.VoiceMaxApiErrors`，不做内部命名空间改动。

- [ ] **Step 4: 运行品牌测试并确认通过**

Run: `pytest tests/test_main.py tests/test_frontend_scripts.py -v`

Expected: 全部 PASS。

- [ ] **Step 5: 提交运行时品牌**

```bash
git add app/main.py web/index.html tests/test_main.py tests/test_frontend_scripts.py
git commit -m "feat: rebrand interface as VoiceCanvas"
```

### Task 4: macOS 构建资源和发行名称

**Files:**
- Rename: `VoiceMax.spec` → `VoiceCanvas.spec`
- Rename: `assets/VoiceMax.icns` → `assets/VoiceCanvas.icns`
- Modify: `VoiceCanvas.spec`
- Modify: `scripts/build_app.sh`
- Modify: `scripts/generate_app_icon.sh`
- Modify: `README.md`

**Interfaces:**
- Consumes: `assets/app-icon.png`、环境变量 `VOICEMAX_TARGET_ARCH`（为构建兼容保留原变量名）。
- Produces: `dist/<arch>/声绘魔法.app`，其中可执行文件为 `Contents/MacOS/VoiceCanvas`。

- [ ] **Step 1: 用 Git 移动构建文件和图标资源**

```bash
git mv VoiceMax.spec VoiceCanvas.spec
git mv assets/VoiceMax.icns assets/VoiceCanvas.icns
```

- [ ] **Step 2: 更新 PyInstaller 配置**

在 `VoiceCanvas.spec` 中设置：

```python
exe = EXE(
    # 保持其他现有参数不变
    name="VoiceCanvas",
)

coll = COLLECT(
    # 保持其他现有参数不变
    name="VoiceCanvas",
)

app = BUNDLE(
    coll,
    name="声绘魔法.app",
    icon=str(project_root / "assets" / "VoiceCanvas.icns"),
    bundle_identifier="com.voicecanvas.app",
    info_plist={
        "CFBundleName": "声绘魔法",
        "CFBundleDisplayName": "声绘魔法",
        # 保持本地化和高分屏现有字段不变
    },
)
```

- [ ] **Step 3: 更新构建和图标脚本**

- `scripts/generate_app_icon.sh`：`ICONSET` 改为 `VoiceCanvas.iconset`，`OUTPUT` 改为 `VoiceCanvas.icns`。
- `scripts/build_app.sh`：PyInstaller 输入改为 `VoiceCanvas.spec`；完成、`du` 和 `lipo` 路径改为 `dist/$ARCH/声绘魔法.app`，其中 `lipo` 指向 `Contents/MacOS/VoiceCanvas`；顶部说明同步更新。
- 保留环境变量 `VOICEMAX_TARGET_ARCH`，避免影响现有外部构建调用；该变量仅为内部构建接口，不是用户可见品牌。

- [ ] **Step 4: 更新 README**

将标题改为 `# 声绘魔法（VoiceCanvas）`，将构建产物写为 `dist/<arch>/声绘魔法.app`，将数据目录说明写清：默认使用 `~/Library/Application Support/VoiceCanvas/`，首次新版启动会迁移旧 `VoiceMax` 数据目录，迁移失败会安全回退；默认输出目录写为 `~/Music/VoiceCanvas`。技术提供方 `MiniMax` 保持原名。

- [ ] **Step 5: 检查静态构建引用**

Run: `rg -n "VoiceMax\.spec|VoiceMax\.icns|VoiceMax\.app|Contents/MacOS/VoiceMax|CFBundleName.*VoiceMax|CFBundleDisplayName.*VoiceMax" VoiceCanvas.spec scripts README.md assets`

Expected: 无输出。允许 `VOICEMAX_TARGET_ARCH` 出现。

- [ ] **Step 6: 运行图标生成脚本**

Run: `scripts/generate_app_icon.sh`

Expected: 输出 `==> 已生成: .../assets/VoiceCanvas.icns`，命令退出码为 0。

- [ ] **Step 7: 提交发行名称**

```bash
git add VoiceCanvas.spec assets/VoiceCanvas.icns scripts/build_app.sh scripts/generate_app_icon.sh README.md
git commit -m "build: rename macOS app to VoiceCanvas"
```

### Task 5: 全量回归和改名验收

**Files:**
- Modify only if verification exposes a defect in files already listed above.

**Interfaces:**
- Consumes: Tasks 1–4 的全部实现。
- Produces: 通过测试、静态品牌扫描和构建配置检查的可实施版本。

- [ ] **Step 1: 运行全量自动化测试**

Run: `pytest -v`

Expected: 全部 PASS，无新增 warning 或 error。

- [ ] **Step 2: 运行 Python 与 Shell 静态检查**

Run: `python -m compileall -q app tests`

Expected: 无输出，退出码 0。

Run: `bash -n scripts/build_app.sh scripts/generate_app_icon.sh`

Expected: 无输出，退出码 0。

- [ ] **Step 3: 扫描用户可见旧品牌残留**

Run: `rg -n "VoiceMax" README.md web/index.html app/main.py VoiceCanvas.spec scripts/build_app.sh scripts/generate_app_icon.sh`

Expected: 只允许以下有意兼容内容：`VOICEMAX_TARGET_ARCH`、`app/main.py` 的内部环境标志（若保留）以及 README 的“从旧 VoiceMax 数据目录迁移”说明；不得出现旧窗口标题、旧侧栏品牌、旧应用包或旧图标路径。

- [ ] **Step 4: 检查 Git 差异和工作树**

Run: `git diff --check && git status --short`

Expected: `git diff --check` 无输出；工作树只显示本任务明确产生且尚未提交的文件，理想状态为空。

- [ ] **Step 5: 如验证产生修复则提交**

仅当步骤 1–4 暴露并修复了缺陷时执行：

```bash
git add app/config.py app/models.py app/main.py web/index.html VoiceCanvas.spec scripts/build_app.sh scripts/generate_app_icon.sh README.md tests
git commit -m "fix: complete VoiceCanvas rename verification"
```
