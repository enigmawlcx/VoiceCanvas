# VoiceMax 设计文档

- 日期：2026-07-08
- 状态：已实现（2026-07-10）
- 定位：Mac 上运行的个人自用桌面应用，基于 MiniMax API 完成语音克隆、音色设计、语音合成，并提供配置界面与用量报表。

## 1. 目标与范围

### 目标
- 提供一个原生外观的 Mac 桌面 App（个人自用，数据全本地）。
- 覆盖 MiniMax 语音能力：语音合成（T2A）、音色克隆、音色设计。
- 提供"整篇文章 → AI 润色标注（情绪/语气词）→ 审阅 → 合成音频"的完整工作流。
- 提供配置界面（API Key 等）与用量报表界面。

### 非目标（YAGNI）
- 不做多用户/权限/云端同步。
- 不做官方账单对账（用量报表基于本地记录）。
- 不做移动端/Windows/Linux（当前仅 Mac）。

## 2. 技术方案

采用 **pywebview + FastAPI 本地 Web 内核** 方案：
- pywebview 提供原生 Mac 窗口外壳。
- 前端为静态 HTML/CSS/JS。
- 后端 FastAPI 在同进程后台线程启动，前端通过 `http://127.0.0.1:<随机端口>` 访问。
- 所有数据本地存储，不上云。

## 3. 整体架构

```
┌─────────────────────────────────────────┐
│  pywebview 窗口 (原生 Mac 窗口外壳)         │
│  ┌─────────────────────────────────────┐ │
│  │  前端 (静态 HTML/CSS/JS)              │ │
│  │  - textarea + 分段列表预览           │ │
│  │  - 自研 SVG 用量折线图               │ │
│  │  - 原生 <audio> 试听                 │ │
│  └──────────────┬──────────────────────┘ │
│                 │ HTTP (localhost)         │
│  ┌──────────────▼──────────────────────┐ │
│  │  FastAPI 后端 (同进程线程启动)        │ │
│  │  - API 路由层                        │ │
│  │  - MiniMax 客户端封装                │ │
│  │  - 业务服务 (润色/合成/克隆/用量)     │ │
│  │  - SQLite 存储 + Keychain 存密钥      │ │
│  └──────────────┬──────────────────────┘ │
└─────────────────┼────────────────────────┘
                  │ HTTPS
          ┌───────▼────────┐
          │  MiniMax API   │
          │  (T2A/克隆/    │
          │   设计/LLM)     │
          └────────────────┘
```

- 单进程启动：FastAPI 跑后台线程，pywebview 主线程开窗口。
- API Key 存 macOS Keychain（`keyring`），不落明文。

## 4. 界面模块

左侧导航切换四个主界面。

### 4.1 配置页 (Settings)
- API Key 输入（存 Keychain，界面只显示掩码）。
- 默认模型选择（如 `speech-2.8-hd`）、默认音频格式/采样率。
- 音频文件默认保存目录。
- 连接测试按钮（调轻量接口验证 Key 有效）。

### 4.2 工作台 (Studio) — 核心
- 主区：单一大文本框，输入原文并接收 "AI 润色标注" 结果。
- 右侧：情绪/语气词按钮面板，可在文本框中插入标注。
- 合成设置：音色、语速、音量、pitch 与音效器（`voice_modify`）。
- 底部：分段列表预览 + 单段试听/失败重试 + 整篇合成拼接导出；整篇合成后失败段仍可单独重试。

### 4.3 音色库 (Voices)
- 系统音色列表（Get Voice API）。
- 音色克隆：上传音频 → 设 voice_id，可选填写文本形式的 `clone_prompt` → 生成 → 试听。
- 音色设计：文字描述 → 生成音色 → 试听。
- 本地音色管理（voice_id + 备注 + 试听）。

### 4.4 报表 (Usage)
- 自研 SVG 用量趋势图（按天/周切换，字符数）。
- 按功能拆分（合成/润色/克隆分别统计）。
- 明细表（时间、功能、模型、字符/token、音色）。
- 时间范围筛选 + 导出 CSV；合计区显示字符、Token 和按配置单价计算的估算费用。

## 5. 核心数据流（润色 → 标注 → 合成管线）

### 5.1 标注格式
编辑器中间表示，人类可读可改：

```
[calm] 大家好，欢迎回来。(emm) 今天聊个有意思的话题。
[happy] 没想到吧！(laughs) 这真的太棒了。
[sad] 但结局并不完美……
```

- `[emotion]` 段落级情绪标签 → 映射 T2A `emotion` 参数。
- `(laughs)`/`(sighs)`/`(emm)` 内嵌语气词 → 直接写进 `text`（speech-2.8 支持）。
- 每行/每空行分隔 = 一个合成分段。

### 5.2 管线步骤
1. 润色标注：原文 → MiniMax LLM（system prompt 约束分段、选情绪、插语气词、不改原意）→ 返回标注文本 → 填入编辑器。
2. 人工审阅：在编辑器修改情绪/语气词/断句。
3. 解析：标注文本 → 分段结构 `[{text, emotion}, ...]`。
4. 合成：逐段调 T2A（含 voice_setting + voice_modify）→ 音频；支持单段试听或整篇合成。
5. 拼接导出：整篇合成按序拼接为一个音频文件（`pydub`）导出到默认目录。
6. 记账：每次 LLM/T2A 调用后记录 `usage_characters`/token 到 SQLite。

