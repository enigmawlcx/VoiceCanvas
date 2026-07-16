# “声绘魔法 / VoiceCanvas”应用改名设计

- 日期：2026-07-12
- 状态：待实施
- 原名称：VoiceMax
- 新名称：声绘魔法（中文主品牌）/ VoiceCanvas（英文品牌名）

## 1. 目标

将当前应用从 `VoiceMax` 更名为“声绘魔法 / VoiceCanvas”，使品牌更准确地表达“使用声音创作作品”的产品定位，同时保证已有配置、API Key、草稿、音色记录和用量数据不会因更名丢失。

本次工作只改变品牌与用户可见名称，不改变语音合成、音色克隆、音色设计、文章润色标注、报表等业务能力。

## 2. 品牌规则

- 中文界面主品牌：`声绘魔法`
- 英文品牌名：`VoiceCanvas`
- 中文介绍中首次出现时使用：`声绘魔法（VoiceCanvas）`
- 英文名固定写作 `VoiceCanvas`，中间不加空格，不使用 `Voice Canvas`
- 不再在用户可见界面、文档标题和发行产物中使用 `VoiceMax`
- MiniMax 是底层 API 服务商名称，不属于应用品牌，技术说明中继续保留

## 3. 用户可见改名范围

### 3.1 应用界面

- 网页标题、侧栏品牌名、Logo 的替代文本改为“声绘魔法”或对应的中英文组合
- macOS 原生窗口标题改为“声绘魔法”
- FastAPI 元数据标题改为“声绘魔法 / VoiceCanvas”
- README 标题和产品介绍改为“声绘魔法（VoiceCanvas）”

### 3.2 macOS 发行产物

- 应用包名称：`声绘魔法.app`
- Finder 和系统界面显示名称：`声绘魔法`
- 可执行文件内部名称使用 `VoiceCanvas`，避免中文路径或命令行工具兼容问题
- PyInstaller 配置文件改名为 `VoiceCanvas.spec`
- 应用图标文件改名为 `VoiceCanvas.icns`
- 构建脚本和 README 中的产物路径同步更新

### 3.3 默认输出目录

- 全新安装的默认音频保存目录改为 `~/Music/VoiceCanvas`
- 已经在配置中保存了输出目录的用户继续使用原配置，不强制迁移文件
- 不移动或删除已有的 `~/Music/VoiceMax` 内容

## 4. 数据与凭据兼容策略

### 4.1 应用数据目录

新标准数据目录为：

`~/Library/Application Support/VoiceCanvas/`

启动时按以下优先级处理：

1. 如果通过测试或运行参数显式指定了数据目录，完全尊重该目录，不执行真实用户目录迁移。
2. 如果新目录已经存在，直接使用新目录，不覆盖其中内容。
3. 如果新目录不存在、旧目录 `~/Library/Application Support/VoiceMax/` 存在，则将旧目录整体重命名为新目录。
4. 如果迁移失败，继续使用旧目录并记录清晰错误信息，避免应用因品牌迁移无法启动。
5. 如果新旧目录同时存在，不自动合并；优先使用新目录，避免覆盖或混合两套数据库。

迁移不得删除数据库、配置文件、草稿、音色记录或用量日志。

### 4.2 macOS Keychain

- 新 Keychain service 名称为 `VoiceCanvas`
- 读取 API Key 时先读取 `VoiceCanvas`，没有值时回退读取旧 service `VoiceMax`
- 从旧 service 读到 Key 后，将同一值写入新 service
- 迁移成功后暂不删除旧 Keychain 项，为版本回退保留兼容性
- 用户更新或清除 API Key 时，以新 service 为主，并确保界面行为与当前版本一致

## 5. 内部标识处理

用户不可见且不会泄漏到数据路径、发行名称或对外接口的内部标识不做机械式全量改名。例如：

- `window.VoiceMaxPages`
- `window.VoiceMaxNavigate`
- `window.VoiceMaxApiErrors`

保留这些 JavaScript 命名空间可以降低无业务价值的回归风险。若未来进行前端模块化重构，再单独统一内部命名。

项目工作区目录也不在本次改名范围内，避免影响现有 Git 工作区和本地工具配置。

## 6. 涉及的主要文件

- `web/index.html`：网页标题、品牌文字、Logo 替代文本
- `app/main.py`：FastAPI 标题和 macOS 窗口标题
- `app/config.py`：数据目录和 Keychain 兼容迁移
- `app/models.py`：新安装默认输出目录
- `VoiceMax.spec`：改名为 `VoiceCanvas.spec` 并更新应用包元数据
- `scripts/build_app.sh`：构建配置及产物路径
- `scripts/generate_app_icon.sh`：图标资源名称
- `assets/VoiceMax.icns`：改名为 `assets/VoiceCanvas.icns`
- `README.md`：品牌、构建产物和数据路径说明
- `tests/`：新增或更新品牌名称、数据目录及 Keychain 迁移测试

已有历史设计文档保留原文，不批量篡改历史记录；必要时在当前 README 或新文档中说明项目曾用名。

## 7. 错误处理

- 数据目录迁移失败时不得静默创建空白新环境，应回退旧目录并提供可诊断日志
- 新旧数据目录同时存在时不得自动覆盖或合并
- Keychain 新 service 写入失败时，当前进程仍可使用从旧 service 读取的 Key
- 改名不得改变 API 配置、数据库结构或网络请求行为

## 8. 测试与验收

### 自动化测试

- 新安装使用 `VoiceCanvas` 数据目录和默认音频输出目录
- 旧数据目录存在时可以迁移并继续读取原配置与数据库
- 显式数据目录覆盖时不触碰真实默认目录
- 新旧目录同时存在时优先使用新目录且不覆盖文件
- 数据目录迁移失败时回退旧目录
- 新 Keychain service 有值时优先读取新值
- 只有旧 Keychain service 有值时能读取并复制到新 service
- Keychain 复制失败时仍可使用旧值
- 现有测试全部通过

### 人工验收

- 应用包显示为“声绘魔法.app”
- Finder、窗口标题和侧栏显示“声绘魔法”
- README 使用“声绘魔法（VoiceCanvas）”
- 旧版本已有配置、API Key、草稿、音色记录和报表数据仍然可用
- 构建产物位于 `dist/<arch>/声绘魔法.app`
- 用户可见位置不再出现旧品牌 `VoiceMax`
- MiniMax API 服务商名称仍正确保留

## 9. 非目标

- 不修改功能、接口协议、数据库结构或 UI 布局
- 不重新设计 Logo 图形；本次只处理名称和现有图标资源的文件命名
- 不改项目工作区文件夹名称
- 不重命名所有内部 JavaScript 全局变量
- 不删除旧数据目录、旧输出文件或旧 Keychain 项
