# VoiceMax 项目骨架与基础设施 Implementation Plan

> **状态说明（2026-07-10）：** 本计划已完成。正文中未勾选的逐步步骤保留为原始 TDD 执行模板，不表示当前仍未实施；完成状态以文末“完成标准”和提交历史为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建 VoiceMax 项目骨架——路径与 JSON 配置管理、Keychain 密钥存储、SQLite 数据层、MiniMax 客户端封装（含统一记账）、FastAPI + pywebview 应用外壳与前端导航骨架，为后续「配置页/工作台/音色库/报表」四个功能模块提供可复用基础设施。

**Architecture:** pywebview 提供原生 Mac 窗口外壳，FastAPI 在后台线程启动并通过 `http://127.0.0.1:<随机端口>` 提供服务；所有 MiniMax API 调用统一经过 `app/services/minimax_client.py` 一个出口，成功响应后在该出口内直接写入 SQLite `usage_log`，避免遗漏记账。

**Tech Stack:** Python 3.13、FastAPI、uvicorn、pywebview、httpx、keyring（macOS Keychain）、SQLite（标准库 `sqlite3`）、Pydantic 2；测试用 pytest + pytest-asyncio + respx（不打真实 API）。

---

## 前置说明

- 仓库当前为空骨架（仅 `docs/` 和 `.gitignore`），本计划从零创建 `app/`、`web/`、`tests/`。
- 本计划**不实现**任何具体业务功能（润色/合成/克隆/设计/用量报表），只搭建后续四个功能计划共用的基础设施。四个功能模块将在各自独立的计划中新增 `app/api/*.py` 和 `app/services/*.py`。
- 依赖版本已通过 `pip download` 核实为当前 PyPI 最新版本（核实日期 2026-07-08），避免臆造版本号。

## File Structure

- Create: `requirements.txt` — 依赖声明（版本锁定）
- Create: `pytest.ini` — pytest 配置（`testpaths`、`asyncio_mode`）
- Create: `app/__init__.py` — 包标记
- Create: `app/models.py` — 共享 Pydantic 模型（`AppConfig`）
- Create: `app/config.py` — 应用目录路径、JSON 配置读写、Keychain 密钥读写
- Create: `app/db/__init__.py` — 包标记 + `get_db_path()` / `get_connection()` / `init_db()`
- Create: `app/db/schema.py` — 三张表的建表 SQL
- Create: `app/db/usage_repo.py` — `insert_usage_log()`，供 `minimax_client` 记账调用
- Create: `app/services/__init__.py` — 包标记
- Create: `app/services/minimax_client.py` — httpx 封装、错误分类、统一记账
- Create: `app/main.py` — FastAPI app 工厂、健康检查路由、静态文件挂载、后台线程启动、pywebview 入口
- Create: `web/index.html` — 四栏导航骨架（配置/工作台/音色库/报表）
- Create: `web/css/style.css` — 基础布局样式
- Create: `web/js/app.js` — 导航切换 + 健康检查探测
- Create: `tests/conftest.py` — `isolated_app_dir` / `db` fixture
- Create: `tests/test_config.py`
- Create: `tests/test_db.py`
- Create: `tests/test_minimax_client.py`
- Create: `tests/test_main.py`
- Create: `README.md`

---

### Task 1: 项目骨架与依赖声明

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `app/__init__.py`
- Create: `app/services/__init__.py`

- [ ] **Step 1: 写依赖声明**

```text
fastapi==0.139.0
uvicorn[standard]==0.50.2
pywebview==6.2.1
httpx==0.28.1
keyring==25.7.0
pydub==0.25.1
audioop-lts==0.2.2; python_version>='3.13'
pydantic==2.13.4
pytest==9.1.1
pytest-asyncio==1.4.0
respx==0.23.1
```

> `audioop-lts` 是必需项：Python 3.13 移除了标准库 `audioop`，`pydub` 依赖它做音频处理；未安装时 `import pydub` 会抛 `ModuleNotFoundError`。

保存为 `requirements.txt`。

