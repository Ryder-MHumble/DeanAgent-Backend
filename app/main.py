import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import v1_router
from app.scheduler.manager import SchedulerManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of scheduler and other resources."""
    # Startup
    scheduler = SchedulerManager()
    try:
        await scheduler.start()
        logger.info("Application startup complete")
    except Exception as e:
        logger.error("Scheduler failed to start: %s", e)

    yield

    # Shutdown
    try:
        await scheduler.stop()
    except Exception as e:
        logger.error("Scheduler failed to stop cleanly: %s", e)

    # Close Playwright browser if active
    try:
        from app.crawlers.utils.playwright_pool import close_browser

        await close_browser()
    except Exception as e:
        logger.warning("Failed to close Playwright: %s", e)

    logger.info("Application shutdown complete")


app = FastAPI(
    title="Information Crawler API",
    description="信息监测系统 API - 爬取 ~112 个信源，覆盖 9 个维度",
    version="0.1.0",
    lifespan=lifespan,
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


@app.get("/")
async def root():
    return {"message": "Information Crawler API", "docs": "/docs"}
