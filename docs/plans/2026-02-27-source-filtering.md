# Feed API 信源筛选功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为所有 feed API 添加信源筛选功能，支持通过 ID（精确）或名称（模糊）筛选单个或多个信源

**Architecture:** 
- 共享工具层提供参数解析和名称解析功能
- API 层添加 4 个可选参数（source_id/source_ids/source_name/source_names）
- Service 层各模块独立调用工具函数应用筛选逻辑

**Tech Stack:** FastAPI, Python 3.11+, 现有 JSON 存储系统

---

## Task 1: 添加共享工具函数 - 参数解析

**Files:**
- Modify: `app/services/intel/shared.py`
- Create: `tests/test_source_filter.py`

**Step 1: 编写失败的测试**

创建测试文件：

```python
# tests/test_source_filter.py
import pytest
from app.services.intel.shared import parse_source_filter


def test_parse_source_filter_returns_none_when_all_params_empty():
    """所有参数为空时返回 None（不筛选）"""
    result = parse_source_filter(None, None, None, None)
    assert result is None


def test_parse_source_filter_single_id():
    """单个 source_id"""
    result = parse_source_filter("gov_cn_zhengce", None, None, None)
    assert result == {"gov_cn_zhengce"}


def test_parse_source_filter_multiple_ids():
    """逗号分隔的多个 source_ids"""
    result = parse_source_filter(None, "id1,id2,id3", None, None)
    assert result == {"id1", "id2", "id3"}


def test_parse_source_filter_whitespace_handling():
    """处理空白字符和空项"""
    result = parse_source_filter(" id1 ", " id2 , , id3 ", None, None)
    assert result == {"id1", "id2", "id3"}


def test_parse_source_filter_deduplication():
    """去重：source_id 和 source_ids 中有重复"""
    result = parse_source_filter("id1", "id1,id2", None, None)
    assert result == {"id1", "id2"}


def test_parse_source_filter_all_empty_strings():
    """全是空字符串时返回空集合"""
    result = parse_source_filter("", " , , ", None, None)
    assert result == set()
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/test_source_filter.py -v
```

预期输出：所有测试 FAIL，提示 `parse_source_filter` 函数未定义

**Step 3: 实现 parse_source_filter 函数（不含名称解析）**

在 `app/services/intel/shared.py` 末尾添加：

```python
def parse_source_filter(
    source_id: str | None,
    source_ids: str | None,
    source_name: str | None,
    source_names: str | None,
) -> set[str] | None:
    """解析信源筛选参数，返回信源 ID 集合。
    
    Args:
        source_id: 单个信源 ID（精确）
        source_ids: 多个信源 ID，逗号分隔（精确）
        source_name: 单个信源名称（模糊）
        source_names: 多个信源名称，逗号分隔（模糊）
        
    Returns:
        None: 不筛选（返回所有信源）
        set[str]: 信源 ID 集合（已去重）
    """
    if not any([source_id, source_ids, source_name, source_names]):
        return None
    
    result = set()
    
    # 处理 ID（精确匹配）
    if source_id and source_id.strip():
        result.add(source_id.strip())
    if source_ids:
        for s in source_ids.split(','):
            if s.strip():
                result.add(s.strip())
    
    # TODO: 处理 name（模糊匹配）- 在 Task 2 实现
    if source_name or source_names:
        raise NotImplementedError("Name filtering not yet implemented")
    
    return result if result else set()
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/test_source_filter.py::test_parse_source_filter_returns_none_when_all_params_empty -v
pytest tests/test_source_filter.py::test_parse_source_filter_single_id -v
pytest tests/test_source_filter.py::test_parse_source_filter_multiple_ids -v
pytest tests/test_source_filter.py::test_parse_source_filter_whitespace_handling -v
pytest tests/test_source_filter.py::test_parse_source_filter_deduplication -v
pytest tests/test_source_filter.py::test_parse_source_filter_all_empty_strings -v
```

预期：所有测试 PASS