- [ ] **Step 2: 写 pytest 配置**

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
```

保存为 `pytest.ini`。

- [ ] **Step 3: 创建包标记文件**

`app/__init__.py`（空文件）。

`app/services/__init__.py`（空文件）。

- [ ] **Step 4: 创建虚拟环境并安装依赖**

Run:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -c "import fastapi, uvicorn, webview, httpx, keyring, pydub, pydantic, pytest, respx; print('deps ok')"
```
Expected: 打印 `deps ok`，无报错。

- [ ] **Step 5: 提交**

```bash
git add requirements.txt pytest.ini app/__init__.py app/services/__init__.py .gitignore
git commit -m "chore: 初始化项目骨架与依赖声明"
```

---

### Task 2: 路径与 JSON 配置管理

**Files:**
- Create: `app/models.py`
- Create: `app/config.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 写测试 fixture**

```python
import pytest


@pytest.fixture
def isolated_app_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VOICEMAX_APP_DIR", str(tmp_path))
    return tmp_path
```

保存为 `tests/conftest.py`。

- [ ] **Step 2: 写失败的测试**

```python
from app.config import get_app_dir, get_config_path, load_config, save_config
from app.models import AppConfig


def test_get_app_dir_creates_directory(isolated_app_dir):
    result = get_app_dir()

    assert result == isolated_app_dir
    assert result.exists()


def test_load_config_returns_defaults_when_missing(isolated_app_dir):
    config = load_config()

    assert config.default_model == "speech-2.8-hd"
    assert config.default_format == "mp3"
    assert config.default_sample_rate == 32000


def test_save_and_load_config_round_trip(isolated_app_dir):
    config = AppConfig(
        default_model="speech-2.8-turbo",
        default_format="wav",
        default_sample_rate=16000,
        save_dir="/tmp/out",
    )

    save_config(config)
    loaded = load_config()

    assert loaded == config
    assert get_config_path().exists()


def test_load_config_returns_defaults_on_corrupt_json(isolated_app_dir):
    get_config_path().parent.mkdir(parents=True, exist_ok=True)
    get_config_path().write_text("not valid json", encoding="utf-8")

    config = load_config()

    assert config == AppConfig()
```

保存为 `tests/test_config.py`。

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/test_config.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.config'`（或 `app.models`）。

- [ ] **Step 4: 实现 AppConfig 模型**

```python
from pathlib import Path

from pydantic import BaseModel, Field


def _default_save_dir() -> str:
    return str(Path.home() / "Music" / "VoiceMax")


class AppConfig(BaseModel):
    default_model: str = "speech-2.8-hd"
    default_format: str = "mp3"
    default_sample_rate: int = 32000
    save_dir: str = Field(default_factory=_default_save_dir)
```

保存为 `app/models.py`。

- [ ] **Step 5: 实现配置读写**

```python
import json
import os
from pathlib import Path

from app.models import AppConfig


def get_app_dir() -> Path:
    override = os.environ.get("VOICEMAX_APP_DIR")
    base = Path(override) if override else Path.home() / "Library" / "Application Support" / "VoiceMax"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_config_path() -> Path:
    return get_app_dir() / "config.json"


def load_config() -> AppConfig:
    path = get_config_path()
    if not path.exists():
        return AppConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return AppConfig()
    return AppConfig(**data)


def save_config(config: AppConfig) -> None:
    path = get_config_path()
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
```

保存为 `app/config.py`。

- [ ] **Step 6: 运行测试确认通过**

Run: `pytest tests/test_config.py -v`
Expected: 4 passed。

- [ ] **Step 7: 提交**

```bash
git add app/models.py app/config.py tests/conftest.py tests/test_config.py
git commit -m "feat: 实现应用目录与 JSON 配置读写"
```

---

### Task 3: Keychain 密钥管理

**Files:**
- Modify: `app/config.py`
- Create: `tests/test_keychain.py`

- [ ] **Step 1: 写失败的测试（用假 keyring 后端，不碰真实 Keychain）**

