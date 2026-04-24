import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from scalar_fastapi import get_scalar_api_reference

from app.api.academic_monitor import router as academic_monitor_router
from app.api.v1.router import v1_router
from app.console_api import console_api_app
from app.config import BASE_DIR, settings
from app.db.client import close_client, init_client
from app.db.pool import close_pool, init_pool
from app.scheduler.manager import SchedulerManager, load_all_source_configs

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
        "支持目录化筛选（维度/分组/标签/健康状态）与分面统计；"
        "并提供按信源直接取数（/sources/items）、信源解析（/sources/resolve）与"
        "弃用迁移表（/sources/deprecations）。",
    },
    {
        "name": "crawler-control",
        "description": "爬虫控制 — 前端 UI 专用接口，支持批量启动爬取、实时状态监控、"
        "自定义领域过滤、多格式导出（JSON/CSV/数据库）。",
    },
    {
        "name": "dimensions",
        "description": "维度视图 — 按 9 大维度（国家政策、北京政策、技术动态、人才政策、"
        "产业动态、高校动态、活动会议、人事变动、Twitter）浏览文章汇总。",
    },
    {
        "name": "health",
        "description": "系统健康 — 调度器状态、全局爬取健康度概览。",
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
    {
        "name": "daily-briefing",
        "description": "AI 早报 — LLM 生成的每日简报，包含叙事段落（带交互链接）和聚合指标卡片。"
        "数据来自全部 9 个维度的爬取结果和已处理的政策/人事情报。",
    },
    {
        "name": "university-eco",
        "description": "高校生态 — 45 所高校及 AI 研究机构新闻动态监测。"
        "提供总览仪表盘、分页文章 Feed（支持分组/信源/关键词/日期过滤）、"
        "文章详情和信源状态。",
    },
    {
        "name": "sentiment",
        "description": "舆情监测 — 国内社媒平台（小红书、抖音等）内容与评论监测。"
        "数据存储于 Supabase，提供内容信息流、互动统计、评论分析等功能。",
    },
    {
        "name": "social-kol",
        "description": "统一社媒KOL数据 — 面向 X/LinkedIn/YouTube/小宇宙等平台的"
        "统一账号/帖子/回复模型。"
        "支持批量导入、账号检索、帖子检索与热门回复查询。",
    },
    {
        "name": "social-posts",
        "description": "统一社媒帖子库 — social_posts 表的通用查询接口。"
        "支持列表、搜索、聚合统计和详情（含帖子热门回复）。",
    },
    {
        "name": "venues",
        "description": "学术社群 — AI 领域顶会与期刊知识库。"
        "维护顶会（AAAI/NeurIPS/CVPR 等）和期刊（Nature/TPAMI/JMLR 等）的级别、"
        "H5 指数、录用率、影响因子等元数据，支持按类型/级别/领域过滤。",
    },
    {
        "name": "leadership",
        "description": "高校领导 — 高校领导列表与机构领导详情查询。",
    },
    {
        "name": "reports",
        "description": "AI 分析报告 — 基于爬取数据生成多维度智能分析报告。"
        "支持舆情监测、政策分析、科技前沿、人事情报、高校生态等维度，"
        "提供数据洞察、风险预警、机会识别和行动建议。",
    },
]


async def _validate_startup() -> dict[str, str]:
    """Validate critical dependencies at startup. Returns issues dict."""
    issues: dict[str, str] = {}

    # 1. Data directories (create if missing)
    for subdir in [
        "data/raw",
        "data/processed/policy_intel",
        "data/processed/personnel_intel",
        "data/processed/tech_frontier",
        "data/processed/university_eco",
        "data/processed/daily_briefing",
        "data/state",
        "data/logs",
    ]:
        (BASE_DIR / subdir).mkdir(parents=True, exist_ok=True)
    logger.info("Startup check: data directories OK")

    # 2. Playwright browser (non-blocking)
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
    """Check if processed intel data is missing and pipeline should run.

    Returns True if ANY of these processed output files are missing,
    meaning the pipeline processing stages have never completed successfully.
    This handles the case where raw data exists (from individual crawl jobs)
    but processed data was never generated.
    """
    required_files = [
        "data/processed/policy_intel/feed.json",
        "data/processed/personnel_intel/feed.json",
        "data/processed/tech_frontier/topics.json",
        "data/processed/university_eco/feed.json",
    ]
    for rel_path in required_files:
        if not (BASE_DIR / rel_path).exists():
            logger.info("Missing processed file: %s — pipeline needed", rel_path)
            return True
    return False


