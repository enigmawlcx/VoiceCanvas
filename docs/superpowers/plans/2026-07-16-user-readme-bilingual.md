# VoiceCanvas Bilingual User README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the Chinese README for end users and add an English README with identical structure, facts, commands, and limitations.

**Architecture:** Treat `README.md` as the Simplified Chinese source document and `README_EN.md` as its English counterpart. Preserve the latest `main` public-release additions for CI, contribution, security, and licensing while moving user onboarding and usage before developer-oriented testing and packaging details.

**Tech Stack:** GitHub-Flavored Markdown, shell-based structural checks, pytest

---

## File Map

- Modify: `README.md` — Simplified Chinese end-user documentation and canonical content order.
- Create: `README_EN.md` — English document mirroring every Chinese section, fact, path, and command.
- Reference only: `app/models.py`, `app/config.py`, `app/main.py`, `app/services/synthesize.py`, `scripts/build_app.sh`, `VoiceCanvas.spec` — authoritative sources for documented behavior.
- Reference only: `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, `LICENSE.zh-CN.md` — public contribution, security, and licensing documents linked by the README.
- Preserve without editing: `.github/` and all application/test files introduced or changed on `main`.

### Task 1: Rewrite the Simplified Chinese README for end users

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Record the pre-existing README additions that must survive the rewrite**

Run:

```bash
git diff -- README.md
```

Expected: the diff contains the GitHub Actions sentence and links to `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, and `LICENSE.zh-CN.md`. Keep all items in the rewritten document.

- [ ] **Step 2: Replace the Chinese README with the approved user-first structure**

Use these level-two headings in this exact order:

```markdown
## 核心功能
## 系统要求
## 安装与启动
## 首次配置
## 基本使用流程
## 音频输出说明
## 数据与隐私
## 测试
## macOS 打包
## 项目结构
## 参与贡献与安全
## 开源许可证
```

The body must contain all of the following verified facts:

```text
声绘魔法（VoiceCanvas）是个人使用的 macOS 桌面应用，通过 MiniMax API 提供语音合成、音色克隆、音色设计和用量报表。
支持 MP3、WAV、FLAC。
MP3 支持 32、64、128、256 kbps CBR；WAV 和 FLAC 不应用 MP3 比特率设置。
每两个成功合成的相邻音频段之间固定插入 1 秒静音，首尾不额外插入静音。
一次生成开始时锁定格式、采样率和比特率，分段、重试和拼接复用同一配置。
API Key 存储在 macOS Keychain；配置和 SQLite 数据默认位于 ~/Library/Application Support/VoiceCanvas/；默认输出目录为 ~/Music/VoiceCanvas。
MiniMax 请求会发送到用户配置的 API 服务地址，因此本地存储不等于离线处理。
```