```python
import keyring

from app.config import delete_api_key, get_api_key, set_api_key


class FakeKeyring:
    def __init__(self):
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self._store.get((service, username))

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def delete_password(self, service, username):
        key = (service, username)
        if key not in self._store:
            raise keyring.errors.PasswordDeleteError("not found")
        del self._store[key]


def test_set_and_get_api_key(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(keyring, "get_password", fake.get_password)
    monkeypatch.setattr(keyring, "set_password", fake.set_password)

    set_api_key("sk-test-123")

    assert get_api_key() == "sk-test-123"


def test_get_api_key_returns_none_when_missing(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(keyring, "get_password", fake.get_password)

    assert get_api_key() is None


def test_delete_api_key_removes_value(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(keyring, "get_password", fake.get_password)
    monkeypatch.setattr(keyring, "set_password", fake.set_password)
    monkeypatch.setattr(keyring, "delete_password", fake.delete_password)
    set_api_key("sk-test-123")

    delete_api_key()

    assert get_api_key() is None


def test_delete_api_key_ignores_missing_key(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(keyring, "delete_password", fake.delete_password)

    delete_api_key()
```

保存为 `tests/test_keychain.py`。

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_keychain.py -v`
Expected: FAIL，`ImportError: cannot import name 'get_api_key' from 'app.config'`。

- [ ] **Step 3: 实现 Keychain 读写**

在 `app/config.py` 顶部添加 import，文件末尾追加：

```python
import keyring
```

```python
KEYRING_SERVICE = "VoiceMax"
KEYRING_USERNAME = "minimax_api_key"


def get_api_key() -> str | None:
    return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)


def set_api_key(api_key: str) -> None:
    keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, api_key)


def delete_api_key() -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except keyring.errors.PasswordDeleteError:
        pass
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_keychain.py -v`
Expected: 4 passed。

- [ ] **Step 5: 提交**

```bash
git add app/config.py tests/test_keychain.py
git commit -m "feat: 新增 Keychain API Key 读写"
```

---

### Task 4: SQLite 数据层

**Files:**
- Create: `app/db/__init__.py`
- Create: `app/db/schema.py`
- Create: `app/db/usage_repo.py`
- Modify: `tests/conftest.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: 扩展 fixture，加入已初始化的数据库**

在 `tests/conftest.py` 末尾追加：

```python
@pytest.fixture
def db(isolated_app_dir):
    from app.db import init_db

    init_db()
    return isolated_app_dir
```

- [ ] **Step 2: 写失败的测试**

```python
from app.db import get_connection, init_db
from app.db.usage_repo import insert_usage_log


def test_init_db_creates_all_tables(db):
    with get_connection() as conn:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

    assert {"usage_log", "voices", "projects"}.issubset(tables)


def test_insert_usage_log_stores_row(db):
    row_id = insert_usage_log(feature="synthesize", model="speech-2.8-hd", characters=120, voice_id="voice-1")

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM usage_log WHERE id = ?", (row_id,)).fetchone()

    assert row["feature"] == "synthesize"
    assert row["characters"] == 120
    assert row["status"] == "success"


def test_insert_usage_log_defaults_status_success(db):
    insert_usage_log(feature="polish", model="abab-chat")

    with get_connection() as conn:
        row = conn.execute("SELECT status FROM usage_log ORDER BY id DESC LIMIT 1").fetchone()

    assert row["status"] == "success"


def test_init_db_is_idempotent(db):
    init_db()
    init_db()

    with get_connection() as conn:
        tables = [
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usage_log'")
        ]

    assert tables == ["usage_log"]
```

保存为 `tests/test_db.py`。

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/test_db.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.db'`。

- [ ] **Step 4: 实现建表 SQL**

```python
SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS usage_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        feature TEXT NOT NULL,
        model TEXT,
        characters INTEGER,
        tokens INTEGER,
        voice_id TEXT,
        cost_estimate REAL,
        status TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS voices (
        voice_id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        name TEXT,
        note TEXT,
        sample_path TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        source_text TEXT,
        annotated_text TEXT,
        updated_at TEXT NOT NULL
    )
    """,
]
```

保存为 `app/db/schema.py`。

- [ ] **Step 5: 实现连接管理与初始化**

```python
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import get_app_dir
from app.db.schema import SCHEMA_STATEMENTS


def get_db_path() -> Path:
    return get_app_dir() / "voicemax.db"


@contextmanager
def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
```

保存为 `app/db/__init__.py`。

- [ ] **Step 6: 实现用量写入**

