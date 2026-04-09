# Console API: OpenRouter Token/费用监控

## 端点

- `GET /console-api/api-monitor/usage`
- 作用：返回 OpenRouter 调用量、Token 消耗、费用、模块归因、模型排行与最近调用明细。

## 查询参数

- `days`: 时间窗口（1-30，默认 `7`）
- `module`: 模块过滤（可选）
- `stage`: stage 过滤（可选）
- `model`: 模型过滤（可选）
- `source_id`: 信源过滤（可选）
- `success`: 调用状态过滤，`all` / `success` / `failed`（默认 `all`）
- `limit`: 最近明细返回条数（1-200，默认 `80`）

## 返回结构

- `scope`: 本次查询作用域（固定 `provider=openrouter`）
- `overview`: 总览 KPI
  - `total_calls`
  - `total_tokens` / `total_input_tokens` / `total_output_tokens`
  - `total_cost_usd`
  - `priced_calls` / `unpriced_calls` / `unpriced_tokens`
  - `avg_cost_per_call_usd`（仅按 `priced_calls` 计算）
  - `success_calls` / `failed_calls` / `success_rate`
- `by_module`: 模块聚合
- `by_model`: 模型聚合
- `by_stage`: stage 聚合
- `recent_calls`: 最近调用明细（时间、模块、stage、model、source、token、费用、状态、耗时）
- `available_filters`: 可选筛选值（modules/stages/models/source_ids）
- `generated_at`: 生成时间

## 费用口径与 `unpriced` 语义

统计优先级：

1. `provider_cost_usd`（provider 回传费用）
2. 本地价格表推导（`pricing_map`）
3. 历史兼容费用（`cost_usd`）
4. 仍不可定价则记为 `unpriced`

`unpriced` 语义：

- 该调用无法可靠定价，不会被强制记为 `0`。
- `total_cost_usd` 只累计可定价调用。
- `avg_cost_per_call_usd` 分母只使用 `priced_calls`。
