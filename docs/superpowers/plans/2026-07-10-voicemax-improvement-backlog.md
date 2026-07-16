# VoiceMax 改进路线图（历史完成记录）

> **状态：Phase 0–4 已完成（2026-07-10）；本文保留为历史记录。**
>
> 后续维护以 [2026-07-11 maintenance cleanup 计划](2026-07-11-maintenance-cleanup.md) 为入口，不再从本文启动历史 Phase。

**Goal:** 记录主 spec 与开发过程中积累的缺口如何被分阶段补齐，并保留原编号供提交、测试和竣工文档追溯。

**Architecture:** 继续采用 pywebview + FastAPI + 原生 JS；已完成的功能补齐没有改变这一总体架构。

**Tech Stack:** Python 3.13、FastAPI、SQLite、pytest + respx、原生 HTML/CSS/JS。

---

## 一、完成时现状摘要

- 配置页、音色库、工作台（含 Studio 重构）和报表均已实现；Phase 4 完成时完整测试结果为 **109 tests passed**。
- 配置、音色、报表已有三份竣工文档：`2026-07-10-settings-as-built.md`、`2026-07-10-voices-as-built.md`、`2026-07-10-usage-as-built.md`。
- 主设计文档和 Studio 设计文档均已更新为已实现；应用图标与侧边栏 Logo 已提交。
- A1–A10、E1、E3、E4 均已解决；B1–B3 与 F 类为明确接受的产品/技术取舍，不是待实现功能。
- 当前剩余维护项仅见第二节“当前维护清单”。

---

## 二、历史条目归档与当前维护清单

### A. 主 spec 功能缺口：已解决

| # | 历史问题 | 完成状态与核实依据 |
|---|---|---|
| A1 | 费用估算 `cost_estimate` | **已解决。** Settings 支持字符/Token 单价，`minimax_client` 写入估算费用，Usage 汇总与 CSV 使用该字段；见 Settings、Usage 竣工文档及 `tests/test_minimax_client.py`。 |
| A2 | 密钥缺失时无配置页引导 | **已解决。** `web/js/app.js` 导出 `VoiceMaxNavigate.toSettings`，Studio/Voices 复用错误处理并跳转；见 Settings、Voices 竣工文档和 `tests/test_frontend_scripts.py`。 |
| A3 | 整篇合成无分段进度 | **已解决。** 合成响应返回 `completed`/`failed`，前端显示完成段数；见 `app/services/synthesize.py`、`web/js/pages/studio.js` 及合成服务/API 测试。 |
| A4 | 整篇合成单段失败即全失败 | **已解决。** 单段异常被记录后继续处理，其余成功音频仍可拼接；见 `tests/test_synthesize_service.py`。 |
| A5 | 失败段无显式重试入口 | **已解决。** 失败段使用 `segment-failed` 状态并将操作按钮显示为“重试”；有前端静态标记测试。 |
| A6 | `voice_modify.sound_effects` 无 UI | **已解决。** `web/js/pages/studio.js` 读取音效器控件并写入 payload，`app/api/studio.py` 接收 `sound_effects`，`tests/test_synthesize_service.py` 验证下游 payload，`tests/test_frontend_scripts.py` 保留前端功能标记回归。 |
| A7 | 报表仅支持按天趋势 | **已解决。** Usage API、仓储查询和前端支持 day/week 切换；见 Usage 竣工文档和 `tests/test_usage_repo.py`。 |
| A8 | 音色克隆 `clone_prompt` 未暴露 | **已解决。** 克隆表单、API 和服务支持可选 `prompt_text`；参考音频 file_id UI 不在当前范围；见 Voices 竣工文档和 `tests/test_voices_service.py`。 |
| A9 | API 失败不记账 | **已解决。** MiniMax 认证、限流最终失败、超时、网络及业务错误均写入 `status=failed`；见 Usage 竣工文档和 `tests/test_minimax_client.py`。 |
| A10 | 限流不自动退避重试 | **已解决。** 状态码 1002 使用 1 秒、2 秒退避，重试耗尽后再记录失败并抛错；见 `app/services/minimax_client.py` 及其测试。 |

### B. 主 spec 与实现的有意偏差：保留取舍

| # | 取舍 | 当前结论 |
|---|---|---|
| B1 | CodeMirror 标注编辑器 → 原生 textarea | **保留。** 当前轻量编辑方案满足需求，无语法高亮需求前不引入 CodeMirror。 |
| B2 | ECharts → 自研 SVG 折线图 | **保留。** 已支持按天/周趋势；复杂图表需求出现前不增加依赖。 |
| B3 | 系统 ffmpeg → `imageio-ffmpeg` 内置二进制 | **保留。** 用户无需单独安装 ffmpeg；cleanup 已消除 pydub 导入期探测警告。 |