```python
from datetime import datetime, timezone

from app.db import get_connection


def insert_usage_log(
    *,
    feature: str,
    model: str | None = None,
    characters: int | None = None,
    tokens: int | None = None,
    voice_id: str | None = None,
    cost_estimate: float | None = None,
    status: str = "success",
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO usage_log (timestamp, feature, model, characters, tokens, voice_id, cost_estimate, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                feature,
                model,
                characters,
                tokens,
                voice_id,
                cost_estimate,
                status,
            ),
        )
        return cursor.lastrowid
```

保存为 `app/db/usage_repo.py`。

- [ ] **Step 7: 运行测试确认通过**

Run: `pytest tests/test_db.py -v`
Expected: 4 passed。

- [ ] **Step 8: 提交**

```bash
git add app/db tests/conftest.py tests/test_db.py
git commit -m "feat: 实现 SQLite 数据层与用量写入"
```

---

### Task 5: MiniMax 客户端基础封装

**Files:**
- Create: `app/services/minimax_client.py`
- Create: `tests/test_minimax_client.py`

> 说明：本任务只搭建通用请求/错误分类/记账机制，不涉及任何具体业务端点（T2A/克隆/设计/润色），这些将在各自功能计划中调用 `MiniMaxClient.request_json`。`base_url` 与真实业务路径需在功能计划实现时对照 MiniMax 官方文档确认。

- [ ] **Step 1: 写失败的测试**

```python
import httpx
import pytest
import respx

from app.db import get_connection
from app.services.minimax_client import (
    MiniMaxAuthError,
    MiniMaxClient,
    MiniMaxRateLimitError,
    MiniMaxTimeoutError,
)

BASE_URL = "https://fake.minimax.test"


@pytest.mark.asyncio
@respx.mock
async def test_request_json_returns_data_on_success(db):
    respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(
            200, json={"base_resp": {"status_code": 0, "status_msg": "success"}, "data": "ok"}
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    result = await client.request_json("POST", "/v1/fake", json={"a": 1})

    assert result["data"] == "ok"


@pytest.mark.asyncio
@respx.mock
async def test_request_json_records_usage_when_feature_given(db):
    respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(
            200,
            json={"base_resp": {"status_code": 0, "status_msg": "success"}, "usage_characters": 42},
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    await client.request_json("POST", "/v1/fake", json={"a": 1}, feature="synthesize", model="speech-2.8-hd")

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM usage_log ORDER BY id DESC LIMIT 1").fetchone()

    assert row["feature"] == "synthesize"
    assert row["model"] == "speech-2.8-hd"
    assert row["characters"] == 42


@pytest.mark.asyncio
@respx.mock
async def test_request_json_does_not_record_usage_without_feature(db):
    respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(
            200,
            json={"base_resp": {"status_code": 0, "status_msg": "success"}, "usage_characters": 42},
        )
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    await client.request_json("POST", "/v1/fake", json={"a": 1})

    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM usage_log").fetchone()["c"]

    assert count == 0


@pytest.mark.asyncio
@respx.mock
async def test_request_json_raises_auth_error_on_1004(db):
    respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(200, json={"base_resp": {"status_code": 1004, "status_msg": "鉴权失败"}})
    )
    client = MiniMaxClient(api_key="bad-key", base_url=BASE_URL)

    with pytest.raises(MiniMaxAuthError):
        await client.request_json("POST", "/v1/fake")


@pytest.mark.asyncio
@respx.mock
async def test_request_json_raises_rate_limit_error_on_1002(db):
    respx.post(f"{BASE_URL}/v1/fake").mock(
        return_value=httpx.Response(200, json={"base_resp": {"status_code": 1002, "status_msg": "触发限流"}})
    )
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    with pytest.raises(MiniMaxRateLimitError):
        await client.request_json("POST", "/v1/fake")


@pytest.mark.asyncio
@respx.mock
async def test_request_json_raises_timeout_error(db):
    respx.post(f"{BASE_URL}/v1/fake").mock(side_effect=httpx.TimeoutException("timeout"))
    client = MiniMaxClient(api_key="test-key", base_url=BASE_URL)

    with pytest.raises(MiniMaxTimeoutError):
        await client.request_json("POST", "/v1/fake")
```

保存为 `tests/test_minimax_client.py`。

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_minimax_client.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.minimax_client'`。

- [ ] **Step 3: 实现客户端**