**Step 5: Commit**

```bash
git add app/services/intel/shared.py tests/test_source_filter.py
git commit -m "feat: add parse_source_filter (ID only, name TODO)

- Support source_id and source_ids parameters
- Handle whitespace and deduplication
- Return None when no filter, set when filtered
- Name filtering deferred to Task 2

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 2: 添加名称解析功能

**Files:**
- Modify: `app/services/intel/shared.py`
- Modify: `tests/test_source_filter.py`

**Step 1: 编写名称解析测试**

在 `tests/test_source_filter.py` 添加：

```python
from unittest.mock import patch
from app.services.intel.shared import resolve_source_ids_by_names


def test_resolve_source_ids_by_names_exact_match():
    """精确匹配信源名称"""
    mock_sources = [
        {"id": "gov_cn", "name": "中国政府网"},
        {"id": "xinhua", "name": "新华社"},
    ]
    with patch('app.services.source_service.get_all_sources', return_value=mock_sources):
        result = resolve_source_ids_by_names(["中国政府网"])
        assert result == {"gov_cn"}


def test_resolve_source_ids_by_names_fuzzy_match():
    """模糊匹配：子串匹配"""
    mock_sources = [
        {"id": "gov_cn", "name": "中国政府网-最新政策"},
        {"id": "beijing_gov", "name": "北京市人民政府网"},
        {"id": "xinhua", "name": "新华社"},
    ]
    with patch('app.services.source_service.get_all_sources', return_value=mock_sources):
        result = resolve_source_ids_by_names(["政府网"])
        assert result == {"gov_cn", "beijing_gov"}


def test_resolve_source_ids_by_names_case_insensitive():
    """大小写不敏感"""
    mock_sources = [
        {"id": "arxiv", "name": "ArXiv CS.AI"},
    ]
    with patch('app.services.source_service.get_all_sources', return_value=mock_sources):
        result = resolve_source_ids_by_names(["arxiv"])
        assert result == {"arxiv"}


def test_resolve_source_ids_by_names_space_handling():
    """去除空格后匹配"""
    mock_sources = [
        {"id": "gov", "name": "中国 政府 网"},
    ]
    with patch('app.services.source_service.get_all_sources', return_value=mock_sources):
        result = resolve_source_ids_by_names(["政府网"])
        assert result == {"gov"}


def test_resolve_source_ids_by_names_no_match():
    """没有匹配时返回空集合"""
    mock_sources = [
        {"id": "gov", "name": "中国政府网"},
    ]
    with patch('app.services.source_service.get_all_sources', return_value=mock_sources):
        result = resolve_source_ids_by_names(["不存在的信源"])
        assert result == set()


def test_resolve_source_ids_by_names_multiple_patterns():
    """多个名称模式"""
    mock_sources = [
        {"id": "gov", "name": "中国政府网"},
        {"id": "xinhua", "name": "新华社"},
        {"id": "people", "name": "人民日报"},
    ]
    with patch('app.services.source_service.get_all_sources', return_value=mock_sources):
        result = resolve_source_ids_by_names(["政府", "新华"])
        assert result == {"gov", "xinhua"}
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/test_source_filter.py::test_resolve_source_ids_by_names_exact_match -v
```

预期：FAIL，提示 `resolve_source_ids_by_names` 未定义

**Step 3: 实现 resolve_source_ids_by_names**

在 `app/services/intel/shared.py` 的 `parse_source_filter` 之前添加：

```python
def resolve_source_ids_by_names(names: list[str]) -> set[str]:
    """根据信源名称（模糊匹配）解析出信源 ID 集合。
    
    Args:
        names: 待匹配的名称列表
        
    Returns:
        匹配到的信源 ID 集合
    """
    # 避免循环导入，在函数内部导入
    import asyncio
    from app.services.source_service import list_sources
    
    # 同步调用异步函数获取所有信源
    all_sources = asyncio.run(list_sources())
    matched_ids = set()
    
    for name_pattern in names:
        pattern_lower = name_pattern.lower().replace(' ', '')
        for source in all_sources:
            source_name_lower = source['name'].lower().replace(' ', '')
            if pattern_lower in source_name_lower:
                matched_ids.add(source['id'])
    
    return matched_ids