def _check_needs_today_briefing_backfill() -> bool:
    """Trigger a catch-up pipeline if today's briefing is still missing after schedule time."""
    now = datetime.now(timezone.utc)
    scheduled_today = now.replace(
        hour=settings.PIPELINE_CRON_HOUR,
        minute=settings.PIPELINE_CRON_MINUTE,
        second=0,
        microsecond=0,
    )

    if now < scheduled_today:
        return False

    briefing_path = BASE_DIR / "data/processed/daily_briefing" / f"{now.date().isoformat()}.json"
    return not briefing_path.exists()


async def _check_needs_today_social_kol_backfill() -> bool:
    """Trigger a catch-up run when today's scheduled social KOL crawl was missed."""
    now_utc = datetime.now(timezone.utc)
    bj = ZoneInfo("Asia/Shanghai")
    now_bj = now_utc.astimezone(bj)
    scheduled_bj = now_bj.replace(hour=4, minute=0, second=0, microsecond=0)
    if now_bj < scheduled_bj:
        return False

    scheduled_utc = scheduled_bj.astimezone(timezone.utc)
    try:
        from app.db.client import get_client

        client = get_client()
        res = await (
            client.table("social_posts")
            .select("id", count="exact")
            .eq("platform", "x")
            .gte("crawled_at", scheduled_utc)
            .execute()
        )
        return int(res.count or 0) == 0
    except Exception as e:  # noqa: BLE001
        logger.warning("Social KOL backfill check skipped (DB unavailable): %s", e)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of scheduler and other resources."""
    logger.info("=" * 60)
    logger.info("  Intelligence Engine Backend Services starting")
    logger.info("=" * 60)

    # Step 0: Initialize database client
    db_ready = False
    db_init_error: Exception | None = None
    try:
        backend = settings.DB_BACKEND.strip().lower()
        if backend in {"postgres", "postgresql", "local"}:
            if settings.POSTGRES_DSN:
                await init_pool(dsn=settings.POSTGRES_DSN)
            else:
                await init_pool(
                    host=settings.POSTGRES_HOST,
                    port=settings.POSTGRES_PORT,
                    user=settings.POSTGRES_USER,
                    password=settings.POSTGRES_PASSWORD,
                    database=settings.POSTGRES_DB,
                )
            await init_client(backend="postgres")
            db_ready = True
            logger.info(
                "PostgreSQL client initialized (%s:%s/%s)",
                settings.POSTGRES_HOST,
                settings.POSTGRES_PORT,
                settings.POSTGRES_DB,
            )
        elif settings.SUPABASE_URL and settings.SUPABASE_KEY:
            await init_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_KEY,
                backend="supabase",
            )
            db_ready = True
            logger.info("Supabase client initialized")
        else:
            logger.warning(
                "No database backend configured; DB features will fallback to local JSON"
            )
    except Exception as e:
        db_init_error = e
        logger.warning("Database client initialization failed: %s", e)

    if settings.REQUIRE_DB_ON_STARTUP and not db_ready:
        base_msg = "Database is required but initialization failed"
        if db_init_error:
            raise RuntimeError(f"{base_msg}: {db_init_error}") from db_init_error
        raise RuntimeError(f"{base_msg}: no backend configured")

    # Step 0.5: Sync source catalog metadata into source_states
    try:
        from app.services.stores.source_state import sync_source_catalog_from_configs

        sync_result = await sync_source_catalog_from_configs(
            source_configs=load_all_source_configs(),
            mark_missing_unsupported=True,
        )
        logger.info(
            "Source catalog synced: upserted=%d, marked_unsupported=%d, deleted_missing=%d",
            sync_result.get("upserted", 0),
            sync_result.get("marked_unsupported", 0),
            sync_result.get("deleted_missing", 0),
        )
    except Exception as e:
        logger.warning("Source catalog sync failed: %s", e)

    # Step 1: Validate dependencies
    startup_issues = await _validate_startup()

    # Step 2: Start scheduler
    scheduler = SchedulerManager()
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
                    "Processed data missing — triggering initial pipeline"
                )
                await scheduler.trigger_pipeline()
            elif _check_needs_today_briefing_backfill():
                logger.info(
                    "Today's briefing cache missing after scheduled pipeline window — triggering catch-up pipeline"
                )
                await scheduler.trigger_pipeline()
        except Exception as e:
            logger.warning("Initial data check failed: %s", e)

        # Step 3.5: Catch-up social KOL crawl if today's scheduled run was missed.
        try:
            if await _check_needs_today_social_kol_backfill():
                logger.info(
                    "Today's social KOL crawl appears missing after 04:00 Asia/Shanghai — "
                    "triggering catch-up crawl for twitter_ai_kol_international"
                )
                await scheduler.trigger_source("twitter_ai_kol_international")
        except Exception as e:
            logger.warning("Social KOL catch-up check failed: %s", e)

    # Step 4: Build scholar institutions data (only if missing)
    try:
        from pathlib import Path
        institutions_file = Path("data/scholars/institutions.json")
        if not institutions_file.exists():
            from app.services.institution_builder import save_institutions_data
            save_institutions_data()
            logger.info("Scholar institutions data built (first time)")
        else:
            logger.info("Scholar institutions data already exists, skipping rebuild")
    except Exception as e:
        logger.warning("Failed to build scholar institutions data: %s", e)

    # Step 5: Summary
    if startup_issues:
        logger.warning("Startup completed with issues: %s", list(startup_issues))
    else:
        logger.info("Application startup complete — all checks passed")

    yield

    # Shutdown
    await close_client()
    await close_pool()

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
    title="Intelligence Engine Backend Services API",
    summary="中关村人工智能研究院 — 信息监测系统",
    description=(
        "## 概述\n\n"
        "信息监测系统 API，自动爬取多维度信源，为中关村人工智能研究院提供全方位的"
        "信息监测与商业智能服务。\n\n"
        "## 功能模块\n\n"
        "| 模块 | 说明 |\n"
        "|------|------|\n"
        "| **文章管理** | 全量文章的查询、搜索、统计 |\n"
        "| **信源管理** | 信源配置、状态监控、分面筛选、手动触发 |\n"
        "| **维度视图** | 多维度文章聚合浏览 |\n"
        "| **政策智能** | 规则引擎 + LLM 二级管线，政策机会挖掘 |\n"
        "| **人事情报** | 任免信息自动提取，LLM 相关性分析 |\n"
        "| **系统健康** | 调度器、爬取健康度监控 |\n\n"
        "## 维度说明\n\n"
        "- `national_policy` — 国家政策（国务院、部委）\n"
        "- `beijing_policy` — 北京政策（市/区政府）\n"
        "- `technology` — 技术动态（ArXiv、GitHub Trending、Hacker News 等）\n"
        "- `talent` — 人才政策\n"
        "- `industry` — 产业动态\n"
        "- `universities` — 高校动态（46 所高校 AI 院系）\n"
        "- `events` — 活动会议\n"
        "- `personnel` — 人事变动\n"
        "- `twitter` — Twitter/X KOL 动态\n"
        "- `scholars` — 学者师资信源（知识库导入）\n"
        "- `sentiment` — 舆情专项信源\n\n"
        "## 技术栈\n\n"
        "FastAPI + Local JSON Storage + APScheduler + "
        "httpx + BeautifulSoup4 + Playwright"
    ),
    version="0.2.0",
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
    expose_headers=["Content-Disposition"],
)

# Register API routes
app.include_router(v1_router)
app.include_router(
    academic_monitor_router,
    prefix="/academic-monitor/api/v1",
    tags=["academic-monitor-compat"],
)
app.mount("/console-api", console_api_app)

# Mount static files for frontend UI
from pathlib import Path
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(frontend_dir), html=True), name="ui")
    logger.info("Frontend UI mounted at /ui")

console_frontend_dir = Path(__file__).parent.parent / "crawler-console" / "dist"
if console_frontend_dir.exists():
    app.mount("/console", StaticFiles(directory=str(console_frontend_dir), html=True), name="console")
    logger.info("Crawler console mounted at /console")


@app.get("/", tags=["default"], summary="API 入口", include_in_schema=False)
async def root():
    return {
        "message": "Intelligence Engine Backend Services API",
        "version": "0.2.0",
        "docs": "/docs",
        "swagger": "/swagger",
        "openapi": "/openapi.json",
        "ui": "/ui",
        "console_api_docs": "/console-api/docs",
        "console_ui": "/console",
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
