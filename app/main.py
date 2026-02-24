import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference

from app.api.v1.router import v1_router
from app.config import BASE_DIR, settings
from app.scheduler.manager import SchedulerManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAPI tag metadata — controls grouping & descriptions in Scalar / Apifox
# ---------------------------------------------------------------------------
TAG_METADATA = [
    {
        "name": "articles",
        "description": "文章管理 — 查询、搜索、统计和更新爬取到的文章。支持按维度、信源、关键词、"
        "日期范围过滤，以及分页排序。",
    },
    {
        "name": "sources",
        "description": "信源管理 — 查看信源配置与状态，启用/禁用信源，手动触发爬取，查看爬取日志。"
        "系统共 129 个信源（105 个启用），覆盖 9 个维度。",
    },
    {
        "name": "dimensions",
        "description": "维度视图 — 按 9 大维度（国家政策、北京政策、技术动态、人才政策、"
        "产业动态、高校动态、活动会议、人事变动、Twitter）浏览文章汇总。",
    },
    {
        "name": "health",
        "description": "系统健康 — 数据库连接检查、调度器状态、全局爬取健康度概览。",
    },
    {
        "name": "policy-intel",
        "description": "政策智能 — 基于规则引擎 + LLM 二级管线处理的政策情报。"
        "提供政策动态 Feed、政策机会看板（含资金/截止日/匹配度评分）和汇总统计。",
    },
    {
        "name": "personnel-intel",
        "description": "人事情报 — 自动提取任免信息，LLM 富化分析。"
        "提供人事动态 Feed、结构化任免变动、LLM 富化 Feed（含相关性评分/行动建议）和统计。",
    },
]


async def _validate_startup() -> dict[str, str]:
    """Validate critical dependencies at startup. Returns issues dict."""
    issues: dict[str, str] = {}

    # 1. Database connectivity
    try:
        from sqlalchemy import text

        from app.database import async_session_factory

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        logger.info("Startup check: database connection OK")
    except Exception as e:
        issues["database"] = str(e)
        logger.error("Startup check: database connection FAILED: %s", e)

    # 2. Data directories (create if missing)
    for subdir in [
        "data/raw",
        "data/processed/policy_intel",
        "data/processed/personnel_intel",
    ]:
        (BASE_DIR / subdir).mkdir(parents=True, exist_ok=True)
    logger.info("Startup check: data directories OK")

    # 3. Playwright browser (non-blocking)
    try:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        await browser.close()
        await pw.stop()
        logger.info("Startup check: Playwright browser OK")
    except Exception as e:
        issues["playwright"] = str(e)
        logger.warning(
            "Startup check: Playwright unavailable: %s (dynamic crawls will fail)", e
        )

    return issues


