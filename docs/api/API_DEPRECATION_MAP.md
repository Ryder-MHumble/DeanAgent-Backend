# API 弃用与迁移表（v1）

更新时间：`2026-04-03`  
目标：减少重复接口，统一调用入口，保持向后兼容。

## 已标记弃用（仍可用）

当前无运行期弃用接口。

> 统一查询入口：`GET /api/v1/sources/deprecations`。

## 新增统一入口（按信源取数）

| 新接口 | 用途 | 关键参数 |
|---|---|---|
| `GET /api/v1/sources/items` | 按信源条件统一取数 | `source_id` / `source_ids` / `source_name` / `source_names`（至少一个） |
| `GET /api/v1/sources/{source_id}/items` | 固定单信源取数 | 路径 `source_id` + `date_from/date_to/keyword/page/page_size` |

## 迁移建议

1. 新调用统一优先走 `sources/items`（面向“按渠道拿数据”）。  
2. 后续若再次引入兼容接口，优先为其补充明确 sunset 日期与迁移负责人。  
3. 继续以 `GET /api/v1/sources/deprecations` 作为统一弃用查询入口。
