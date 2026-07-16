# 配置页（Settings）竣工文档

- 日期：2026-07-10
- 状态：已实现
- 关联主 spec：`docs/superpowers/specs/2026-07-08-voice-max-design.md` §4.1

## 实现摘要

- API Key 存 Keychain，界面仅显示掩码；支持保存、清除、连接测试。
- 可配置默认模型/格式/采样率、保存目录、Base URL、Group ID。
- MP3 默认比特率可配置为 32/64/128/256 kbps，默认 256 kbps；WAV/FLAC 下禁用该选项但保留所选值。
- 费用估算：可设每千字符/每千 Token 参考单价（填 0 表示不估算），供报表 `cost_estimate` 使用。
- 缺 Key 时其他页面可跳转配置页，`sessionStorage` 传递提示文案。

## 主要文件

- `app/api/settings.py`
- `web/js/pages/settings.js`

## 与主 spec 偏差

- 无显著功能缺口；单价配置为后续改进计划补充，已合入。
