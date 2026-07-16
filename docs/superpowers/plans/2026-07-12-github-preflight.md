# GitHub 私有仓库发布前审计实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保持仓库本地未提交且不连接 GitHub 的前提下，完成全部人工维护文档、敏感信息、Git 纳入范围和项目健康度审计，并生成必要的 Git 配置与审计报告。

**Architecture:** 以 Git 已跟踪清单为上传候选基线，以源码、依赖、测试和构建脚本作为文档事实来源。审计分为证据采集、文档修正、Git 边界收紧和最终验证四部分，所有修改仅限发布准备相关文件。

**Tech Stack:** Git、Python 3.13、pytest、PyInstaller、Markdown、Shell

## Global Constraints

- 目标仓库为私有仓库，不创建开源许可证。
- 不连接或登录 GitHub，不创建远端仓库，不配置 `origin`。
- 不执行 `git add`、`git commit`、`git push` 或历史改写。
- 不删除本地缓存、虚拟环境、构建产物、发行包或工作树。
- 最终保留本地未提交修改，等待用户确认下一阶段。

---

### Task 1: 建立审计证据基线

**Files:**
- Inspect: `.gitignore`
- Inspect: `README.md`
- Inspect: `requirements.txt`
- Inspect: `pytest.ini`
- Inspect: `VoiceMax.spec`
- Inspect: `scripts/build_app.sh`
- Inspect: `scripts/generate_app_icon.sh`
- Inspect: `docs/superpowers/**/*.md`

**Interfaces:**
- Consumes: 当前工作区、Git 索引、Git 历史和忽略规则
- Produces: 文档清单、跟踪状态、敏感信息命中和事实核对表

- [x] **Step 1: 枚举上传候选与忽略内容**

Run: `git ls-files && git status --short --ignored`

Expected: 明确列出已跟踪文件、新文件和已忽略的虚拟环境、缓存、构建产物及工作树。

- [x] **Step 2: 读取全部人工维护文档及配置说明**

Run: `for f in README.md requirements.txt pytest.ini VoiceMax.spec scripts/*.sh docs/superpowers/**/*.md; do sed -n '1,9999p' "$f"; done`

Expected: 所有目标文件均可读取，不遗漏根目录说明、规格、计划和脚本说明。

- [x] **Step 3: 收集源码事实**

Run: `rg -n "FastAPI|uvicorn|webview|keyring|MiniMax|pytest|PyInstaller|VOICEMAX|API_KEY|GROUP_ID|database|sqlite" app run.py tests scripts requirements.txt VoiceMax.spec`

Expected: 得到启动方式、配置存储、接口、构建和测试行为的可核对证据。

- [x] **Step 4: 扫描敏感信息和个人路径**

Run: `git grep -nEI "([B]EGIN (RSA |OPENSSH |EC )?PRIVATE KEY|api[_-]?key|secret|token|password|/[U]sers/|[g]hp_[A-Za-z0-9]+|[g]ithub_pat_[A-Za-z0-9_]+|[s]k-[A-Za-z0-9_-]+)"`

Expected: 每个命中均人工区分字段名、测试占位符、文档示例和真实凭据。

### Task 2: 修正文档与 Git 纳入规则

**Files:**
- Modify: `README.md`（仅在审计发现与当前实现不一致或缺少必要的私有项目使用说明时）
- Modify: `docs/superpowers/**/*.md`（仅修正事实错误、过时状态或敏感内容）
- Modify: `.gitignore`
- Create: `.gitattributes`（仅在审计证明有必要时）
- Create: `docs/GITHUB_PREFLIGHT_REPORT.md`

**Interfaces:**
- Consumes: Task 1 的事实核对表和风险命中
- Produces: 准确文档、收紧后的上传边界、可复核审计报告

- [x] **Step 1: 修正文档事实错误**

逐项以当前源码和脚本为依据修改运行、测试、配置、构建及功能状态描述；不改写仅用于保留历史决策过程且事实标注清晰的旧计划。

Expected: 当前使用说明可直接执行，历史文档不会被误读为当前状态。

- [x] **Step 2: 完善忽略规则**

确保 `.gitignore` 覆盖：`.venv*/`、`__pycache__/`、`*.py[cod]`、`.pytest_cache/`、`build/`、`dist/`、`.worktrees/`、本地环境文件、数据库、日志、macOS 元数据和编辑器临时文件。

Expected: 当前已发现的本地生成物全部显示为 ignored，且源码、测试、资产和人工文档仍可纳入 Git。

- [x] **Step 3: 判断并生成属性规则**

若仓库同时包含 Shell、Python、Markdown、图片和 macOS 图标，则创建 `.gitattributes`，将文本文件规范为 LF，并将 PNG、ICNS、ZIP、音频和数据库声明为 binary。

Expected: `git check-attr` 对文本和二进制样例返回明确属性。

- [x] **Step 4: 写入审计报告**

报告必须包含：范围、已检查文档、修改摘要、敏感信息结论、Git 历史风险、建议上传清单、必须排除清单、验证结果和下一阶段待确认事项。

Expected: 报告不包含真实凭据值，只描述文件、风险类别和处置状态。

### Task 3: 验证发布准备状态

**Files:**
- Verify: `.gitignore`
- Verify: `.gitattributes`
- Verify: `README.md`
- Verify: `docs/GITHUB_PREFLIGHT_REPORT.md`
- Verify: `docs/superpowers/**/*.md`

**Interfaces:**
- Consumes: Task 2 的全部本地修改
- Produces: 测试证据、上传预览和最终待确认状态

- [x] **Step 1: 验证忽略与属性规则**

Run: `git check-ignore -v .venv .venv-x86 build dist .pytest_cache .worktrees app/__pycache__`

Expected: 每个路径都由明确的 `.gitignore` 规则覆盖。

Run: `git check-attr text eol diff -- README.md app/main.py scripts/build_app.sh assets/app-icon.png assets/VoiceMax.icns`

Expected: 文本样例使用 LF；PNG 与 ICNS 被识别为 binary。

- [x] **Step 2: 重新扫描待上传文件**

Run: `git grep -nEI "([B]EGIN (RSA |OPENSSH |EC )?PRIVATE KEY|/[U]sers/|[g]hp_[A-Za-z0-9]+|[g]ithub_pat_[A-Za-z0-9_]+|[s]k-[A-Za-z0-9_-]+)"`

Expected: 不存在真实凭据或个人绝对路径；如保留字段名和测试占位符，必须记录在报告中。

- [x] **Step 3: 运行完整测试**

Run: `.venv/bin/python -m pytest -q`

Expected: pytest 退出码为 0，无失败测试。

- [x] **Step 4: 审阅最终差异和上传清单**

Run: `git diff --check && git diff --stat && git status --short --ignored && git ls-files`

Expected: 无空白错误；只有发布准备相关修改；生成物仍被忽略；未发生提交或远端配置变化。

- [x] **Step 5: 停止并交付用户确认**

报告本地变更、测试结果、风险和下一阶段建议，不运行任何 `git add`、`git commit`、`git remote add`、`gh repo create` 或 `git push` 命令。
