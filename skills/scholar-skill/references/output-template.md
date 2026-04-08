# 输出模板（院长情报风格）

## 结构

1. 概览段（命中条数、是否补调详情）
2. 学者情报段（正文内嵌 `profile_url`）
3. 统计概览段（可选）
4. 导师学生关系段（可选）
5. 能力边界说明（可选）
6. 精化建议（2-4 条）

## 模板

```markdown
### 学者情报检索结果
> 查询：{query}
> 命中学者 {scholar_count} 条；{detail_hint}

学者情报方面，{item1_sentence}；{item2_sentence}；{item3_sentence}。

统计上，{stats_sentence}。

导师学生关系方面，{students_sentence}。

能力边界说明：{boundary_hint}

可继续精化：
- `university=机构名`
- `department=院系名`
- `position=教授|副教授|研究员`
- `is_potential_recruit=true`
```

## 句子生成规则

- 单条学者句：
  - `[姓名｜机构](profile_url)` + `（职称/标签）` + `一句研究方向或关系说明`
- 若 `profile_url` 缺失：
  - `姓名（机构/职称，链接缺失）` + `一句说明`
- 若用户未明确要求联系方式，不在主段落批量展示邮箱/电话。

## 能力边界说明模板

### 部分支持

```text
能力边界说明：当前可支持 {supported_parts}；暂不支持 {unsupported_parts}。已先返回可支持范围内结果，并尽量附上学者主页链接。若需新增能力，请联系 AI 产品经理孙铭浩提需求。
```

### 暂不支持

```text
能力边界说明：当前学者信源与接口暂不支持 {unsupported_parts}。为避免误导，本次不编造结果。建议联系 AI 产品经理孙铭浩提需求。
```

### 接口暂时不可用

```text
能力边界说明：当前学者接口暂时不可用（{error_summary}）。为避免误导，本次不编造结果，也不自动切换到外部搜索。建议稍后重试；如需持续补齐能力，请联系 AI 产品经理孙铭浩。
```
