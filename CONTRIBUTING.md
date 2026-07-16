# 参与贡献

感谢你愿意改进声绘魔法（VoiceCanvas）。

## 开始之前

1. 先搜索现有 Issue，确认问题或建议没有被重复提交。
2. 对较大的功能、架构调整或不兼容变更，请先创建 Issue 讨论方案。
3. 不要在 Issue、日志、截图、测试数据或提交中包含真实 API Key、Group ID、个人音频及其他敏感信息。

## 本地开发

项目要求 macOS 和 Python 3.13 或更高版本：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
```

启动应用：

```bash
python -m app.main
```

## 提交合并请求

- 一个合并请求只解决一类问题，说明变更原因、用户影响和验证方式。
- 新功能和缺陷修复应补充自动化测试。
- 提交前运行完整测试，并确保没有把构建产物、本地数据库、虚拟环境或凭据纳入 Git。
- 界面文案、文档、提交说明和用户可见错误信息优先使用简体中文。

提交贡献即表示你有权提交相关内容，并同意按本项目许可证发布你的贡献。