```

**Step 4: 更新 parse_source_filter 以支持名称参数**

修改 `parse_source_filter` 函数，替换 TODO 部分：

```python
    # 处理 name（模糊匹配）
    if source_name or source_names:
        names = []
        if source_name and source_name.strip():
            names.append(source_name.strip())
        if source_names:
            for s in source_names.split(','):
                if s.strip():
                    names.append(s.strip())
        
        if names:
            resolved_ids = resolve_source_ids_by_names(names)
            result.update(resolved_ids)
```

**Step 5: 运行测试验证通过**

```bash
pytest tests/test_source_filter.py -v
```

预期：所有测试 PASS

**Step 6: 添加集成测试（ID + 名称混合）**

在 `tests/test_source_filter.py` 添加：

```python
def test_parse_source_filter_mixed_id_and_name():
    """混合使用 ID 和名称参数"""
    mock_sources = [
        {"id": "gov", "name": "中国政府网"},
        {"id": "xinhua", "name": "新华社"},
    ]
    with patch('app.services.source_service.get_all_sources', return_value=mock_sources):
        result = parse_source_filter("arxiv", "github", "政府", None)
        # arxiv, github (ID) + gov (from "政府" name match)
        assert result == {"arxiv", "github", "gov"}
```

运行验证：

```bash
pytest tests/test_source_filter.py::test_parse_source_filter_mixed_id_and_name -v
```

**Step 7: Commit**

```bash
git add app/services/intel/shared.py tests/test_source_filter.py
git commit -m "feat: add name-based source filtering with fuzzy match

- Implement resolve_source_ids_by_names with substring match
- Case-insensitive and space-tolerant matching
- Integrate name resolution into parse_source_filter
- Full test coverage for name and mixed filtering

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 3: 修改政策 Feed API 和 Service

**Files:**
- Modify: `app/api/v1/intel/policy.py`
- Modify: `app/services/intel/policy/service.py`

**Step 1: 添加 API 参数**

修改 `app/api/v1/intel/policy.py` 的 `get_policy_feed` 函数：

```python
@router.get("/feed", ...)
async def get_policy_feed(
    category: str | None = Query(...),
    importance: str | None = Query(...),
    min_match_score: int | None = Query(...),
    keyword: str | None = Query(...),
    # 新增：信源筛选参数
    source_id: str | None = Query(None, description="按单个信源 ID 筛选（精确匹配）"),
    source_ids: str | None = Query(None, description="按多个信源 ID 筛选（逗号分隔，精确匹配）"),
    source_name: str | None = Query(None, description="按单个信源名称筛选（模糊匹配）"),
    source_names: str | None = Query(None, description="按多个信源名称筛选（逗号分隔，模糊匹配）"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return policy_service.get_policy_feed(
        category=category,
        importance=importance,
        min_match_score=min_match_score,
        keyword=keyword,
        source_id=source_id,
        source_ids=source_ids,
        source_name=source_name,
        source_names=source_names,
        limit=limit,
        offset=offset,
    )
```

**Step 2: 更新 Service 函数签名**

修改 `app/services/intel/policy/service.py` 的 `get_policy_feed` 函数签名：

```python
def get_policy_feed(
    category: str | None = None,
    importance: str | None = None,
    min_match_score: int | None = None,
    keyword: str | None = None,
    source_id: str | None = None,
    source_ids: str | None = None,
    source_name: str | None = None,
    source_names: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
```

**Step 3: 添加筛选逻辑**

在 `get_policy_feed` 函数中，加载数据后立即应用信源筛选：

