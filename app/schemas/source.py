from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SourceResponse(BaseModel):
    """信源详情。"""

    id: str = Field(description="信源唯一 ID", examples=["tech_arxiv"])
    name: str = Field(description="信源名称", examples=["ArXiv AI Papers"])
    url: str = Field(
        description="信源 URL",
        examples=["https://arxiv.org/list/cs.AI/recent"],
    )
    dimension: str = Field(description="所属维度", examples=["technology"])
    crawl_method: str = Field(
        description="爬取方式: static / dynamic / rss / snapshot / custom",
        examples=["static"],
    )
    schedule: str = Field(
        description="调度频率: hourly / daily / twice_daily 等",
        examples=["daily"],
    )
    crawl_interval_minutes: int | None = Field(
        default=None, description="调度频率折算分钟（若可解析）", examples=[1440]
    )
    is_enabled: bool = Field(description="是否启用", examples=[True])
    priority: int = Field(description="优先级（1-5，1 最高）", examples=[2])
    last_crawl_at: datetime | None = Field(
        default=None, description="上次爬取时间"
    )
    last_success_at: datetime | None = Field(
        default=None, description="上次成功爬取时间"
    )
    consecutive_failures: int = Field(
        default=0, description="连续失败次数", examples=[0]
    )
    source_file: str | None = Field(
        default=None, description="来源配置文件名", examples=["technology.yaml"]
    )
    group: str | None = Field(
        default=None, description="信源分组", examples=["university_leadership_official"]
    )
    tags: list[str] = Field(
        default_factory=list, description="信源标签", examples=[["personnel", "leadership"]]
    )
    crawler_class: str | None = Field(
        default=None, description="自定义 crawler_class（如有）", examples=["twitter_search"]
    )
    source_type: str | None = Field(
        default=None,
        description="信源类型（如 policy_news / social_kol / university_leadership）",
    )
    source_platform: str | None = Field(
        default=None,
        description="信源平台（如 web / x / youtube / xiaoyuzhou / rss / api）",
    )
    institution_name: str | None = Field(
        default=None, description="关联高校名称（适用于高校类信源）"
    )
    institution_tier: str | None = Field(
        default=None, description="高校层级：985 / 211 / other"
    )
    dimension_name: str | None = Field(
        default=None, description="维度中文名", examples=["组织人事动态"]
    )
    dimension_description: str | None = Field(
        default=None, description="维度说明"
    )
    taxonomy_version: str | None = Field(
        default=None, description="专业分类版本号", examples=["v2"]
    )
    taxonomy_domain: str | None = Field(
        default=None, description="一级专业域 ID", examples=["policy_governance"]
    )
    taxonomy_domain_name: str | None = Field(
        default=None, description="一级专业域名称", examples=["政策治理"]
    )
    taxonomy_track: str | None = Field(
        default=None, description="二级主题 ID", examples=["policy_national"]
    )
    taxonomy_track_name: str | None = Field(
        default=None, description="二级主题名称", examples=["国家政策"]
    )
    taxonomy_scope: str | None = Field(
        default=None, description="覆盖范围 ID", examples=["national"]
    )
    taxonomy_scope_name: str | None = Field(
        default=None, description="覆盖范围名称", examples=["国家级"]
    )
    health_status: Literal["healthy", "warning", "failing", "unknown"] = Field(
        default="unknown", description="健康状态（基于连续失败次数与爬取记录）"
    )
    is_supported: bool = Field(
        default=True, description="是否仍在当前配置清单中（用于识别过期/下线信源）"
    )
    is_enabled_overridden: bool = Field(
        default=False, description="是否被运行时启停覆盖（非 YAML 原始状态）"
    )


class SourceUpdate(BaseModel):
    """信源更新请求体。"""

    is_enabled: bool | None = Field(
        default=None, description="启用或禁用信源"
    )


class SourceFacetItem(BaseModel):
    """分面聚合项。"""

    key: str = Field(description="分面值")
    label: str | None = Field(default=None, description="分面展示名")
    count: int = Field(description="数量")


class SourceDimensionFacetItem(SourceFacetItem):
    """维度分面（含启用数）。"""

    enabled_count: int = Field(description="启用数")


class SourceFacetsResponse(BaseModel):
    """信源筛选分面。"""

    dimensions: list[SourceDimensionFacetItem] = Field(default_factory=list)
    groups: list[SourceFacetItem] = Field(default_factory=list)
    tags: list[SourceFacetItem] = Field(default_factory=list)
    crawl_methods: list[SourceFacetItem] = Field(default_factory=list)
    source_types: list[SourceFacetItem] = Field(default_factory=list)
    source_platforms: list[SourceFacetItem] = Field(default_factory=list)
    schedules: list[SourceFacetItem] = Field(default_factory=list)
    health_statuses: list[SourceFacetItem] = Field(default_factory=list)
    taxonomy_domains: list[SourceFacetItem] = Field(default_factory=list)
    taxonomy_tracks: list[SourceFacetItem] = Field(default_factory=list)
    taxonomy_scopes: list[SourceFacetItem] = Field(default_factory=list)


class SourceCatalogResponse(BaseModel):
    """信源目录响应。"""

    generated_at: datetime = Field(description="生成时间（UTC）")
    total_sources: int = Field(description="全量信源数")
    filtered_sources: int = Field(description="过滤后信源数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")
    total_pages: int = Field(description="总页数")
    items: list[SourceResponse] = Field(default_factory=list)
    facets: SourceFacetsResponse | None = Field(
        default=None, description="分面统计（仅 include_facets=true 时返回）"
    )
    applied_filters: dict[str, Any] = Field(
        default_factory=dict, description="本次实际生效的筛选条件"
    )


class SourceResolveItem(BaseModel):
    """按关键词解析出的信源项。"""

    id: str = Field(description="信源 ID")
    name: str = Field(description="信源名称")
    dimension: str = Field(description="维度")
    group: str | None = Field(default=None, description="信源分组")
    source_type: str | None = Field(default=None, description="信源类型")
    source_platform: str | None = Field(default=None, description="信源平台")
    taxonomy_domain: str | None = Field(default=None, description="一级专业域 ID")
    taxonomy_track: str | None = Field(default=None, description="二级主题 ID")
    taxonomy_scope: str | None = Field(default=None, description="覆盖范围 ID")
    is_enabled: bool = Field(description="是否启用")
    recommended_endpoint: str = Field(description="推荐直接取数接口")


class SourceResolveResponse(BaseModel):
    """信源解析响应。"""

    query: str | None = Field(default=None, description="本次查询关键词")
    total: int = Field(description="匹配总数")
    page: int = Field(description="页码")
    page_size: int = Field(description="每页数量")
    total_pages: int = Field(description="总页数")
    items: list[SourceResolveItem] = Field(default_factory=list)


class ApiDeprecationItem(BaseModel):
    """API 弃用项。"""

    method: str = Field(description="HTTP 方法")
    path: str = Field(description="已弃用接口路径")
    replacement_path: str = Field(description="替代接口路径")
    sunset_date: str = Field(description="计划 Sunset 日期（YYYY-MM-DD）")
    note: str | None = Field(default=None, description="补充说明")


class ApiDeprecationResponse(BaseModel):
    """API 弃用列表响应。"""

    generated_at: datetime = Field(description="生成时间（UTC）")
    total: int = Field(description="弃用接口总数")
    items: list[ApiDeprecationItem] = Field(default_factory=list)