```python
from __future__ import annotations

import httpx

from app.db.usage_repo import insert_usage_log


class MiniMaxError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class MiniMaxAuthError(MiniMaxError):
    pass


class MiniMaxRateLimitError(MiniMaxError):
    pass


class MiniMaxTimeoutError(MiniMaxError):
    pass


class MiniMaxClient:
    def __init__(self, api_key: str, base_url: str = "https://api.minimax.chat", timeout: float = 30.0):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        feature: str | None = None,
        model: str | None = None,
        voice_id: str | None = None,
    ) -> dict:
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(method, url, headers=headers, json=json, params=params)
        except httpx.TimeoutException as exc:
            raise MiniMaxTimeoutError("请求超时") from exc

        data = response.json()
        base_resp = data.get("base_resp", {})
        status_code = base_resp.get("status_code", 0)
        status_msg = base_resp.get("status_msg", "MiniMax 接口错误")

        if status_code == 1004:
            raise MiniMaxAuthError(status_msg, status_code=status_code)
        if status_code == 1002:
            raise MiniMaxRateLimitError(status_msg, status_code=status_code)
        if status_code != 0:
            raise MiniMaxError(status_msg, status_code=status_code)

        if feature is not None:
            characters = data.get("usage_characters")
            insert_usage_log(feature=feature, model=model, characters=characters, voice_id=voice_id, status="success")

        return data
```

保存为 `app/services/minimax_client.py`。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_minimax_client.py -v`
Expected: 6 passed。

- [ ] **Step 5: 提交**

```bash
git add app/services/minimax_client.py tests/test_minimax_client.py
git commit -m "feat: 实现 MiniMax 客户端封装与统一记账"
```

---

### Task 6: 前端导航骨架

**Files:**
- Create: `web/index.html`
- Create: `web/css/style.css`
- Create: `web/js/app.js`

- [ ] **Step 1: 写页面骨架**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>VoiceMax</title>
  <link rel="stylesheet" href="/css/style.css" />
</head>
<body>
  <div class="app-shell">
    <nav class="sidebar">
      <div class="brand">VoiceMax</div>
      <ul class="nav-list">
        <li class="nav-item active" data-page="settings">配置</li>
        <li class="nav-item" data-page="studio">工作台</li>
        <li class="nav-item" data-page="voices">音色库</li>
        <li class="nav-item" data-page="usage">报表</li>
      </ul>
      <div class="health-indicator" id="health-indicator">检测中...</div>
    </nav>
    <main class="content" id="content">
      <p>页面内容占位，后续模块开发中填充。</p>
    </main>
  </div>
  <script src="/js/app.js"></script>
</body>
</html>
```

保存为 `web/index.html`。

- [ ] **Step 2: 写基础样式**

```css
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, "PingFang SC", sans-serif;
  color: #1d1d1f;
}

.app-shell {
  display: flex;
  height: 100vh;
}

.sidebar {
  width: 200px;
  background: #f5f5f7;
  border-right: 1px solid #d2d2d7;
  display: flex;
  flex-direction: column;
  padding: 16px 0;
}

.brand {
  font-weight: 600;
  font-size: 18px;
  padding: 0 20px 16px;
}

.nav-list {
  list-style: none;
  flex: 1;
}

.nav-item {
  padding: 10px 20px;
  cursor: pointer;
  font-size: 14px;
}

.nav-item.active {
  background: #d2d2d7;
  font-weight: 600;
}

.health-indicator {
  padding: 10px 20px;
  font-size: 12px;
  color: #86868b;
}

.health-indicator.ok {
  color: #2ea043;
}

.content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}
```

保存为 `web/css/style.css`。

- [ ] **Step 3: 写导航切换与健康检查脚本**

```javascript
function switchPage(page) {
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.page === page);
  });
}

function checkHealth() {
  const indicator = document.getElementById("health-indicator");
  fetch("/api/health")
    .then((response) => response.json())
    .then((data) => {
      const isOk = data.status === "ok";
      indicator.textContent = isOk ? "服务正常" : "服务异常";
      indicator.classList.toggle("ok", isOk);
    })
    .catch(() => {
      indicator.textContent = "无法连接";
      indicator.classList.remove("ok");
    });
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => switchPage(item.dataset.page));
  });
  checkHealth();
});
```

