from fastapi import FastAPI

from app.console_api.router import router

TAG_METADATA = [
    {
        "name": "console-overview",
        "description": "控制台总览、每日趋势与 OpenRouter API 监控接口。",
    },
    {
        "name": "console-sources",
        "description": "控制台信源管理接口，包含列表、启停、日志和单源触发。",
    },
    {
        "name": "console-manual-jobs",
        "description": "控制台手动批量爬取任务接口，包含启动、停止、状态和结果下载。",
    },
]

console_api_app = FastAPI(
    title="Crawler Console API",
    summary="爬虫控制面板专用 API",
    description=(
        "面向管理员控制台的专用 API。"
        "与主业务 API 文档隔离，避免主 `/swagger` 出现大量控制台内部接口。"
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
    openapi_tags=TAG_METADATA,
)

console_api_app.include_router(router)


@console_api_app.get("/", include_in_schema=False)
async def console_root() -> dict[str, str]:
    return {
        "name": "Crawler Console API",
        "docs": "/console-api/docs",
        "openapi": "/console-api/openapi.json",
    }
