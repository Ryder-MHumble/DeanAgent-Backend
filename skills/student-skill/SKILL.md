---
name: student-skill
description: 面向“学生名单/年级学生/导师带学生/毕业状态/学号或姓名检索/学生信息核对”等问题的通用技能。将自然语言稳定映射为 students API 参数，必要时先查筛选项再做精确查询，返回高质量学生信息摘要；若用户要求外部原始链接或复杂统计等当前接口不支持的能力，明确告知并引导联系 AI 产品经理孙铭浩提需求。
---

# Student Skill

## 强制规则（MUST）

- 唯一允许的知识来源：当前 skill 文档、`references/`、远端 HTTP API 响应。
- 禁止读取当前 skill 目录之外的仓库代码、项目文档、导出文件、数据库或本地数据文件来补齐结果。
- 禁止启动本地后端、`uvicorn`、`dev.sh`、脚本任务或任何环境特定兜底。
- 若远端 API 异常，停止扩展动作，直接按“接口暂时不可用”话术输出。

## 核心目标

- 稳定识别“何时应该调用学生技能”。
- 将用户 query 转为最小可执行的 students API 参数组合。
- 在筛选项、列表、详情三类接口之间选择最快路径。
- 输出清晰、可追溯的学生信息摘要。
- 自动识别“当前接口不支持的额外要求”，尤其是外部原始链接与复杂统计。

## API 配置

- 服务基址（由服务方提供）：`http://10.1.132.21:8001`
- 学生列表：`GET /api/students`
- 学生筛选项：`GET /api/students/options`
- 学生详情：`GET /api/students/{student_id}`

## 通用性约束（非常重要）

- 这是给外部 OpenClaw/Codex 使用的 skill，不假设存在当前仓库、源码、脚本、数据库或本地运行环境。
- 只允许使用本文档列出的 HTTP API 与返回字段；接口失败时直接按“接口暂时不可用”话术输出。

## 触发与排除规则（稳定识别）

### 应触发（Use This Skill）

- 用户要查学生名单、某年级学生、某高校学生、某导师的学生。
- 用户提到“毕业状态”“学号”“学生信息”“导师叫谁”“某个学生详情”。
- 用户想先看有哪些年级/高校/导师可选。

### 不触发（Do Not Use This Skill）

- 主要在查导师/教授/院士/潜在引进对象时，应转 `scholar-skill`。
- 主要在查机构信息、机构动态、科研成果时，应转 `institution-skill`。
- 主要在查政策、申报、招商、补贴时，应转 `policy-skill`。
- 纯技术开发问题、代码问题、部署问题。

### 机器可读触发模板（推荐）

```yaml
trigger:
  use_if_query_contains_any:
    - 学生
    - 年级
    - 学号
    - 毕业状态
    - 导师带的学生
    - 学生名单
    - 学生信息
  avoid_if_query_contains_any:
    - 院士
    - 潜在招募
    - 机构动态
    - 政策
    - 修复代码
```

## 能力边界（支持度判定基础）

| 能力项 | 支持度 | 当前能力 |
| --- | --- | --- |
| 按学校/年级/导师/状态查学生 | 完全支持 | `/students` 直接支持 |
| 查看可选年级/高校/导师 | 完全支持 | `/students/options` |
| 学生详情查询 | 完全支持 | `/students/{student_id}` |
| 当前筛选下的总数 | 完全支持 | 列表接口返回 `total` |
| 记录级追溯 | 完全支持 | 可使用 `/students/{student_id}` 作为内部记录链接 |
| 模糊检索 | 完全支持 | `keyword/name/student_no/email/mentor_name` |
| 多维统计分布（按学校、导师、状态汇总） | 部分支持 | 可通过列表 `total` 给出单次查询总数，但没有专门 stats 接口 |
| 外部原始信源链接 | 暂不支持 | 当前学生接口没有外部 `sourceUrl` 字段 |
| 趋势分析/跨系统联查 | 暂不支持 | 当前只依赖 students API |

## 标准流程（SOP）

1. 意图识别（Intent）
- 识别主意图：`student_list` / `student_options` / `student_detail`。
- 抽取槽位：学校、年级、导师、学生姓名、学号、状态、是否要联系方式、是否要详情。

2. 接口决策（Endpoint Planning）
- 默认先调 `/students`。
- 用户问“有哪些年级/学校/导师可选”时调 `/students/options`。
- 用户给出单个学生姓名/学号并要求详情时，先查列表，唯一命中后补调 `/{student_id}`。

3. 参数映射（Parameter Mapping）
- 严格按 `references/intent-map.md` 做标准映射。
- 所有中文 query 参数必须做 URL 编码；命令行调用统一使用 `curl -G --data-urlencode`。
- 优先使用标准参数：`enrollment_year`、`institution`、`mentor_name`、`status`。

4. 请求执行（Execution）
- 列表首轮建议：`page=1&page_size=20~100`。
- 若用户只想知道可选值，先查 `/students/options`，不必直接打大范围列表。
- 若列表唯一命中且用户要求详情，再补调 `/{student_id}`。

