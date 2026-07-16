# 音色库（Voices）竣工文档

- 日期：2026-07-10
- 状态：已实现
- 关联主 spec：`docs/superpowers/specs/2026-07-08-voice-max-design.md` §4.3

## 实现摘要

- 系统音色列表（远程 Get Voice API）。
- 音色克隆：上传音频、voice_id、可选预览文案、可选 clone_prompt、备注。
- 音色设计：文字描述 + 预览文案生成音色。
- 本地音色备注管理；克隆/设计音色显示「已生效 / 7 天内需使用」状态。
- 缺 Key 时引导跳转配置页。

## 主要文件

- `app/api/voices.py`、`app/services/voices.py`
- `web/js/pages/voices.js`

## 与主 spec 偏差

- `clone_prompt` 当前仅支持 `prompt_text` 文本形式，未做参考音频 file_id 上传 UI。