保存为 `web/js/app.js`。

- [ ] **Step 4: 验证静态文件内容**

Run:
```bash
python3 -c "
from pathlib import Path
html = Path('web/index.html').read_text()
assert html.count('nav-item') == 4
assert 'VoiceMax' in html
print('web assets ok')
"
```
Expected: 打印 `web assets ok`。

- [ ] **Step 5: 提交**

```bash
git add web
git commit -m "feat: 搭建前端导航骨架"
```

---

### Task 7: FastAPI 应用工厂 + pywebview 入口

**Files:**
- Create: `app/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: 写失败的测试**

```python
from fastapi.testclient import TestClient

from app.main import create_app, find_free_port


def test_health_endpoint_returns_ok():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_static_index_is_served():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "VoiceMax" in response.text


def test_find_free_port_returns_valid_port():
    port = find_free_port()

    assert isinstance(port, int)
    assert 1024 <= port <= 65535
```

保存为 `tests/test_main.py`。

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_main.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.main'`。

- [ ] **Step 3: 实现应用工厂与启动入口**

```python
import socket
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def create_app() -> FastAPI:
    app = FastAPI(title="VoiceMax")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="static")
    return app


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run_server(app: FastAPI, port: int) -> None:
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def main() -> None:
    import webview

    init_db()
    app = create_app()
    port = find_free_port()

    server_thread = threading.Thread(target=run_server, args=(app, port), daemon=True)
    server_thread.start()
    time.sleep(0.5)

    webview.create_window("VoiceMax", f"http://127.0.0.1:{port}")
    webview.start()


if __name__ == "__main__":
    main()
```

保存为 `app/main.py`。

`webview` 延迟导入在 `main()` 内部，使 `create_app`/`find_free_port` 可在无 GUI 环境下被测试直接导入。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_main.py -v`
Expected: 3 passed。

- [ ] **Step 5: 提交**

```bash
git add app/main.py tests/test_main.py
git commit -m "feat: 实现 FastAPI 应用工厂与 pywebview 启动入口"
```

---

### Task 8: 联调、文档与收尾

**Files:**
- Create: `README.md`

- [ ] **Step 1: 运行完整测试套件**

Run: `pytest -v`
Expected: 全部通过（Task 2~7 累计 21 个测试用例），无失败。

- [ ] **Step 2: 写 README**

````markdown
# VoiceMax

个人自用 Mac 桌面 App，基于 MiniMax API 提供语音合成、音色克隆、音色设计能力。数据全部本地存储。

## 环境要求

- macOS
- Python 3.13+
- ffmpeg（后续 `pydub` 音频拼接依赖，`brew install ffmpeg`）

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 运行

```bash
python3 -m app.main
```

启动后会弹出原生窗口，后端 FastAPI 在本地随机端口后台运行。

## 测试

```bash
pytest -v
```

测试使用 `respx` 拦截 MiniMax 请求，不消耗真实额度。

## 项目结构

- `app/` — 后端：FastAPI 路由、业务服务、SQLite 数据层
- `web/` — 前端静态资源（原生 HTML/CSS/JS）
- `tests/` — pytest 测试

## 数据存储位置

`~/Library/Application Support/VoiceMax/`（配置 JSON、SQLite 数据库）；API Key 存 macOS Keychain，不落明文。
````

保存为 `README.md`。

- [ ] **Step 3: 手动验证应用可启动（可选，非自动化）**

Run: `python3 -m app.main`
Expected: 弹出标题为 "VoiceMax" 的窗口，左侧显示四个导航项，"检测中..." 在 1 秒内变为绿色 "服务正常"。手动关闭窗口结束验证。

- [ ] **Step 4: 提交**

```bash
git add README.md
git commit -m "docs: 补充 README 安装与运行说明"
```

---

## 完成标准

- [x] `pytest -v` 全部通过（21 个测试：Task2 四个 + Task3 四个 + Task4 四个 + Task5 六个 + Task7 三个）
- [x] `python3 -m app.main` 可正常弹出窗口并显示导航骨架
- [x] `app/config.py`、`app/db/`、`app/services/minimax_client.py` 均可被后续四个功能计划直接复用，无需改动接口签名