### 5.3 关键取舍
整篇合成采用"逐段多次调用 + 本地拼接"，而非一次性传整篇。
- 优点：情绪可分段不同、失败可单段重试、进度可见。
- 代价：多次请求。

## 6. 数据存储与用量记账

### 6.1 存储位置
`~/Library/Application Support/VoiceMax/`

### 6.2 SQLite 表
- `usage_log`：`id, timestamp, feature(polish/synthesize/clone/design), model, characters, tokens, voice_id, cost_estimate, status`
- `voices`：`voice_id, type(system/cloned/designed), name, note, sample_path, created_at`
- `projects`：`id, title, source_text, annotated_text, updated_at`（自动保存草稿）

### 6.3 配置存储
- 普通配置（默认模型/格式/目录）→ JSON 文件。
- API Key → macOS Keychain（`keyring`），JSON 不存密钥。

### 6.4 记账来源
- 主来源：响应中的 `usage_characters`（T2A）与 LLM token 字段，调用成功即写入 `usage_log`。
- 报表基于本地 `usage_log` 聚合，不依赖官方账单接口。
- `cost_estimate` 按可配置单价本地估算，仅供参考。

## 7. 技术栈与项目结构

### 7.1 依赖
- `pywebview` — 原生窗口外壳。
- `fastapi` + `uvicorn` — 后端。
- `httpx` — 调 MiniMax（异步、超时、重试）。
- `keyring` — Keychain 存密钥。
- `pydub` + `imageio-ffmpeg` — 音频拼接；代码显式使用内置静态 ffmpeg 二进制，无需系统安装 ffmpeg。
- `pytest` + `respx` — 测试（拦截 httpx，不打真实 API）。
- 前端：原生 HTML/CSS/JS；标注编辑使用 textarea + 分段列表预览，用量趋势使用自研 SVG 折线图，无前端构建链或第三方图表/编辑器依赖。

### 7.2 项目结构
```
voice-max/
├── app/
│   ├── main.py              # pywebview 启动 + FastAPI 线程
│   ├── config.py            # 路径/配置/Keychain
│   ├── api/                 # FastAPI 路由
│   │   ├── settings.py
│   │   ├── studio.py
│   │   ├── voices.py
│   │   └── usage.py
│   ├── services/            # 业务逻辑
│   │   ├── minimax_client.py    # API 封装（单一出口，统一记账）
│   │   ├── polish.py            # LLM 润色标注
│   │   ├── annotate.py          # 标注文本解析
│   │   ├── tags.py              # 情绪/语气词唯一数据源
│   │   ├── synthesize.py        # 合成 + 拼接
│   │   └── voices.py
│   ├── db/                  # SQLite + 数据访问
│   └── models.py            # Pydantic 模型
├── web/                     # 前端静态资源
│   ├── index.html
│   ├── css/
│   ├── images/
│   └── js/
├── tests/
├── requirements.txt
└── README.md
```

### 7.3 关键设计
所有 MiniMax 调用只经 `minimax_client.py` 一个出口，记账逻辑集中于此，杜绝漏记。

## 8. 错误处理

- 网络超时 / 限流(1002) / 鉴权失败(1004) 分类捕获，前端给明确提示。
- 分段合成单段失败可重试，不影响其他段。
- 密钥缺失时引导跳转配置页。

## 9. 测试

- `respx` mock MiniMax 响应，覆盖：标注解析、记账写入、合成拼接、错误分支。
- 不消耗真实额度。

## 10. MiniMax API 关键事实（设计依据）

- 合成模型 `speech-2.8-hd` 支持 `emotion`（happy/sad/angry/fearful/disgusted/surprised/calm/fluent/whisper）+ 文本内嵌语气词 `(laughs)`/`(sighs)`/`(emm)`。
- `voice_setting`：voice_id、speed[0.5,2]、vol、pitch、emotion。
- `voice_modify`：pitch、intensity、timbre（[-100,100]）、sound_effects。
- 音色克隆：上传音频获 file_id → `/v1/voice_clone`（voice_id + 可选 clone_prompt）；克隆音色为临时音色，需 7 天内使用一次以持久化。
- 音色设计：文字描述生成 voice_id。
- 计费按字符，响应返回 `usage_characters`。
- 鉴权：Bearer JWT。

## 附录：历史设计决策

以下内容记录方案从初稿到竣工实现的取舍；现行规范以本文正文为准：

- **B1 标注编辑器**：初稿考虑 CodeMirror 高亮编辑器；最终选择纯 textarea + 分段列表预览，避免引入前端构建链。
- **B2 用量图表**：初稿考虑 ECharts；最终选择自研 SVG 折线图 + 表格。
- **B3 音频拼接依赖**：初稿考虑由用户安装系统 ffmpeg；最终选择 `imageio-ffmpeg` 内置静态二进制（`synthesize.py` 显式设置 `AudioSegment.converter`）。