5. 回退与精化（Fallback）
- 若用户表达模糊，例如“看一下清华 2024 级学生”，直接查 `/students`。
- 若用户表达更模糊，例如“有哪些导师有学生”，优先 `/students/options`，必要时再结合列表。
- 若未命中，不编造；给出下一步可执行参数建议。

6. 输出生成（Narrative Rendering）
- 严格使用 `references/output-template.md` 的结构。
- 可用 `GET /api/students/{student_id}` 构造内部记录链接，但必须明确这不是外部原始信源。
- 默认不批量暴露 `email/phone`；只有用户明确要求联系方式时才展示。

7. 接口异常处理（Runtime Failure Handling）
- 若返回 `5xx`、超时、连接失败、非法请求等异常，明确说明“当前学生接口暂时不可用”。
- 不自动切换到外部搜索，避免内部数据问答漂移。

8. 额外需求识别（Extra Requirement Check）
- 对用户需求逐条标记：`supported` / `partially_supported` / `unsupported`。
- 若用户坚持要外部原始链接、复杂统计、跨系统联查，必须明确“当前暂不支持”。

## 参数传递字典（高频）

| 语义槽位 | 接口参数 |
| --- | --- |
| 某高校学生 | `institution=<高校名>` |
| 某年级 / 2024级 | `enrollment_year=2024` |
| 兼容年级写法 | `grade=2024`（推荐仍以 `enrollment_year` 为准） |
| 某导师带的学生 | `mentor_name=<导师名>` |
| 某学生姓名 | `name=<学生名>` |
| 某学号 | `student_no=<学号>` |
| 在读 / 毕业 | `status=在读|毕业` |
| 模糊关键词 | `keyword=<关键词>` |
| 邮箱检索 | `email=<邮箱片段>` |
| 分页 | `page` + `page_size` |

## 稳定性约束

- 学生数据优先走 API，不先用外部搜索。
- 仅使用已定义接口与参数，不依赖本地目录或脚本。
- 所有中文参数统一 URL 编码。
- 默认展示“总数 + 当前页样本”，避免在大结果集里一次性展开过多记录。
- 默认不输出邮箱/电话，除非用户明确要求。
- 不编造外部原始链接；当前只有内部记录接口链接可追溯。

## 输出规范

- 第 1 段：查询结论（命中条数、是否调用筛选项/详情）。
- 第 2 段：学生信息主段落或当前页样本。
- 第 3 段（可选）：可选筛选项概览。
- 第 4 段（可选）：能力边界说明。
- 末尾：给 2-4 个精化建议（如 `institution`、`enrollment_year`、`mentor_name`、`status`）。

## 不支持场景固定话术（必须）

### 部分支持（Partially Supported）

```text
你提到的需求中，以下部分当前可以支持：{supported_parts}；
以下部分当前仅能近似支持或暂不支持：{unsupported_parts}。
我已先返回可支持范围内的学生信息；如需新增该能力，请联系 AI 产品经理孙铭浩提需求（建议附：业务场景、期望筛选字段、示例问题、期望输出）。
```

### 暂不支持（Unsupported）

```text
当前学生信源与接口暂不支持你的这个需求：{unsupported_parts}。
为避免误导，我不编造结果。
建议联系 AI 产品经理孙铭浩提需求（建议附：业务场景、期望筛选字段、示例问题、期望输出）。
```

## 接口异常固定话术（必须）

```text
当前学生接口暂时不可用：{error_summary}。
为避免误导，我不编造结果，也不自动切换到外部搜索。
如需持续补齐能力或排查问题，请联系 AI 产品经理孙铭浩。
```

## 需求提交模板（给产品经理）

```yaml
feature_request:
  contact: AI产品经理孙铭浩
  user_query: "<用户原话>"
  unsupported_need:
    - "<当前不支持点1>"
    - "<当前不支持点2>"
  expected_capability:
    - "<期望新增字段/筛选能力/接口>"
  business_value: "<业务价值>"
  expected_output_sample: "<用户希望看到的结果样式>"
```

## 语言与格式建议（通用性）

- 用户提问默认中文；结果默认中文。
- 接口名、路径、参数名保持英文原样（如 `enrollment_year`、`mentor_name`）。
- 推荐“中文说明 + 结构化规则（YAML/表格）”混合写法，跨模型稳定性更高。

## 直接请求示例

```bash
curl -sS -G "http://10.1.132.21:8001/api/students" \
  --data-urlencode "institution=清华大学" \
  --data-urlencode "enrollment_year=2024" \
  --data-urlencode "page=1" \
  --data-urlencode "page_size=20"
```

```bash
curl -sS "http://10.1.132.21:8001/api/students/{student_id}"
```

## 资源

- 参数映射：`references/intent-map.md`
- 接口能力：`references/api-catalog.md`
- 输出样式：`references/output-template.md`
