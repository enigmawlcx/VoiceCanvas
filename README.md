# 声绘魔法（VoiceCanvas）

个人自用 Mac 桌面 App，基于 MiniMax API 提供语音合成、音色克隆、音色设计能力。配置、用量记录和音频产物存储在本地；语音相关请求会发送到用户配置的 MiniMax API 服务。配置页/工作台/音色库/报表四个功能模块均已实现。

## 功能模块

- **配置页**：API Key（存 Keychain，界面仅显示掩码）、Group ID、默认模型/格式/采样率、保存目录、连接测试。
- **音频编码**：MP3 支持 32/64/128/256 kbps，分段与拼接成品统一使用恒定比特率（CBR）；WAV/FLAC 不应用比特率设置。
- **音色库**：系统音色浏览、音色克隆（上传音频，可选文本形式的 clone prompt）、音色设计（文字描述生成）、本地音色备注管理。
- **工作台**：原文 → AI 润色标注 → 标注编辑（`[emotion]` 情绪标签 + `(语气词)`）→ 分段试听 → 整篇合成拼接导出；支持整篇合成失败段重试、音效器和草稿自动保存。
- **报表**：按天/按周用量趋势图、按功能拆分统计、明细查询（时间范围/功能筛选、分页）、CSV 导出，以及按配置单价计算的费用估算。

## 技术说明

- 后端：FastAPI + SQLite + httpx，所有 MiniMax 调用统一经过 `app/services/minimax_client.py`（含错误分类与自动记账）。
- 前端：原生 HTML/CSS/JS，无构建工具。标注编辑器与用量图表均为轻量自研实现（文本框 + 分段预览、SVG 折线图），未引入第三方编辑器或图表库，以保持项目零构建链、低维护成本。
- MiniMax API 默认使用国内站 `https://api.minimaxi.com`，如账号在国际站请在配置页修改 Base URL；部分接口可能需要额外配置 Group ID。

## 环境要求

- macOS
- Python 3.13+
- 无需系统安装 ffmpeg：`pydub` 音频拼接依赖的 ffmpeg 已通过 `imageio-ffmpeg` 内置静态二进制，pip 安装依赖即可

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

GitHub Actions 会在每次推送到 `main` 以及合并请求中使用 macOS 和 Python 3.13 运行完整测试。

## 打包

打包脚本会先安装/更新构建依赖并运行完整测试，然后生成对应架构的 macOS App：

```bash
scripts/build_app.sh arm64
# 或：scripts/build_app.sh x86_64
```

产物位于 `dist/<arch>/声绘魔法.app`。构建 x86_64 版本需要 Rosetta 2；`universal2` 参数仅在当前 Python 解释器及全部依赖均提供 universal2 支持时使用。构建目录与发行产物属于本地生成内容，不纳入 Git。

## 项目结构

- `app/` — 后端：FastAPI 路由、业务服务、SQLite 数据层
- `web/` — 前端静态资源（原生 HTML/CSS/JS）
- `tests/` — pytest 测试
- `scripts/` — 应用图标生成与 macOS 打包脚本
- `docs/` — 设计、实施计划与维护记录

## 数据存储位置

默认使用 `~/Library/Application Support/VoiceCanvas/` 存储配置 JSON 和 SQLite 数据库；首次启动新版时会迁移旧 `VoiceMax` 数据目录，迁移失败会安全回退。API Key 存 macOS Keychain，不落明文。默认音频输出目录为 `~/Music/VoiceCanvas`。

## 参与贡献与安全

- 贡献代码前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。
- 未修复漏洞请按 [SECURITY.md](SECURITY.md) 私密报告，不要公开提交敏感信息。

## 开源许可证

本项目采用 [MIT License](LICENSE) 开源；[中文说明](LICENSE.zh-CN.md) 仅供辅助理解，法律效力以英文原文为准。
