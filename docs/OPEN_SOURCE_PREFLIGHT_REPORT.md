# GitHub 公开发布审计报告

审计日期：2026-07-16

目标仓库：`enigmawlcx/VoiceCanvas`

发布方式：从当前已清理文件创建单提交 public 仓库，不公开原 private 仓库的旧历史

## 审计结论

项目已具备公开发布所需的基本代码、测试、许可证、贡献说明、安全报告渠道和自动化检查。审计中发现的目录穿越、内部异常信息泄露和本机绝对路径问题已修复。

## 已完成检查

- 当前文件和可达 Git 历史未发现疑似真实 API Key、GitHub Token 或私钥。
- `.env`、数据库、虚拟环境、构建产物、缓存和本地工作树均已由 `.gitignore` 排除。
- API Key 使用 macOS Keychain 保存，不写入配置 JSON。
- 直接依赖声明的许可证为 MIT、Apache-2.0、BSD、PSF-2.0 等宽松许可证，未发现明显许可证冲突。
- 项目使用 MIT License，并提供非法律效力的中文辅助说明。
- Python、Shell、JavaScript 语法检查和 `git diff --check` 通过。
- 完整测试结果：149 项通过；存在 1 条已知的 Starlette 测试依赖弃用警告。
- 新增 macOS/Python 3.13 GitHub Actions 测试和 Dependabot 配置。

## 本次修复

- 拒绝包含绝对路径、父目录或路径分隔符的音频导出文件名，防止写出配置的保存目录。
- 未捕获异常只向客户端返回通用错误，详细信息仅写入本地日志。
- 从设计文档中移除本机用户名和工作区绝对路径。
- 增加 `CONTRIBUTING.md`、`SECURITY.md`、MIT 许可证和自动化测试工作流。

## 已知边界

- PyPI 与 OSV 漏洞数据库在审计时均响应超时，因此未取得一次完整的在线依赖漏洞扫描结果；Dependabot 将在 public 仓库中持续检查依赖更新和安全告警。
- 自动化测试使用模拟的 MiniMax 响应，未使用真实账户执行端到端 API 验证。
- 源码仓库无法证明图片和图标素材的原创性或外部授权状态；发布者仍需确保 `assets/` 和 `web/images/` 中素材拥有可公开分发的权利。
- 本报告不构成法律意见。