Keep these commands unchanged:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m app.main
pytest -v
scripts/build_app.sh arm64
scripts/build_app.sh x86_64
```

Document the package path as `dist/<arch>/声绘魔法.app`. Preserve the existing GitHub Actions statement under testing. Under `参与贡献与安全`, require contributors to read `CONTRIBUTING.md`, require unresolved vulnerabilities to be reported privately according to `SECURITY.md`, and prohibit public disclosure of sensitive information. Under `开源许可证`, link `LICENSE` as the MIT License and `LICENSE.zh-CN.md` as a reference-only Chinese translation whose English original controls.

- [ ] **Step 3: Check the Chinese README structure and critical facts**

Run:

```bash
rg -n '^## ' README.md
rg -n '1 秒|32、64、128、256 kbps|声绘魔法\.app|GitHub Actions|CONTRIBUTING\.md|SECURITY\.md|MIT License|LICENSE\.zh-CN\.md|私密报告|不等于离线' README.md
```

Expected: headings appear in the specified order; every critical fact and preserved pre-existing addition has at least one match.

### Task 2: Create a structurally identical English README

**Files:**
- Create: `README_EN.md`

- [ ] **Step 1: Create the English README with one-to-one section mapping**

Use these level-two headings in this exact order:

```markdown
## Core Features
## System Requirements
## Installation and Launch
## First-Time Setup
## Basic Workflow
## Audio Output
## Data and Privacy
## Testing
## macOS Packaging
## Project Structure
## Contributing and Security
## Open-Source License
```

Translate the Chinese content faithfully. Keep paths, filenames, command blocks, formats, bitrates, the one-second silence duration, and product behavior identical. Use `VoiceCanvas` as the English product name. State explicitly that API requests are sent to the configured MiniMax service and local persistence does not mean offline processing.

Include the same GitHub Actions behavior under testing. In `Contributing and Security`, require contributors to read `CONTRIBUTING.md`, require unresolved vulnerabilities to be reported privately according to `SECURITY.md`, and prohibit public disclosure of sensitive information. In `Open-Source License`, link `LICENSE` as the MIT License and `LICENSE.zh-CN.md` as a reference-only Chinese translation whose English original controls.

- [ ] **Step 2: Check the English README structure and critical facts**

Run:

```bash
rg -n '^## ' README_EN.md
rg -n '1 second|32, 64, 128, and 256 kbps|声绘魔法\.app|GitHub Actions|CONTRIBUTING\.md|SECURITY\.md|MIT License|LICENSE\.zh-CN\.md|privately report|offline processing' README_EN.md
```

Expected: headings appear in the specified order and all critical facts have at least one match.

### Task 3: Verify parity and repository health

**Files:**
- Verify: `README.md`
- Verify: `README_EN.md`

- [ ] **Step 1: Verify heading counts and command parity**

Run:

```bash
test "$(rg -c '^## ' README.md)" -eq 12
test "$(rg -c '^## ' README_EN.md)" -eq 12
for command in 'python3 -m venv .venv' 'source .venv/bin/activate' 'pip install -r requirements.txt' 'python3 -m app.main' 'pytest -v' 'scripts/build_app.sh arm64' 'scripts/build_app.sh x86_64'; do
  rg -Fq "$command" README.md
  rg -Fq "$command" README_EN.md
done
```

Expected: each README has exactly 12 level-two headings; command checks exit with status 0 and no output.

- [ ] **Step 2: Verify paths and numeric facts appear in both files**

Run:

```bash
rg -Fq '32、64、128、256 kbps' README.md
rg -Fq '32, 64, 128, and 256 kbps' README_EN.md
for fact in 'dist/<arch>/声绘魔法.app' '~/Library/Application Support/VoiceCanvas/' '~/Music/VoiceCanvas'; do
  rg -Fq "$fact" README.md
  rg -Fq "$fact" README_EN.md
done
rg -Fq '1 秒' README.md
rg -Fq '1 second' README_EN.md
for file in CONTRIBUTING.md SECURITY.md LICENSE LICENSE.zh-CN.md; do
  test -f "$file"
  rg -Fq "($file)" README.md
  rg -Fq "($file)" README_EN.md
done
rg -Fq '私密报告' README.md
rg -Fq '不要公开提交敏感信息' README.md
rg -Fq 'Privately report unresolved vulnerabilities' README_EN.md
rg -Fq 'do not publicly disclose sensitive information' README_EN.md
rg -Fq '法律效力以英文原文为准' README.md
rg -Fq 'the English original controls' README_EN.md
```

Expected: exit status 0 with no output.

- [ ] **Step 3: Run Markdown whitespace validation**

Run:

```bash
git diff --check -- README.md README_EN.md
```

Expected: exit status 0 with no output.

- [ ] **Step 4: Run the complete automated test suite**

Run outside the restricted socket sandbox:

```bash
.venv/bin/pytest -v
```

Expected: all collected tests pass; the accepted Starlette deprecation warning may remain.

- [ ] **Step 5: Review only the README changes and protect unrelated work**

Run:

```bash
git diff -- README.md README_EN.md
git status --short
```

Expected: README changes match this plan. Changes merged from `main` in application code, tests, `.github/`, `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, and `LICENSE.zh-CN.md` remain present and are not altered by this task.

- [ ] **Step 6: Commit the bilingual README compatibility update if the user requests a commit**

```bash
git add README.md README_EN.md docs/superpowers/specs/2026-07-16-user-readme-bilingual-design.md docs/superpowers/plans/2026-07-16-user-readme-bilingual.md
git commit -m "docs: add bilingual user readme"
```

Expected: the documentation commit contains the two README files and their compatibility-updated design and plan. When this work follows a merge from `main`, retain all merged public-release changes without modifying their product code.