```python
from app.services.intel.shared import parse_source_filter

def get_policy_feed(...):
    # 1. 加载数据
    data = load_intel_json("policy_intel/feed.json")
    items = data.get("items", [])
    
    # 2. 应用信源筛选（优先筛选，减少后续处理量）
    source_filter = parse_source_filter(source_id, source_ids, source_name, source_names)
    if source_filter:
        items = [item for item in items if item.get("source_id") in source_filter]
    
    # 3. 其他筛选逻辑（保持原有代码）
    if category:
        items = [item for item in items if item.get("category") == category]
    # ... 其他筛选 ...
```

**Step 4: 手工测试**

启动服务：

```bash
uvicorn app.main:app --reload
```

测试 API（在另一个终端）：

```bash
# 测试 source_id
curl "http://localhost:8000/api/v1/intel/policy/feed?source_id=gov_cn_zhengce" | jq '.items[0].source_id'

# 测试 source_name
curl "http://localhost:8000/api/v1/intel/policy/feed?source_name=政府" | jq '.items[] | .source_id' | sort -u

# 测试混合
curl "http://localhost:8000/api/v1/intel/policy/feed?source_id=gov_cn&source_names=新华" | jq '.total'
```

预期：返回的数据只包含指定信源

**Step 5: Commit**

