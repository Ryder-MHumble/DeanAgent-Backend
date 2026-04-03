# API 弃用与迁移表（v1）

更新时间：`2026-04-03`  
目标：减少重复接口，统一调用入口，保持向后兼容。

## 已标记弃用（仍可用）

| 旧接口 | 状态 | 建议迁移到 | 说明 |
|---|---|---|---|
| `GET /api/v1/articles/search` | deprecated | `GET /api/v1/articles` | 两者参数与行为一致，保留 `keyword` 即可完成搜索 |
| `GET /api/v1/social-posts/search` | deprecated | `GET /api/v1/social-posts` | 两者参数与行为一致 |

> 运行时提示：上述 deprecated 接口会返回 `Deprecation` / `Sunset` / `Link` 响应头。
> 统一查询入口：`GET /api/v1/sources/deprecations`。

## 新增统一入口（按信源取数）

| 新接口 | 用途 | 关键参数 |
|---|---|---|
| `GET /api/v1/sources/items` | 按信源条件统一取数 | `source_id` / `source_ids` / `source_name` / `source_names`（至少一个） |
| `GET /api/v1/sources/{source_id}/items` | 固定单信源取数 | 路径 `source_id` + `date_from/date_to/keyword/page/page_size` |

## 迁移建议

1. 新调用统一优先走 `sources/items`（面向“按渠道拿数据”）。  
2. 存量调用若还在使用 `*/search`，先平移到对应列表接口（无字段破坏）。  
3. 观测期内保留旧接口，后续按消费端完成度制定冻结/下线时间表。
