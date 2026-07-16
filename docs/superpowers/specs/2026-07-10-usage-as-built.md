# 报表（Usage）竣工文档

- 日期：2026-07-10
- 状态：已实现
- 关联主 spec：`docs/superpowers/specs/2026-07-08-voice-max-design.md` §4.4

## 实现摘要

- 用量趋势：自研 SVG 折线图，支持按天/按周切换。
- 按功能拆分统计表（调用次数、字符、Token、条形占比）。
- 明细表：时间范围/功能筛选、分页、CSV 导出。
- 合计区显示字符/Token 总量及估算费用（需配置页设单价）。
- 记账来源：`minimax_client` 统一写入，含 `status=success/failed`。

## 主要文件

- `app/api/usage.py`、`app/db/usage_repo.py`
- `web/js/pages/usage.js`

## 与主 spec 偏差

- 图表为 SVG 自研实现，非 ECharts（见主 spec 附录 B2）。