### C. 开发期问题：修复已保留，交互验证继续维护

| # | 历史问题 | 当前分类 |
|---|---|---|
| C1 | 页面切换竞态 | **已解决。** `__isPageActive`/页面 generation 守卫已实现；真实 DOM 交互覆盖仍是当前债务。 |
| C2 | 清空工作台与自动保存竞态 | **已解决。** `studioSaveGeneration` 已实现；真实 DOM 交互覆盖仍是当前债务。 |
| C3 | 原生右键菜单中文 | **保留现有取舍。** 使用进程语言参数，不重新引入已回滚的 Web 自定义菜单。 |
| C4 | 润色兜底产生孤立标点段 | **已解决并有后端回归测试。** 新边界案例按正常缺陷流程处理。 |

### D. 工程质量：已处理项与当前债务

| # | 历史问题 | 当前分类 |
|---|---|---|
| D1 | Settings 测试读取真实 Keychain | **已解决并验收。** `tests/test_settings_api.py` 的 `client` fixture 默认隔离 `get_api_key`，单项测试仍可覆盖。 |
| D2 | 前端缺少自动化 | **部分解决，仍有当前债务。** 已有 `tests/test_frontend_scripts.py` 静态脚本标记检查；尚无浏览器中的真实 DOM/交互自动化测试。 |
| D3 | Studio Task 8 人工验证未归档 | **部分解决，仍有当前债务。** 已归档历史结论；润色有效 Key 场景和自动保存/重启恢复等部分人工验证未在完整应用会话中复测归档。 |
| D4 | pytest 环境警告 | **部分解决。** cleanup 已消除 pydub 导入期 ffmpeg 探测警告；仅保留 Starlette `TestClient` 上游弃用警告，本轮不升级核心依赖。 |
| D5 | `StaticFiles` 注册顺序风险 | **当前债务。** 根路径 mount 必须位于所有 API 路由之后，当前依靠代码结构和注释约束，尚无自动防护。 |

### E. 文档与流程：已解决

| # | 历史问题 | 当前分类 |
|---|---|---|
| E1 | 两份 spec 状态过期 | **已解决。** 状态已改为已实现并记录偏差。 |
| E2 | 实现计划完成标准未勾选 | **已解决。** 有证据的完成标准已勾选；历史执行步骤保留原貌供追溯，不代表当前待办。 |
| E3 | 配置/音色/报表缺少独立文档 | **已解决。** 三份 as-built 文档已入库。 |
| E4 | `index.html` 保留页面占位文案 | **已解决。** 已替换为应用加载提示。 |

### F. 已知取舍：继续保留

- 草稿无历史版本 / 多草稿 UI（Studio 重构非目标）。
- 一行内多次情绪切换解析（非目标）。
- `localStorage` 草稿 id 丢失的极端恢复（非目标）。
- 双声道不可配置（固定为 2）。

### 当前维护清单

后续只维护以下已核实问题；状态变化记录到 [2026-07-11 maintenance cleanup 计划](2026-07-11-maintenance-cleanup.md)：

- [ ] 补充真实浏览器 DOM/交互自动化测试；现有前端测试仅验证静态脚本标记。
- [ ] 跟踪 Starlette `TestClient` 上游兼容性债务，待 FastAPI 官方支持的迁移路径稳定后单独处理。
- [ ] 为 `StaticFiles` 必须最后注册的顺序风险增加自动防护，或持续明确记录约束。
- [ ] 归档尚未在完整应用会话复测的 Studio 人工验证项。

---

## 三、历史 Phase 0–4（均已完成）

| 历史阶段 | 完成内容 | 归档状态 |
|---|---|---|
| Phase 0 | 文档状态、测试隔离、加载提示和应用图标整理 | **已完成（2026-07-10）** |
| Phase 1 | API Key 引导、整篇合成进度/容错/重试、失败调用记账 | **已完成（2026-07-10）** |
| Phase 2 | 可配置单价、费用估算和按周趋势 | **已完成（2026-07-10）** |
| Phase 3 | `sound_effects`、`clone_prompt` 和限流退避 | **已完成（2026-07-10）** |
| Phase 4 | 前端静态脚本测试、打包测试门禁和三份 as-built 文档 | **已完成（2026-07-10）** |

历史优先级 P0–P4 已全部执行完毕，不再作为当前排期。新的维护工作统一从 [maintenance cleanup 计划](2026-07-11-maintenance-cleanup.md) 拆分、验证和归档。

---

## 四、保留决策

- 不因历史路线图完成而引入 CodeMirror/ECharts；只有明确的新需求证明收益时再评估。
- 不扩展多草稿/版本历史 UI，除非产品范围发生变化。
- 不恢复 Web 自定义右键菜单；继续采用已验证的原生方案。