```bash
git add app/api/v1/intel/policy.py app/services/intel/policy/service.py
git commit -m "feat(policy): add source filtering to policy feed API

- Add 4 source filter params to API endpoint
- Apply source filtering in service layer
- Filter early to optimize performance

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 4: 修改人事 Feed API 和 Service

**Files:**
- Modify: `app/api/v1/intel/personnel.py`
- Modify: `app/services/intel/personnel/service.py`

**Step 1: 修改 `/feed` 端点**

在 `app/api/v1/intel/personnel.py` 的 `get_personnel_feed` 函数添加参数：

```python
@router.get("/feed", ...)
async def get_personnel_feed(
    importance: str | None = Query(...),
    min_match_score: int | None = Query(...),
    keyword: str | None = Query(...),
    source_id: str | None = Query(None, description="按单个信源 ID 筛选（精确匹配）"),
    source_ids: str | None = Query(None, description="按多个信源 ID 筛选（逗号分隔，精确匹配）"),
    source_name: str | None = Query(None, description="按单个信源名称筛选（模糊匹配）"),
    source_names: str | None = Query(None, description="按多个信源名称筛选（逗号分隔，模糊匹配）"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return personnel_service.get_personnel_feed(
        importance=importance,
        min_match_score=min_match_score,
        keyword=keyword,
        source_id=source_id,
        source_ids=source_ids,
        source_name=source_name,
        source_names=source_names,
        limit=limit,
        offset=offset,
    )
```

**Step 2: 修改 `/enriched-feed` 端点**

同样修改 `get_enriched_feed` 函数：

```python
@router.get("/enriched-feed", ...)
async def get_enriched_feed(
    group: str | None = Query(...),
    importance: str | None = Query(...),
    min_relevance: int | None = Query(...),
    keyword: str | None = Query(...),
    source_id: str | None = Query(None, description="按单个信源 ID 筛选（精确匹配）"),
    source_ids: str | None = Query(None, description="按多个信源 ID 筛选（逗号分隔，精确匹配）"),
    source_name: str | None = Query(None, description="按单个信源名称筛选（模糊匹配）"),
    source_names: str | None = Query(None, description="按多个信源名称筛选（逗号分隔，模糊匹配）"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return personnel_service.get_enriched_feed(
        group=group,
        importance=importance,
        min_relevance=min_relevance,
        keyword=keyword,
        source_id=source_id,
        source_ids=source_ids,
        source_name=source_name,
        source_names=source_names,
        limit=limit,
        offset=offset,
    )
```

**Step 3: 更新 Service 层**

修改 `app/services/intel/personnel/service.py` 中的两个函数：

```python
from app.services.intel.shared import parse_source_filter

def get_personnel_feed(
    importance=None,
    min_match_score=None,
    keyword=None,
    source_id=None,
    source_ids=None,
    source_name=None,
    source_names=None,
    limit=50,
    offset=0,
):
    data = load_intel_json("personnel_intel/feed.json")
    items = data.get("items", [])
    
    # 应用信源筛选
    source_filter = parse_source_filter(source_id, source_ids, source_name, source_names)
    if source_filter:
        items = [item for item in items if item.get("source_id") in source_filter]
    
    # 其他筛选逻辑...
    ...

def get_enriched_feed(
    group=None,
    importance=None,
    min_relevance=None,
    keyword=None,
    source_id=None,
    source_ids=None,
    source_name=None,
    source_names=None,
    limit=50,
    offset=0,
):
    data = load_intel_json("personnel_intel/enriched_feed.json")
    items = data.get("items", [])
    
    # 应用信源筛选
    source_filter = parse_source_filter(source_id, source_ids, source_name, source_names)
    if source_filter:
        items = [item for item in items if item.get("source_id") in source_filter]
    
    # 其他筛选逻辑...
    ...
```

**Step 4: 手工测试**

```bash
# 测试 personnel/feed
curl "http://localhost:8000/api/v1/intel/personnel/feed?source_name=政府" | jq '.total'

# 测试 personnel/enriched-feed
curl "http://localhost:8000/api/v1/intel/personnel/enriched-feed?source_id=gov_cn" | jq '.total'
```

**Step 5: Commit**

```bash
git add app/api/v1/intel/personnel.py app/services/intel/personnel/service.py
git commit -m "feat(personnel): add source filtering to personnel feeds

- Add source filters to /feed and /enriched-feed endpoints
- Apply filtering in both service functions

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 5: 修改高校生态 Feed API 和 Service

**Files:**
- Modify: `app/api/v1/intel/university.py`
- Modify: `app/services/intel/university/service.py`

**Step 1: 更新 API 参数（已有 source_id，添加其他 3 个）**

修改 `app/api/v1/intel/university.py` 的 `get_feed` 函数：

```python
@router.get("/feed", ...)
async def get_feed(
    group: str | None = Query(...),
    source_id: str | None = Query(None, description="按单个信源 ID 筛选（精确匹配）"),
    # 新增以下 3 个参数
    source_ids: str | None = Query(None, description="按多个信源 ID 筛选（逗号分隔，精确匹配）"),
    source_name: str | None = Query(None, description="按单个信源名称筛选（模糊匹配）"),
    source_names: str | None = Query(None, description="按多个信源名称筛选（逗号分隔，模糊匹配）"),
    keyword: str | None = Query(...),
    date_from: date | None = Query(...),
    date_to: date | None = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    return uni_service.get_feed(
        group=group,
        source_id=source_id,
        source_ids=source_ids,
        source_name=source_name,
        source_names=source_names,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
```

**Step 2: 更新 Service 层**

修改 `app/services/intel/university/service.py` 的 `get_feed` 函数：

```python
from app.services.intel.shared import parse_source_filter

def get_feed(
    group=None,
    source_id=None,
    source_ids=None,
    source_name=None,
    source_names=None,
    keyword=None,
    date_from=None,
    date_to=None,
    page=1,
    page_size=20,
):
    data = load_intel_json("university_eco/feed.json")
    items = data.get("items", [])
    
    # 应用信源筛选（替换原有的单 source_id 逻辑）
    source_filter = parse_source_filter(source_id, source_ids, source_name, source_names)
    if source_filter:
        items = [item for item in items if item.get("source_id") in source_filter]
    
    # 其他筛选逻辑...
    if group:
        items = [item for item in items if item.get("group") == group]
    ...
```

**Step 3: 手工测试**

```bash
# 测试多 ID
curl "http://localhost:8000/api/v1/intel/university/feed?source_ids=tsinghua,pku" | jq '.total'

# 测试名称
curl "http://localhost:8000/api/v1/intel/university/feed?source_name=清华" | jq '.items[0].source_id'
```

**Step 4: Commit**

```bash
git add app/api/v1/intel/university.py app/services/intel/university/service.py
git commit -m "feat(university): enhance source filtering in university feed

- Add source_ids, source_name, source_names params
- Replace single source_id logic with unified filter
- Support multiple sources and name-based filtering

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 6: 修改科技前沿 Signals API 和 Service

**Files:**
- Modify: `app/api/v1/intel/tech_frontier.py`
- Modify: `app/services/intel/tech_frontier/service.py`

**Step 1: 添加 API 参数**

修改 `app/api/v1/intel/tech_frontier.py` 的 `get_signals` 函数：

```python
@router.get("/signals", ...)
async def get_signals(
    topic_id: str | None = Query(...),
    signal_type: str | None = Query(...),
    keyword: str | None = Query(...),
    source_id: str | None = Query(None, description="按单个信源 ID 筛选（精确匹配）"),
    source_ids: str | None = Query(None, description="按多个信源 ID 筛选（逗号分隔，精确匹配）"),
    source_name: str | None = Query(None, description="按单个信源名称筛选（模糊匹配）"),
    source_names: str | None = Query(None, description="按多个信源名称筛选（逗号分隔，模糊匹配）"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return tf_service.get_signals(
        topic_id=topic_id,
        signal_type=signal_type,
        keyword=keyword,
        source_id=source_id,
        source_ids=source_ids,
        source_name=source_name,
        source_names=source_names,
        limit=limit,
        offset=offset,
    )
```

**Step 2: 更新 Service 层**

修改 `app/services/intel/tech_frontier/service.py` 的 `get_signals` 函数：

```python
from app.services.intel.shared import parse_source_filter

def get_signals(
    topic_id=None,
    signal_type=None,
    keyword=None,
    source_id=None,
    source_ids=None,
    source_name=None,
    source_names=None,
    limit=50,
    offset=0,
):
    # 加载 topics 数据并提取所有信号
    data = load_intel_json("tech_frontier/topics.json")
    topics = data.get("topics", [])
    
    # 扁平化所有信号
    signals = []
    for topic in topics:
        # ... 提取 news 和 kol 信号的现有逻辑 ...
    
    # 应用信源筛选
    source_filter = parse_source_filter(source_id, source_ids, source_name, source_names)
    if source_filter:
        signals = [sig for sig in signals if sig.get("source_id") in source_filter]
    
    # 其他筛选逻辑...
    if topic_id:
        signals = [sig for sig in signals if sig.get("topic_id") == topic_id]
    ...
```

**Step 3: 手工测试**

```bash
curl "http://localhost:8000/api/v1/intel/tech_frontier/signals?source_name=twitter" | jq '.total'
```

**Step 4: Commit**

```bash
git add app/api/v1/intel/tech_frontier.py app/services/intel/tech_frontier/service.py
git commit -m "feat(tech_frontier): add source filtering to signals API

- Add 4 source filter params to /signals endpoint
- Apply filtering to flattened signal list

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 7: 修改基础文章 API 和 Service

**Files:**
- Modify: `app/api/v1/articles.py`
- Modify: `app/schemas/article.py`
- Modify: `app/services/article_service.py`

**Step 1: 更新 Schema**

修改 `app/schemas/article.py` 的 `ArticleSearchParams`：

```python
class ArticleSearchParams(BaseModel):
    """文章搜索参数（内部使用）。"""
    
    dimension: str | None = None
    source_id: str | None = None  # 已有
    source_ids: str | None = None  # 新增
    source_name: str | None = None  # 新增
    source_names: str | None = None  # 新增
    tags: list[str] | None = None
    keyword: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    sort_by: str = "crawled_at"
    order: str = "desc"
    page: int = 1
    page_size: int = 20
```

**Step 2: 更新依赖函数**

修改 `app/api/deps.py` 的 `get_article_search_params` 函数（如果存在）或直接在 API 中添加参数：

```python
# app/api/v1/articles.py

@router.get("/", ...)
async def list_articles(
    dimension: str | None = Query(None),
    source_id: str | None = Query(None, description="按单个信源 ID 筛选（精确匹配）"),
    source_ids: str | None = Query(None, description="按多个信源 ID 筛选（逗号分隔，精确匹配）"),
    source_name: str | None = Query(None, description="按单个信源名称筛选（模糊匹配）"),
    source_names: str | None = Query(None, description="按多个信源名称筛选（逗号分隔，模糊匹配）"),
    tags: str | None = Query(None),
    keyword: str | None = Query(None),
    # ... 其他参数
):
    params = ArticleSearchParams(
        dimension=dimension,
        source_id=source_id,
        source_ids=source_ids,
        source_name=source_name,
        source_names=source_names,
        # ... 其他字段
    )
    return await article_service.list_articles(params)
```

**Step 3: 更新 Service 层**

修改 `app/services/article_service.py` 的 `list_articles` 函数：

```python
from app.services.intel.shared import parse_source_filter

async def list_articles(params: ArticleSearchParams):
    # 加载所有文章数据
    all_articles = load_all_articles()  # 假设有这个函数
    
    # 应用信源筛选
    source_filter = parse_source_filter(
        params.source_id,
        params.source_ids,
        params.source_name,
        params.source_names,
    )
    if source_filter:
        all_articles = [a for a in all_articles if a.get("source_id") in source_filter]
    
    # 其他筛选逻辑...
    if params.dimension:
        all_articles = [a for a in all_articles if a.get("dimension") == params.dimension]
    ...
```

**Step 4: 同步更新 `/search` 端点**

确保 `/search` 端点也支持相同参数（如果它使用相同的 service 函数，则自动支持）。

**Step 5: 手工测试**

```bash
# 测试基础文章 API
curl "http://localhost:8000/api/v1/articles/?source_name=政府" | jq '.items | length'

curl "http://localhost:8000/api/v1/articles/?source_ids=gov_cn,xinhua&dimension=national_policy" | jq '.total'
```

**Step 6: Commit**

```bash
git add app/api/v1/articles.py app/schemas/article.py app/services/article_service.py
git commit -m "feat(articles): add enhanced source filtering to article API

- Add source_ids, source_name, source_names to schema
- Update API params and service logic
- Support name-based and multi-source filtering

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 8: 文档更新和最终验证

**Files:**
- Modify: `docs/CrawlStatus.md`
- Modify: `docs/TODO.md`
- Modify: `CLAUDE.md`

**Step 1: 更新 CrawlStatus.md**

在 `docs/CrawlStatus.md` 顶部更新日期，并在合适章节添加 API 使用说明：

```markdown
> 最后更新: 2026-02-27

...

## API 信源筛选功能

所有 feed 类 API 现已支持通过信源筛选数据，提供以下 4 个参数：

- `source_id`: 单个信源 ID（精确匹配）
- `source_ids`: 多个信源 ID，逗号分隔（精确匹配）
- `source_name`: 单个信源名称（模糊匹配）
- `source_names`: 多个信源名称，逗号分隔（模糊匹配）

**支持的端点**：
- `/api/v1/intel/policy/feed`
- `/api/v1/intel/personnel/feed`
- `/api/v1/intel/personnel/enriched-feed`
- `/api/v1/intel/university/feed`
- `/api/v1/intel/tech_frontier/signals`
- `/api/v1/articles/`

**示例**：
```bash
# 技术用户：使用 ID
GET /api/v1/intel/policy/feed?source_id=gov_cn_zhengce

# 业务用户：使用名称（模糊匹配）
GET /api/v1/intel/policy/feed?source_name=政府网

# 多选
GET /api/v1/intel/policy/feed?source_names=政府网,新华社,人民日报

# 混合
GET /api/v1/intel/policy/feed?source_id=arxiv&source_names=新华,政府
```
```

**Step 2: 更新 TODO.md**

在 `docs/TODO.md` 中标记信源筛选功能为完成：

```markdown
> 最后更新: 2026-02-27

...

## P0: 核心功能
- [x] Feed API 添加信源筛选功能（支持 ID 和名称，单选多选）
...
```

**Step 3: 更新 CLAUDE.md**

在 `CLAUDE.md` 的"常用命令"或"API 端点"章节提及信源筛选：

```markdown
## API 信源筛选

所有 feed API 支持 4 个信源筛选参数：
- `source_id/source_ids`: 精确 ID 匹配
- `source_name/source_names`: 模糊名称匹配（子串匹配，大小写不敏感）

详细说明见 `docs/CrawlStatus.md` 的"API 信源筛选功能"章节。
```

**Step 4: 全面手工验证**

测试每个端点的 4 种参数组合：

```bash
# 1. Policy feed
curl "http://localhost:8000/api/v1/intel/policy/feed?source_id=gov_cn" | jq '.total'
curl "http://localhost:8000/api/v1/intel/policy/feed?source_ids=gov_cn,xinhua" | jq '.total'
curl "http://localhost:8000/api/v1/intel/policy/feed?source_name=政府" | jq '.total'
curl "http://localhost:8000/api/v1/intel/policy/feed?source_names=政府,新华" | jq '.total'

# 2. Personnel feed
curl "http://localhost:8000/api/v1/intel/personnel/feed?source_name=政府" | jq '.total'

# 3. Personnel enriched-feed
curl "http://localhost:8000/api/v1/intel/personnel/enriched-feed?source_id=gov_cn" | jq '.total'

# 4. University feed
curl "http://localhost:8000/api/v1/intel/university/feed?source_name=清华" | jq '.total'

# 5. Tech frontier signals
curl "http://localhost:8000/api/v1/intel/tech_frontier/signals?source_name=twitter" | jq '.total'

# 6. Articles
curl "http://localhost:8000/api/v1/articles/?source_names=政府,新华" | jq '.total'
```

**Step 5: 检查 Swagger 文档**

访问 `http://localhost:8000/docs`，确认：
- 所有参数显示正确
- 参数描述清晰
- 可以通过 Swagger UI 正常调用

**Step 6: 运行 Lint 检查**

```bash
ruff check app/
```

预期：无错误

**Step 7: 最终 Commit**

```bash
git add docs/CrawlStatus.md docs/TODO.md CLAUDE.md
git commit -m "docs: update documentation for source filtering feature

- Add API usage guide in CrawlStatus.md
- Mark TODO item as completed
- Reference in CLAUDE.md

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## 完成检查清单

部署前验证：
- [ ] 所有单元测试通过 (`pytest tests/test_source_filter.py -v`)
- [ ] Ruff 检查无错误 (`ruff check app/`)
- [ ] 手工测试至少 6 个端点（每类一个）
- [ ] Swagger 文档参数显示正确
- [ ] 文档已更新（CrawlStatus.md, TODO.md, CLAUDE.md）

部署后验证（生产环境）：
- [ ] 测试 2-3 个真实业务场景
- [ ] 检查服务日志无异常
- [ ] 通知业务部门新功能上线

---

## 设计决策总结

1. **共享工具 + 独立实现**：复用参数解析，各模块独立应用筛选
2. **4 参数支持**：同时满足技术用户（ID）和业务用户（名称）
3. **模糊匹配**：子串匹配 + 大小写不敏感 + 去空格
4. **TDD 流程**：先写测试，验证失败，实现代码，验证通过
5. **分批提交**：每完成一个模块就提交，便于问题定位和回滚
6. **向后兼容**：所有参数可选，不影响现有调用

## 估算工时

- Task 1-2: 共享工具（1 小时）
- Task 3-6: 4 个 intel 模块（1.5 小时）
- Task 7: 基础文章 API（30 分钟）
- Task 8: 文档和验证（30 分钟）

**总计: 约 3.5 小时**
