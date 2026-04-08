# 输出模板（院长情报风格）

## 结构

1. 概览段（静态/动态/科研成果命中情况）
2. 机构画像段（可选）
3. 动态情报段（可选，正文内嵌原始 `url`）
4. 科研成果段（可选，正文内嵌原始 `url`）
5. 能力边界说明（可选）
6. 精化建议（2-4 条）

## 模板

```markdown
### 机构情报检索结果
> 查询：{query}
> 机构画像 {profile_count} 条，动态 {feed_count} 条，科研成果 {research_count} 条；{runtime_hint}

机构画像方面，{profile_sentence}。

动态方面，{feed_sentence1}；{feed_sentence2}；{feed_sentence3}。

科研成果方面，{research_sentence1}；{research_sentence2}；{research_sentence3}。

能力边界说明：{boundary_hint}

可继续精化：
- `classification=共建高校|兄弟院校|海外高校`
- `group=university_news|ai_institutes`
- `date_from=YYYY-MM-DD`
- `type=论文|专利|获奖`
```

## 句子生成规则

- 机构画像句：
  - `机构名（分类/优先级）` + `一句合作重点/重点院系/关键人数说明`
- 动态句：
  - `[标题](url)` + `（日期/来源/分组）` + `一句摘要`
- 科研成果句：
  - `[标题](url)` + `（机构/类型/影响力）` + `一句 AI 分析或正文摘要`
- 静态机构若只有内部记录链接，可说明“记录链接：/api/v1/institutions/{institution_id}`”，但不要说成外部原始信源。

## 能力边界说明模板

### 部分支持

```text
能力边界说明：当前可支持 {supported_parts}；暂不支持 {unsupported_parts}。已先返回可支持范围内结果，并标注了原始链接或记录链接。若需新增能力，请联系 AI 产品经理孙铭浩提需求。
```

### 暂不支持

```text
能力边界说明：当前机构信源与接口暂不支持 {unsupported_parts}。为避免误导，本次不编造结果。建议联系 AI 产品经理孙铭浩提需求。
```

### 接口暂时不可用

```text
能力边界说明：当前机构接口暂时不可用（{error_summary}）。为避免误导，本次不编造结果，也不自动切换到外部搜索。建议稍后重试；如需持续补齐能力，请联系 AI 产品经理孙铭浩。
```
