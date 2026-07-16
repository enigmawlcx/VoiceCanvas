# GitHub 私有仓库发布前审计报告（历史记录）

> 本文记录 2026-07-12 的 private 仓库发布准备，不能代表当前公开发布状态。最新结论见 [OPEN_SOURCE_PREFLIGHT_REPORT.md](OPEN_SOURCE_PREFLIGHT_REPORT.md)。

审计日期：2026-07-12  
目标：将 VoiceMax 作为私有仓库上传前的本地准备  
状态：本地文件已准备；按用户确认重建为单提交历史，尚未连接新仓库或上传

## 审计范围

本次检查了当前工作区、Git 已跟踪文件、全部本地分支可达历史、忽略状态、依赖、测试、构建脚本，以及以下人工维护文档：

- `README.md`
- `docs/superpowers/specs/` 下 7 份既有规格/竣工文档与本次发布前规格
- `docs/superpowers/plans/` 下 4 份既有实施/维护计划与本次发布前计划
- `VoiceMax.spec`
- `scripts/build_app.sh`
- `scripts/generate_app_icon.sh`
- `requirements.txt`
- `pytest.ini`

历史计划中的代码块和未勾选 TDD 步骤属于执行记录；带有“已完成/历史记录”状态说明的内容不作为当前待办。当前功能、技术栈、配置存储、测试和构建描述已与源码及脚本交叉核对。

## 本地修改

- 完善 `.gitignore`：覆盖 Python 缓存、测试/检查缓存、虚拟环境、本地环境变量、数据库、日志、构建/发行产物、图标临时目录、macOS 元数据、编辑器文件及本地工作树。
- 新增 `.gitattributes`：文本文件统一使用 LF；图片、图标、压缩包、音频和数据库按二进制处理。
- 补充 `README.md` 的 macOS 打包方式、架构限制、产物位置，以及 `scripts/`、`docs/` 结构说明。
- 将维护计划中的个人绝对路径替换为 `<项目根目录>` 表示法。
- 新增本次审计规格、实施计划和本报告。
- 未新增许可证：目标仓库为私有仓库，当前没有开放源代码授权需求。

## 敏感信息结论

- 当前已跟踪内容未发现真实 API Key、GitHub Token 或私钥。
- 源码、测试和历史计划中存在 `api_key` 字段名及 `sk-test`、`test-key` 等测试占位值；这些是明确的测试数据，不是真实凭据。
- API Key 的生产存储使用 macOS Keychain；配置 JSON 与仓库文件不保存明文密钥。
- 当前工作区未发现准备纳入 Git 的本地数据库或 `.env` 文件。

## Git 历史与远端风险

审计时发现仓库曾配置以下远端：

```text
origin  <历史 private 仓库地址>
```

用户已确认改用新的私有仓库；历史重建时移除该旧远端配置，全程不访问旧远端。

旧历史的凭据模式扫描未发现疑似真实密钥，但曾保留个人绝对路径和已删除的临时审查报告。用户已授权清空 `main` 历史，以当前审计后的文件快照创建全新首次提交；因此这些旧内容不会从新 `main` 可达，也不会在仅推送 `main` 时上传。

本地还存在 `codex/project-handoff-docs` 分支，其中保留旧历史。用户已明确仅上传 `main`，因此首次上传禁止使用 `git push --all`，也不为该分支创建远端引用。

## 建议纳入 Git

- 根目录的源码入口、依赖、测试配置、README、PyInstaller spec、`.gitignore` 与 `.gitattributes`
- `app/` 后端源码
- `web/` 前端静态资源
- `tests/` 测试
- `scripts/` 构建和图标脚本
- `assets/app-icon.png` 与 `assets/VoiceMax.icns`
- `docs/` 下的设计、实施和审计记录

## 必须排除

- `.venv/`、`.venv-x86/` 及其他本地虚拟环境
- `__pycache__/`、`*.pyc`、`.pytest_cache/` 及检查工具缓存
- `build/`、`dist/`、`*.app`、`*.dmg`、`*.pkg`
- `.env*`（仅允许未来显式创建的 `.env.example`）
- `*.db`、`*.sqlite*`、日志和本地应用数据
- `.worktrees/`、`.superpowers/` 本地执行产物
- `.DS_Store`、编辑器配置和临时文件

## 验证记录

- 沙箱内完整测试：109 passed、1 failed；唯一失败为沙箱禁止绑定 `127.0.0.1` 随机端口。
- 非沙箱完整测试：110 passed、1 条 `StarletteDeprecationWarning`，退出码 0。
- 最终非沙箱完整测试：110 passed、1 条 `StarletteDeprecationWarning`，退出码 0。
- `git check-ignore` 已确认虚拟环境、构建/发行目录、pytest 缓存、工作树、Python 缓存、数据库、日志和本地环境文件均由明确规则排除；`.env.example` 不会被排除。
- `git check-attr` 已确认 Python、Shell 和 Markdown 样例使用 LF，PNG 与 ICNS 样例按二进制处理。
- 对当前上传候选重新扫描私钥头、GitHub Token、长格式 `sk-` 凭据和 macOS 用户主目录绝对路径，无命中。
- `git diff --check` 退出码 0；最终状态仅包含本次发布准备相关文档与 Git 配置修改。

## 下一阶段必须确认

1. 提供新的 GitHub 私有仓库名称，并确认所属 GitHub 账号或组织。
2. 新仓库创建后，只为新地址配置 `origin`。
3. 仅推送新 `main`，不上传 `codex/project-handoff-docs`。