async def _check_needs_initial_data() -> bool:
    """Check if this is a fresh installation with no crawled data."""
    # Check 1: Any JSON in data/raw/?
    raw_dir = BASE_DIR / "data" / "raw"
    has_local_data = False
    if raw_dir.exists():
        for child in raw_dir.iterdir():
            if child.is_dir():
                for _ in child.rglob("*.json"):
                    has_local_data = True
                    break
            if has_local_data:
                break

    if has_local_data:
        return False

    # Check 2: Any articles in database?
    try:
        from sqlalchemy import text

        from app.database import async_session_factory

        async with async_session_factory() as session:
            result = await session.execute(
                text("SELECT EXISTS (SELECT 1 FROM articles LIMIT 1)")
            )
            has_db_data = result.scalar()
            if has_db_data:
                return False
    except Exception:
        pass  # Table might not exist yet

    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of scheduler and other resources."""
    logger.info("=" * 60)
    logger.info("  Information Crawler starting")
    logger.info("=" * 60)

    # Step 1: Validate dependencies
    startup_issues = await _validate_startup()

    db_available = "database" not in startup_issues
    if not db_available:
        logger.warning(
            "Database unavailable — running in file-only mode. "
            "Crawl results will be saved as local JSON only."
        )

    # Step 2: Start scheduler (works with or without DB)
    scheduler = SchedulerManager(db_available=db_available)
    try:
        await scheduler.start()
    except Exception as e:
        logger.error("Scheduler failed to start: %s", e)
        scheduler = None

    # Step 3: Initial data population (if fresh install)
    if scheduler and settings.STARTUP_CRAWL_ENABLED:
        try:
            needs_initial = await _check_needs_initial_data()
            if needs_initial:
                logger.info(
                    "Fresh installation detected — triggering initial pipeline"
                )
                await scheduler.trigger_pipeline()
        except Exception as e:
            logger.warning("Initial data check failed: %s", e)

    # Step 4: Summary
    if startup_issues:
        logger.warning("Startup completed with issues: %s", list(startup_issues))
    else:
        logger.info("Application startup complete — all checks passed")

    yield

    # Shutdown
    if scheduler:
        try:
            await scheduler.stop()
        except Exception as e:
            logger.error("Scheduler failed to stop cleanly: %s", e)

    try:
        from app.crawlers.utils.playwright_pool import close_browser

        await close_browser()
    except Exception as e:
        logger.warning("Failed to close Playwright: %s", e)

    logger.info("Application shutdown complete")


app = FastAPI(
    title="Information Crawler API",
    summary="中关村人工智能研究院 — 信息监测系统",
    description=(
        "## 概述\n\n"
        "信息监测系统 API，自动爬取 **129 个信源**（105 个启用），覆盖 **9 个维度**，"
        "为中关村人工智能研究院提供全方位的信息监测与商业智能服务。\n\n"
        "## 功能模块\n\n"
        "| 模块 | 说明 |\n"
        "|------|------|\n"
        "| **文章管理** | 全量文章的查询、搜索、统计 |\n"
        "| **信源管理** | 129 个信源的配置、状态监控、手动触发 |\n"
        "| **维度视图** | 9 大维度的文章聚合浏览 |\n"
        "| **政策智能** | 规则引擎 + LLM 二级管线，政策机会挖掘 |\n"
        "| **人事情报** | 任免信息自动提取，LLM 相关性分析 |\n"
        "| **系统健康** | 数据库、调度器、爬取健康度监控 |\n\n"
        "## 维度说明\n\n"
        "- `national_policy` — 国家政策（国务院、部委）\n"
        "- `beijing_policy` — 北京政策（市/区政府）\n"
        "- `technology` — 技术动态（ArXiv、GitHub Trending、Hacker News 等）\n"
        "- `talent` — 人才政策\n"
        "- `industry` — 产业动态\n"
        "- `universities` — 高校动态（46 所高校 AI 院系）\n"
        "- `events` — 活动会议\n"
        "- `personnel` — 人事变动\n"
        "- `twitter` — Twitter/X KOL 动态\n\n"
        "## 技术栈\n\n"
        "FastAPI + SQLAlchemy(async) + PostgreSQL(Supabase) + APScheduler + "
        "httpx + BeautifulSoup4 + Playwright"
    ),
    version="0.1.0",
    openapi_tags=TAG_METADATA,
    contact={
        "name": "中关村人工智能研究院",
        "url": "https://www.zgcaiia.com",
    },
    license_info={
        "name": "Internal Use",
    },
    lifespan=lifespan,
    # Keep default /docs (Swagger UI) and add Scalar at /scalar
    docs_url="/swagger",
    redoc_url=None,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(v1_router)


@app.get("/", tags=["default"], summary="API 入口", include_in_schema=False)
async def root():
    return {
        "message": "Information Crawler API",
        "version": "0.1.0",
        "docs": "/docs",
        "swagger": "/swagger",
        "openapi": "/openapi.json",
    }


# ---------------------------------------------------------------------------
# Scalar API Reference — modern, beautiful API documentation UI
# ---------------------------------------------------------------------------
@app.get("/docs", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )
